import logging

from django.utils.module_loading import import_string

from . import settings as app_settings

logger = logging.getLogger(__name__)


def get_modem_upgrader_schema_for_device(device):
    """Get the upgrade schema for a device's modem upgrader"""
    upgrader_class = get_modem_upgrader_class_for_device(device)
    return getattr(upgrader_class, "SCHEMA", None)


def get_modem_upgrader_class_for_device(device):
    """
    Returns modem upgrader class for a device based on the
    update_strategy of the device's DeviceConnection.
    
    Assumptions:
    - A device cannot have DeviceConnection objects with
      different update_strategy values for modem upgrades.
    - An upgrade cannot be performed without a device connection.
    """
    device_conn = device.deviceconnection_set.filter(
        update_strategy__icontains="ssh",
        enabled=True,
    ).first()
    if not device_conn:
        raise device.deviceconnection_set.model.DoesNotExist
    return get_modem_upgrader_class_from_device_connection(device_conn)


def get_modem_upgrader_class_from_device_connection(device_conn):
    """
    Load modem upgrader class based on device connection's update strategy.
    Returns None if the upgrader cannot be loaded.
    """
    try:
        # For modem upgrades, we use a specific key or fallback to default
        strategy_key = getattr(device_conn, "modem_update_strategy", "telit")
        upgrader_class = app_settings.UPGRADERS_MAP.get(
            strategy_key, app_settings.UPGRADERS_MAP.get("telit")
        )
        upgrader_class = import_string(upgrader_class)
    except (AttributeError, ImportError, KeyError) as e:
        logger.exception(e)
        return
    return upgrader_class
