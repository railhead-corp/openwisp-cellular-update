from swapper import swappable_setting

from .base.models import (
    AbstractDeviceModemFirmware,
    AbstractModemBatchUpgradeOperation,
    AbstractModemBuild,
    AbstractModemCategory,
    AbstractModemFirmwareImage,
    AbstractModemUpgradeOperation,
)


class ModemCategory(AbstractModemCategory):
    class Meta(AbstractModemCategory.Meta):
        abstract = False
        swappable = swappable_setting("modem_upgrader", "ModemCategory")


class ModemBuild(AbstractModemBuild):
    class Meta(AbstractModemBuild.Meta):
        abstract = False
        swappable = swappable_setting("modem_upgrader", "ModemBuild")


class ModemFirmwareImage(AbstractModemFirmwareImage):
    class Meta(AbstractModemFirmwareImage.Meta):
        abstract = False
        swappable = swappable_setting("modem_upgrader", "ModemFirmwareImage")


class DeviceModemFirmware(AbstractDeviceModemFirmware):
    class Meta(AbstractDeviceModemFirmware.Meta):
        abstract = False
        swappable = swappable_setting("modem_upgrader", "DeviceModemFirmware")


class ModemBatchUpgradeOperation(AbstractModemBatchUpgradeOperation):
    class Meta(AbstractModemBatchUpgradeOperation.Meta):
        abstract = False
        swappable = swappable_setting("modem_upgrader", "ModemBatchUpgradeOperation")


class ModemUpgradeOperation(AbstractModemUpgradeOperation):
    class Meta(AbstractModemUpgradeOperation.Meta):
        abstract = False
        swappable = swappable_setting("modem_upgrader", "ModemUpgradeOperation")
