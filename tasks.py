import logging

import swapper
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from openwisp_utils.tasks import OpenwispCeleryTask

from . import settings as app_settings
from .exceptions import RecoverableModemFailure
from .swapper import load_model

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    soft_time_limit=app_settings.TASK_TIMEOUT,
    **app_settings.RETRY_OPTIONS,
)
def upgrade_modem_firmware(self, operation_id):
    """
    Calls the upgrade() method of a ModemUpgradeOperation instance
    in the background.
    Device-side scripts handle firmware update retry logic.
    """
    try:
        operation = load_model("ModemUpgradeOperation").objects.get(pk=operation_id)
        operation.upgrade(recoverable=False)
    except SoftTimeLimitExceeded:
        operation.status = "failed"
        operation.log_line(_("Operation timed out."))
        logger.warning("SoftTimeLimitExceeded raised in upgrade_modem_firmware task")
    except ObjectDoesNotExist:
        logger.warning(
            f"The ModemUpgradeOperation object with id {operation_id} has been deleted"
        )


@shared_task(bind=True, soft_time_limit=app_settings.TASK_TIMEOUT)
def batch_modem_upgrade_operation(
    self,
    batch_id,
    firmwareless,
    selected_device_fw_ids=None,
    selected_firmwareless_ids=None,
):
    """
    Calls the upgrade() method of a ModemBatchUpgradeOperation instance
    in the background
    """
    try:
        batch_operation = load_model("ModemBatchUpgradeOperation").objects.get(
            pk=batch_id
        )
        batch_operation.upgrade(
            firmwareless=firmwareless,
            selected_device_fw_ids=selected_device_fw_ids,
            selected_firmwareless_ids=selected_firmwareless_ids,
        )
    except SoftTimeLimitExceeded:
        batch_operation.status = "failed"
        batch_operation.save()
        logger.warning(
            "SoftTimeLimitExceeded raised in batch_modem_upgrade_operation task"
        )
    except ObjectDoesNotExist:
        logger.warning(
            f"The ModemBatchUpgradeOperation object with id {batch_id} has been deleted"
        )


@shared_task(base=OpenwispCeleryTask, bind=True)
def create_device_modem_firmware(self, device_id):
    """
    Create a DeviceModemFirmware instance for a device if one doesn't exist
    """
    DeviceModemFirmware = load_model("DeviceModemFirmware")
    Device = swapper.load_model("config", "Device")

    qs = DeviceModemFirmware.objects.filter(device_id=device_id)
    if qs.exists():
        return

    device = Device.objects.get(pk=device_id)
    DeviceModemFirmware.create_for_device(device)


@shared_task(base=OpenwispCeleryTask, bind=True)
def create_all_device_modem_firmwares(self, modem_image_id):
    """
    Create DeviceModemFirmware instances for all compatible devices
    when a new modem firmware image is added
    """
    DeviceModemFirmware = load_model("DeviceModemFirmware")
    ModemFirmwareImage = load_model("ModemFirmwareImage")
    Device = swapper.load_model("config", "Device")

    fw_image = ModemFirmwareImage.objects.select_related("build").get(
        pk=modem_image_id
    )

    # Find devices with matching modem model
    modem_model = fw_image.build.modem_model
    if not modem_model:
        return

    queryset = Device.objects.filter(modem_model=modem_model)
    for device in queryset.iterator():
        DeviceModemFirmware.create_for_device(device, fw_image)


@shared_task(base=OpenwispCeleryTask)
def delete_modem_firmware_files(files_to_delete):
    """
    Celery task to delete modem firmware image files and their parent
    directories if empty.
    
    Args:
        files_to_delete (list[str]): A list of file paths to delete
    """
    ModemFirmwareImage = load_model("ModemFirmwareImage")
    for file_path in files_to_delete:
        ModemFirmwareImage._remove_file(file_path)
