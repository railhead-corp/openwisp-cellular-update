from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ModemUpgraderConfig(AppConfig):
    name = "openwisp_modem_upgrader"
    label = "modem_upgrader"
    verbose_name = _("Modem Upgrader")

    def ready(self):
        super().ready()
        self.register_menu_groups()
        self.register_signals()

    def register_menu_groups(self):
        """Register menu groups for admin interface"""
        from openwisp_utils.admin_theme.menu import register_menu_group

        register_menu_group(
            position=70,
            config={
                "label": "Modem Firmware",
                "items": {
                    1: {
                        "label": _("Modem Builds"),
                        "model": f"{self.label}.ModemBuild",
                        "name": "changelist",
                        "icon": "ow-modem-build",
                    },
                    2: {
                        "label": _("Modem Categories"),
                        "model": f"{self.label}.ModemCategory",
                        "name": "changelist",
                        "icon": "ow-category",
                    },
                    3: {
                        "label": _("Modem Batch Upgrades"),
                        "model": f"{self.label}.ModemBatchUpgradeOperation",
                        "name": "changelist",
                        "icon": "ow-batch-upgrade",
                    },
                },
                "icon": "ow-modem-firmware",
            },
        )

    def register_signals(self):
        """Register signal handlers"""
        from django.db.models.signals import post_save, pre_delete

        from .swapper import load_model

        ModemFirmwareImage = load_model("ModemFirmwareImage")
        ModemBuild = load_model("ModemBuild")
        ModemCategory = load_model("ModemCategory")
        DeviceModemFirmware = load_model("DeviceModemFirmware")

        # Register firmware image deletion handlers
        pre_delete.connect(
            ModemFirmwareImage.build_pre_delete_handler,
            sender=ModemBuild,
            dispatch_uid="modem_build_pre_delete",
        )
        pre_delete.connect(
            ModemFirmwareImage.category_pre_delete_handler,
            sender=ModemCategory,
            dispatch_uid="modem_category_pre_delete",
        )

        # Auto-create device modem firmware on device creation
        post_save.connect(
            DeviceModemFirmware.auto_add_device_modem_firmware_to_device,
            sender=load_model("DeviceModemFirmware").device.field.related_model,
            dispatch_uid="auto_devicemodemfirmware",
        )

        # Auto-create device firmwares when new modem image is added
        post_save.connect(
            DeviceModemFirmware.auto_create_device_modem_firmwares,
            sender=ModemFirmwareImage,
            dispatch_uid="auto_create_device_modem_firmwares",
        )
