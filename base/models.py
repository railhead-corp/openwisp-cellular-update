import logging
from datetime import timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path

import jsonschema
import swapper
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from private_storage.fields import PrivateFileField

from openwisp_controller.connection.exceptions import NoWorkingDeviceConnectionError
from openwisp_users.mixins import ShareableOrgMixin
from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings
from ..exceptions import (
    ModemReconnectionFailed,
    ModemUpgradeAborted,
    ModemUpgradeNotNeeded,
    ModemUpgradeOptionsException,
    RecoverableModemFailure,
)
from ..hardware import (
    MODEM_IMAGE_MAP,
    MODEM_IMAGE_TYPE_CHOICES,
    REVERSE_MODEM_IMAGE_MAP,
)
from ..swapper import get_model_name, load_model
from ..tasks import (
    batch_modem_upgrade_operation,
    create_all_device_modem_firmwares,
    create_device_modem_firmware,
    upgrade_modem_firmware,
)
from ..utils import (
    get_modem_upgrader_class_for_device,
    get_modem_upgrader_class_from_device_connection,
    get_modem_upgrader_schema_for_device,
)

logger = logging.getLogger(__name__)


class ModemUpgradeOptionsMixin(models.Model):
    """Mixin for models that support modem upgrade options"""

    upgrade_options = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    def validate_upgrade_options(self):
        if not self.upgrade_options:
            return
        if not getattr(self.upgrader_class, "SCHEMA", None):
            raise ValidationError(
                _("Using upgrade options is not allowed with this upgrader.")
            )
        try:
            self.upgrader_class.validate_upgrade_options(self.upgrade_options)
        except jsonschema.ValidationError:
            raise ValidationError("The upgrade options are invalid")
        except ModemUpgradeOptionsException as error:
            raise ValidationError(*error.args)

    def clean(self):
        super().clean()
        self.validate_upgrade_options()


class AbstractModemCategory(ShareableOrgMixin, TimeStampedEditableModel):
    """Abstract model for modem firmware categories"""

    name = models.CharField(max_length=64, db_index=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        verbose_name = _("Modem Category")
        verbose_name_plural = _("Modem Categories")
        unique_together = ("name", "organization")


class AbstractModemBuild(TimeStampedEditableModel):
    """Abstract model for modem firmware builds"""

    category = models.ForeignKey(
        get_model_name("ModemCategory"),
        on_delete=models.CASCADE,
        verbose_name=_("modem category"),
        help_text=_(
            "Group modem firmware by manufacturer, model series, "
            "or deployment scenario"
        ),
    )
    version = models.CharField(max_length=32, db_index=True)
    modem_model = models.CharField(
        _("Modem model identifier"),
        max_length=64,
        blank=True,
        null=True,
        help_text=_(
            "Modem model identifier (e.g., FN990AXX) used to automatically "
            "recognize compatible devices"
        ),
    )
    changelog = models.TextField(
        _("change log"),
        blank=True,
        help_text=_(
            "Descriptive text indicating what has changed since "
            "the previous version"
        ),
    )

    class Meta:
        abstract = True
        verbose_name = _("Modem Build")
        verbose_name_plural = _("Modem Builds")
        unique_together = ("category", "version")
        ordering = ("-created",)

    def __str__(self):
        try:
            return f"{self.category} v{self.version}"
        except ObjectDoesNotExist:
            return super().__str__()

    def clean(self):
        # Ensure uniqueness of (category__organization, modem_model)
        try:
            category = self.category
        except ObjectDoesNotExist:
            return
        if not self.modem_model:
            return
        if (
            load_model("ModemBuild")
            .objects.filter(
                category__organization=category.organization, modem_model=self.modem_model
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {
                    "modem_model": _(
                        f'A build with this modem model ("{self.modem_model}") and '
                        f'organization ("{category.organization}") already exists'
                    )
                }
            )

    def batch_upgrade(
        self,
        selected_device_fw_ids=None,
        selected_firmwareless_device_ids=None,
        upgrade_options=None,
    ):
        """Initiate a batch upgrade operation for this build"""
        upgrade_options = upgrade_options or {}
        batch = load_model("ModemBatchUpgradeOperation")(
            build=self, upgrade_options=upgrade_options
        )
        batch.full_clean()
        batch.save()
        transaction.on_commit(
            partial(
                batch_modem_upgrade_operation.delay,
                batch.pk,
                selected_device_fw_ids or [],
                selected_firmwareless_device_ids or [],
            )
        )
        return batch

    def _find_related_device_modem_firmwares(self, select_devices=False):
        """
        Returns all DeviceModemFirmware objects related to this build's category
        that have not been installed yet
        """
        related = ["image"]
        if select_devices:
            related.append("device")
        return (
            load_model("DeviceModemFirmware")
            .objects.all()
            .select_related(*related)
            .filter(image__build__category_id=self.category_id)
            .exclude(image__build=self, installed=True)
            .order_by("-created")
        )

    def _find_firmwareless_devices(self, boards=None):
        """
        Returns devices which have no related DeviceModemFirmware
        but are upgradable to one of the images in this build
        """
        if boards is None:
            boards = []
            for image in self.modemfirmwareimage_set.all():
                boards += image.boards
        Device = swapper.load_model("config", "Device")
        qs = Device.objects.filter(
            devicemodemfirmware__isnull=True,
            model__in=boards,
        )
        if self.category.organization_id:
            qs = qs.filter(organization_id=self.category.organization_id)
        return qs.order_by("-created")


def get_modem_build_directory(instance, filename):
    """Generate storage path for modem firmware images"""
    build_pk = str(instance.build.pk)
    return "/".join(["modem", build_pk, filename])


class AbstractModemFirmwareImage(TimeStampedEditableModel):
    """Abstract model for modem firmware images"""

    build = models.ForeignKey(get_model_name("ModemBuild"), on_delete=models.CASCADE)
    file = PrivateFileField(
        "File",
        upload_to=get_modem_build_directory,
        max_file_size=app_settings.MAX_FILE_SIZE,
        storage=app_settings.PRIVATE_STORAGE_INSTANCE,
        max_length=255,
    )
    type = models.CharField(
        blank=True,
        max_length=128,
        choices=MODEM_IMAGE_TYPE_CHOICES,
        help_text=_(
            "Modem firmware image type: model or manufacturer. "
        ),
    )

    class Meta:
        abstract = True
        verbose_name = _("Modem Firmware Image")
        verbose_name_plural = _("Modem Firmware Images")
        unique_together = ("build", "type")

    def __str__(self):
        if hasattr(self, "build") and self.type:
            return f"{self.build}: {self.get_type_display()}"
        return super().__str__()

    @property
    def boards(self):
        """Get list of compatible device models for this image"""
        return MODEM_IMAGE_MAP[self.type]["boards"]

    def clean(self):
        if self.file and self.file.name:
            if not self.file.name.lower().endswith('.bin'):
                raise ValidationError(
                    {"file": _("Only .bin firmware files are allowed.")}
                )
        self._clean_type()
        try:
            self.boards
        except KeyError:
            raise ValidationError({"type": "Could not find boards for this type"})

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._remove_file(self.file.name)

    @classmethod
    def _remove_file(cls, file_path):
        """
        Deletes a file and cleans up its parent directory if empty.
        """
        storage = cls.file.field.storage
        try:
            storage.delete(file_path)
            logger.info("Deleted modem firmware file: %s", file_path)
        except Exception as e:
            logger.error("Error deleting modem firmware file %s: %s", file_path, str(e))
            return False
        # Delete the directory if empty
        try:
            dir_path = str(Path(file_path).parent)
            if not dir_path or dir_path == ".":
                return True
            dirs, files = storage.listdir(dir_path)
            if dirs or files:
                logger.debug("Directory %s is not empty, skipping deletion", dir_path)
                return True
            storage.delete(dir_path)
        except FileNotFoundError:
            logger.debug("Directory %s already removed", dir_path)
        except Exception as error:
            logger.error("Could not delete directory %s: %s", dir_path, str(error))
        else:
            logger.info("Deleted empty directory: %s", dir_path)
        return True

    def _clean_type(self):
        """Auto-determine type if missing"""
        if self.type:
            return
        filename = self.file.name
        # Extract type from filename (customize based on naming convention)
        self.type = "-".join(filename.split("-")[1:])

    @classmethod
    def build_pre_delete_handler(cls, sender, instance, **kwargs):
        """Trigger deletion of modem firmware files when a Build is deleted"""
        cls.schedule_firmware_file_deletion(build=instance)

    @classmethod
    def category_pre_delete_handler(cls, sender, instance, **kwargs):
        """Trigger deletion of modem firmware files when a Category is deleted"""
        cls.schedule_firmware_file_deletion(build__category=instance)

    @classmethod
    def organization_pre_delete_handler(cls, sender, instance, **kwargs):
        """Trigger deletion of modem firmware files when an Organization is deleted"""
        cls.schedule_firmware_file_deletion(build__category__organization=instance)

    @classmethod
    def schedule_firmware_file_deletion(cls, **filter_kwargs):
        """Schedule deletion of modem firmware image files in the background"""
        from ..tasks import delete_modem_firmware_files

        files_to_delete = []
        queryset = cls.objects.filter(**filter_kwargs)
        for image in queryset.iterator():
            if image.file and image.file.name:
                files_to_delete.append(image.file.name)
        if files_to_delete:
            transaction.on_commit(
                partial(delete_modem_firmware_files.delay, files_to_delete)
            )


class AbstractDeviceModemFirmware(TimeStampedEditableModel):
    """Abstract model for device modem firmware associations"""

    device = models.OneToOneField(
        swapper.get_model_name("config", "Device"), on_delete=models.CASCADE
    )
    image = models.ForeignKey(
        get_model_name("ModemFirmwareImage"), on_delete=models.CASCADE
    )
    installed = models.BooleanField(default=False)
    _old_image = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_old_image()

    class Meta:
        verbose_name = _("Device Modem Firmware")
        abstract = True

    def clean(self):
        if not hasattr(self, "image") or not hasattr(self, "device"):
            return
        if (
            self.image.build.category.organization is not None
            and self.image.build.category.organization != self.device.organization
        ):
            raise ValidationError(
                {
                    "image": _(
                        "The organization of the image doesn't "
                        "match the organization of the device"
                    )
                }
            )
        if self.device.deviceconnection_set.count() < 1:
            raise ValidationError(
                _(
                    "This device does not have a related connection object defined "
                    "yet and therefore it would not be possible to upgrade it, "
                    'please add one in the section named "Credentials"'
                )
            )
        if self.device.model not in self.image.boards:
            raise ValidationError(_("Device model and modem image model do not match"))

    @property
    def image_has_changed(self):
        return self._state.adding or self.image_id != self._old_image.id

    def save(self, batch=None, upgrade=True, upgrade_options=None, *args, **kwargs):
        """Save device modem firmware and optionally trigger upgrade"""
        if upgrade and (self.image_has_changed or not self.installed):
            self.installed = False
            super().save(*args, **kwargs)
            self.create_upgrade_operation(batch, upgrade_options=upgrade_options or {})
        else:
            super().save(*args, **kwargs)
        self._update_old_image()

    def _update_old_image(self):
        if hasattr(self, "image"):
            self._old_image = self.image

    def create_upgrade_operation(self, batch, upgrade_options=None):
        """Create and queue an upgrade operation for this device"""
        uo_model = load_model("ModemUpgradeOperation")
        operation = uo_model(
            device=self.device, image=self.image, upgrade_options=upgrade_options
        )
        if batch:
            operation.batch = batch
        operation.full_clean()
        operation.save()
        # Launch upgrade_modem_firmware in the background once committed
        transaction.on_commit(partial(upgrade_modem_firmware.delay, operation.pk))
        return operation

    @classmethod
    def create_for_device(cls, device, modem_image=None):
        """
        Create a DeviceModemFirmware instance for the specified device.
        If modem_image is not supplied, attempt automatic detection.
        Returns None if creation is not possible.
        """
        DeviceModemFirmware = load_model("DeviceModemFirmware")
        ModemFirmwareImage = load_model("ModemFirmwareImage")
        image_type = REVERSE_MODEM_IMAGE_MAP.get(device.model)

        if not image_type:
            return

        if not modem_image:
            try:
                modem_image = ModemFirmwareImage.objects.get(
                    build__category__organization_id=device.organization_id,
                    build__modem_model=getattr(device, "modem_model", None),
                    type=image_type,
                )
            except ModemFirmwareImage.DoesNotExist:
                return

        device_fw = DeviceModemFirmware(
            device=device, image=modem_image, installed=True
        )
        try:
            device_fw.full_clean()
        except ValidationError as e:
            logger.warning(e)
            return
        device_fw.save(upgrade=False)
        return device_fw

    @classmethod
    def auto_add_device_modem_firmware_to_device(cls, instance, created, **kwargs):
        """Automatically associate DeviceModemFirmware to registered devices"""
        if not created:
            return
        modem_model = getattr(instance, "modem_model", None)
        if not modem_model or not instance.model:
            return
        if instance.model not in REVERSE_MODEM_IMAGE_MAP:
            return

        transaction.on_commit(
            partial(create_device_modem_firmware.delay, instance.pk)
        )

    @classmethod
    def auto_create_device_modem_firmwares(cls, instance, created, **kwargs):
        """Auto-create device modem firmwares when new image is added"""
        if created:
            transaction.on_commit(
                partial(create_all_device_modem_firmwares.delay, instance.pk)
            )

    @classmethod
    def get_image_queryset_for_device(cls, device, device_modem_firmware=None):
        """Get queryset of compatible modem firmware images for a device"""
        ModemFirmwareImage = cls.image.field.related_model
        qs = (
            ModemFirmwareImage.objects.filter(
                Q(build__category__organization_id=device.organization_id)
                | Q(build__category__organization__isnull=True)
            )
            .order_by("-created")
            .select_related("build", "build__category")
        )
        # Filter by device model compatibility
        if device.model and device.model in REVERSE_MODEM_IMAGE_MAP:
            qs = qs.filter(type=REVERSE_MODEM_IMAGE_MAP[device.model])
        # Restrict to same category if DeviceModemFirmware already exists
        if device_modem_firmware and hasattr(device_modem_firmware, "image"):
            qs = qs.filter(
                build__category_id=device_modem_firmware.image.build.category_id
            )
        return qs


class AbstractModemBatchUpgradeOperation(
    ModemUpgradeOptionsMixin, TimeStampedEditableModel
):
    """Abstract model for batch modem upgrade operations"""

    build = models.ForeignKey(get_model_name("ModemBuild"), on_delete=models.CASCADE)
    STATUS_CHOICES = (
        ("idle", _("idle")),
        ("in-progress", _("in progress")),
        ("success", _("completed successfully")),
        ("failed", _("completed with some failures")),
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0]
    )

    class Meta:
        abstract = True
        verbose_name = _("Modem Mass Upgrade Operation")
        verbose_name_plural = _("Modem Mass Upgrade Operations")

    def __str__(self):
        return f"Modem Upgrade of {self.build}"

    def update(self):
        """Update batch status based on individual operations"""
        operations = self.modemupgradeoperation_set
        if operations.filter(status="in-progress").exists():
            return
        # Mark as failed if any operation failed
        if operations.filter(status="failed").exists():
            self.status = "failed"
        else:
            self.status = "success"
        self.save()

    def upgrade(self, selected_device_fw_ids, selected_firmwareless_device_ids):
        """Execute the batch upgrade for the explicitly selected devices"""
        self.status = "in-progress"
        self.save()
        self.upgrade_related_devices(selected_device_fw_ids)
        self.upgrade_firmwareless_devices(selected_firmwareless_device_ids)

    @staticmethod
    def dry_run(build):
        """Perform a dry run to see affected devices"""
        related_device_fw = build._find_related_device_modem_firmwares(
            select_devices=True
        )
        firmwareless_devices = build._find_firmwareless_devices()
        return {
            "device_modem_firmwares": related_device_fw,
            "devices": firmwareless_devices,
        }

    def upgrade_related_devices(self, selected_ids):
        """Upgrade only the DeviceModemFirmware entries specified by selected_ids"""
        if not selected_ids:
            return
        device_modem_firmwares = (
            self.build._find_related_device_modem_firmwares()
            .filter(pk__in=selected_ids)
        )
        for device_fw in device_modem_firmwares:
            image = self.build.modemfirmwareimage_set.filter(
                type=device_fw.image.type
            ).first()
            if image:
                device_fw.image = image
                device_fw.full_clean()
                device_fw.save(self, upgrade_options=self.upgrade_options)

    def upgrade_firmwareless_devices(self, selected_ids):
        """Upgrade only the firmwareless devices whose IDs are in selected_ids"""
        if not selected_ids:
            return
        for image in self.build.modemfirmwareimage_set.all():
            devices = self.build._find_firmwareless_devices(image.boards).filter(
                pk__in=selected_ids
            )
            for device in devices:
                DeviceModemFirmware = load_model("DeviceModemFirmware")
                device_fw = DeviceModemFirmware(device=device, image=image)
                device_fw.full_clean()
                device_fw.save(self, upgrade_options=self.upgrade_options)

    @cached_property
    def upgrade_operations(self):
        return self.modemupgradeoperation_set.all()

    @cached_property
    def total_operations(self):
        return self.upgrade_operations.count()

    @property
    def progress_report(self):
        completed = self.upgrade_operations.exclude(status="in-progress").count()
        return _(f"{completed} out of {self.total_operations}")

    @property
    def success_rate(self):
        if not self.total_operations:
            return 0
        success = self.upgrade_operations.filter(status="success").count()
        return self.__get_rate(success)

    @property
    def failed_rate(self):
        if not self.total_operations:
            return 0
        failed = self.upgrade_operations.filter(status="failed").count()
        return self.__get_rate(failed)

    @property
    def aborted_rate(self):
        if not self.total_operations:
            return 0
        aborted = self.upgrade_operations.filter(status="aborted").count()
        return self.__get_rate(aborted)

    @property
    def upgrader_class(self):
        return self._get_upgrader_class()

    @property
    def upgrader_schema(self):
        return self._get_upgrader_schema()

    def _get_upgrader_class(
        self, related_device_fw=None, firmwareless_devices=None
    ):
        if self.upgrade_operations:
            return get_modem_upgrader_class_for_device(
                self.upgrade_operations[0].device
            )
        related_device_fw = (
            related_device_fw
            or self.build._find_related_device_modem_firmwares(select_devices=True)
        )
        if related_device_fw:
            return get_modem_upgrader_class_for_device(related_device_fw.first().device)
        firmwareless_devices = (
            firmwareless_devices or self.build._find_firmwareless_devices()
        )
        if firmwareless_devices:
            return get_modem_upgrader_class_for_device(firmwareless_devices.first())

    def _get_upgrader_schema(
        self, related_device_fw=None, firmwareless_devices=None
    ):
        upgrader_class = self._get_upgrader_class(
            related_device_fw, firmwareless_devices
        )
        return getattr(upgrader_class, "SCHEMA", None)

    def __get_rate(self, number):
        result = Decimal(number) / Decimal(self.total_operations) * 100
        return round(result, 2)


class AbstractModemUpgradeOperation(
    ModemUpgradeOptionsMixin, TimeStampedEditableModel
):
    """Abstract model for individual modem upgrade operations"""

    STATUS_CHOICES = (
        ("in-progress", _("in progress")),
        ("success", _("success")),
        ("failed", _("failed")),
        ("aborted", _("aborted")),
    )
    device = models.ForeignKey(
        swapper.get_model_name("config", "Device"), on_delete=models.CASCADE
    )
    image = models.ForeignKey(
        get_model_name("ModemFirmwareImage"), null=True, on_delete=models.SET_NULL
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0]
    )
    log = models.TextField(blank=True)
    progress_percent = models.IntegerField(
        default=0,
        help_text=_("Download/upgrade progress percentage (0-100)"),
    )
    batch = models.ForeignKey(
        get_model_name("ModemBatchUpgradeOperation"),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True

    def log_line(self, line, save=True):
        """Append a line to the operation log"""
        if self.log:
            self.log += f"\n{line}"
        else:
            self.log = line
        logger.info(f"# {line}")
        if save:
            try:
                self.save()
            except Exception:
                logger.error(
                    f"Failed to save log for ModemUpgradeOperation {self.pk}"
                )

    def update_progress(self, percent, save=True):
        """Update progress percentage"""
        self.progress_percent = max(0, min(100, int(percent)))
        if save:
            self.save()

    def _recoverable_failure_handler(self, recoverable, error):
        """Handle recoverable failures with retry logic"""
        cause = str(error)
        if recoverable:
            self.log_line(f"Detected a recoverable failure: {cause}.\n", save=False)
            self.log_line("The upgrade operation will be retried soon.")
            raise error
        self.status = "failed"
        self.log_line(f"Max retries exceeded. Upgrade failed: {cause}.", save=False)

    def upgrade(self, recoverable=True):
        """Execute the modem upgrade operation"""
        DeviceConnection = swapper.load_model("connection", "DeviceConnection")
        try:
            conn = DeviceConnection.get_working_connection(self.device)
        except NoWorkingDeviceConnectionError as error:
            if error.connection is None:
                self.log_line("No device connection available")
                return

            log_template = (
                "Failed to connect with device using {credentials}. "
                "Error: {failure_reason}"
            )
            for conn in self.device.deviceconnection_set.select_related("credentials"):
                self.log_line(
                    log_template.format(
                        credentials=conn.credentials,
                        failure_reason=conn.failure_reason,
                    ),
                    save=False,
                )
            self._recoverable_failure_handler(
                recoverable,
                RecoverableModemFailure(
                    "Failed to establish connection with the device, "
                    "tried all DeviceConnections"
                ),
            )
            self.save()
            return

        installed = False
        # Prevent multiple upgrade operations for same device
        # Use a staleness threshold to avoid permanently blocking upgrades
        # if a previous operation crashed without updating its status
        stale_threshold = timezone.now() - timedelta(
            seconds=app_settings.TASK_TIMEOUT
        )
        ModemUpgradeOperation = load_model("ModemUpgradeOperation")
        stale_qs = ModemUpgradeOperation.objects.filter(
            device=self.device,
            status="in-progress",
            modified__lt=stale_threshold,
        ).exclude(pk=self.pk)
        if stale_qs.exists():
            logger.warning(
                f"Marking {stale_qs.count()} stale in-progress operations as failed"
            )
            stale_qs.update(status="failed")
        active_qs = ModemUpgradeOperation.objects.filter(
            device=self.device, status="in-progress"
        ).exclude(pk=self.pk)
        if active_qs.exists():
            message = "Another modem upgrade operation is in progress, aborting..."
            logger.warning(message)
            self.log_line(message, save=False)
            self.status = "aborted"
            self.save()
            return

        upgrader_class = get_modem_upgrader_class_from_device_connection(conn)
        if not upgrader_class:
            return

        upgrader = upgrader_class(self, conn)
        try:
            upgrader.upgrade(self.image.file)
        except ModemUpgradeNotNeeded:
            self.status = "success"
            installed = True
        except ModemUpgradeAborted:
            self.status = "aborted"
        except RecoverableModemFailure as e:
            self._recoverable_failure_handler(recoverable, e)
        except (Exception, ModemReconnectionFailed) as e:
            cause = str(e)
            self.log_line(cause)
            self.status = "failed"
            if isinstance(e, ModemReconnectionFailed):
                conn.is_working = False
                conn.failure_reason = cause
                conn.last_attempt = timezone.now()
                conn.save()
                installed = True
        else:
            installed = True
            self.status = "success"

        self.save()
        # Mark as installed if successful
        if installed:
            self.device.devicemodemfirmware.installed = True
            self.device.devicemodemfirmware.save(upgrade=False)

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        # Trigger batch update when operation completes
        if self.batch and self.status != "in-progress":
            self.batch.update()
        return result

    @property
    def upgrader_schema(self):
        return get_modem_upgrader_schema_for_device(self.device)

    @property
    def upgrader_class(self):
        return get_modem_upgrader_class_for_device(self.device)
