default_app_config = "openwisp_modem_upgrader.apps.ModemUpgraderConfig"

VERSION = (0, 1, 0, "alpha")
__version__ = VERSION  # alias


def get_version():
    """Return the OpenWISP Modem Upgrader version."""
    return ".".join(map(str, VERSION))
