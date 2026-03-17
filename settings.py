from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

# Custom Telit modem images mapping
CUSTOM_TELIT_IMAGES = getattr(settings, "OPENWISP_CUSTOM_TELIT_IMAGES", None)

# Modem upgraders map
UPGRADERS_MAP = getattr(
    settings,
    "OPENWISP_MODEM_UPGRADERS_MAP",
    {
        "telit": "openwisp_modem_upgrader.upgraders.telit.TelitFN990AXX",
    },
)

# Max modem firmware file size (250 MB default)
MAX_FILE_SIZE = getattr(
    settings, "OPENWISP_MODEM_UPGRADER_MAX_FILE_SIZE", 250 * 1024 * 1024
)

# Celery retry options for modem upgrades
# Device-side scripts handle retry logic, so OpenWISP does not retry.
RETRY_OPTIONS = getattr(
    settings,
    "OPENWISP_MODEM_UPGRADER_RETRY_OPTIONS",
    dict(max_retries=0),
)

# Task timeout (40 minutes default: transfer + update + reconnection cycle)
TASK_TIMEOUT = getattr(settings, "OPENWISP_MODEM_UPGRADER_TASK_TIMEOUT", 2400)

# API enabled flag
MODEM_UPGRADER_API = getattr(settings, "OPENWISP_MODEM_UPGRADER_API", True)

# API base URL
MODEM_API_BASEURL = getattr(settings, "OPENWISP_MODEM_API_BASEURL", "/")

# Modem upgrader specific settings (e.g., Telit tool paths)
MODEM_UPGRADER_SETTINGS = getattr(settings, "OPENWISP_MODEM_UPGRADER_SETTINGS", {})

# Path for modem firmware URLs
MODEM_IMAGE_URL_PATH = "modem-firmware/"

# Private storage instance for modem firmware
try:
    PRIVATE_STORAGE_INSTANCE = import_string(
        getattr(
            settings,
            "OPENWISP_MODEM_PRIVATE_STORAGE_INSTANCE",
            "openwisp_modem_upgrader.private_storage.storage.file_system_private_storage",
        )
    )
except ImportError:
    raise ImproperlyConfigured(
        "Failed to import OPENWISP_MODEM_PRIVATE_STORAGE_INSTANCE"
    )
