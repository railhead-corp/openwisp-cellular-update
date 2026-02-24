"""
Mapping between modem models and firmware image types.
Initially focused on Telit modems, with extensibility for other manufacturers.
"""

from collections import OrderedDict

from . import settings as app_settings

# Initialize with custom images if provided
if app_settings.CUSTOM_TELIT_IMAGES:
    TELIT_MODEM_IMAGE_MAP = OrderedDict(app_settings.CUSTOM_TELIT_IMAGES)
else:
    TELIT_MODEM_IMAGE_MAP = OrderedDict()

# Telit FN990AXX modem mappings
TELIT_MODEM_IMAGE_MAP.update(
    OrderedDict(
        (
            (
                "telit-fn990axx-v1",
                {
                    "label": "Telit FN990AXX",
                    "boards": (
                        "Telit FN990AXX",
                        "FN990AXX",
                        "FN990A28",  # Telit FN990A28 modem variant
                        "Default string Default string",  # Default device model
                        "Raspberry Pi 3 Model B Rev 1.2",  # Raspberry Pi 3B with Telit modem
                        "Raspberry Pi 3 Model B",
                        "Raspberry Pi 3B",
                        "Raspberry Pi 4 Model B",
                        "Raspberry Pi 4B",
                    ),
                },
            ),
        )
    )
)

# Main modem image map (can be extended for other manufacturers)
MODEM_IMAGE_MAP = TELIT_MODEM_IMAGE_MAP.copy()

# Generate choices for Django model field
MODEM_IMAGE_TYPE_CHOICES = tuple(
    (k, MODEM_IMAGE_MAP[k]["label"]) for k in MODEM_IMAGE_MAP.keys()
)

# Reverse mapping: device model -> image type
REVERSE_MODEM_IMAGE_MAP = {}
for image_type, data in MODEM_IMAGE_MAP.items():
    for board in data["boards"]:
        REVERSE_MODEM_IMAGE_MAP[board] = image_type
