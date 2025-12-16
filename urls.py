from django.urls import include, path

app_name = "modem_upgrader"

urlpatterns = [
    # Private storage URLs for modem firmware downloads
    path("", include("openwisp_modem_upgrader.private_storage.urls")),
]

# Conditionally include API URLs
from . import settings as app_settings

if app_settings.MODEM_UPGRADER_API:
    urlpatterns.append(
        path("", include("openwisp_modem_upgrader.api.urls")),
    )
