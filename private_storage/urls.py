from django.urls import path

from .views import modem_firmware_image_download

app_name = "modem_upgrader"

urlpatterns = [
    path(
        "modem-firmware/<path:path>",
        modem_firmware_image_download,
        name="modem_serve_private_file",
    ),
]
