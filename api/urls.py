from django.urls import include, path

from . import views

app_name = "modem_upgrader_api"

urlpatterns = [
    path(
        "modem-upgrader/",
        include(
            [
                path("build/", views.modem_build_list, name="api_modem_build_list"),
                path(
                    "build/<uuid:pk>/",
                    views.modem_build_detail,
                    name="api_modem_build_detail",
                ),
                path(
                    "build/<uuid:pk>/upgrade/",
                    views.api_modem_batch_upgrade,
                    name="api_modem_build_batch_upgrade",
                ),
                path(
                    "build/<uuid:build_pk>/image/",
                    views.modem_firmware_image_list,
                    name="api_modem_firmware_list",
                ),
                path(
                    "build/<uuid:build_pk>/image/<uuid:pk>/",
                    views.modem_firmware_image_detail,
                    name="api_modem_firmware_detail",
                ),
                path(
                    "build/<uuid:build_pk>/image/<pk>/download/",
                    views.modem_firmware_image_download,
                    name="api_modem_firmware_download",
                ),
                path(
                    "category/",
                    views.modem_category_list,
                    name="api_modem_category_list",
                ),
                path(
                    "category/<uuid:pk>/",
                    views.modem_category_detail,
                    name="api_modem_category_detail",
                ),
                path(
                    "batch-upgrade-operation/",
                    views.modem_batch_upgrade_operation_list,
                    name="api_modembatchupgradeoperation_list",
                ),
                path(
                    "batch-upgrade-operation/<uuid:pk>/",
                    views.modem_batch_upgrade_operation_detail,
                    name="api_modembatchupgradeoperation_detail",
                ),
                path(
                    "upgrade-operation/",
                    views.modem_upgrade_operation_list,
                    name="api_modemupgradeoperation_list",
                ),
                path(
                    "upgrade-operation/<uuid:pk>/",
                    views.modem_upgrade_operation_detail,
                    name="api_modemupgradeoperation_detail",
                ),
                path(
                    "device/<uuid:pk>/upgrade-operation/",
                    views.device_modem_upgrade_operation_list,
                    name="api_devicemodemupgradeoperation_list",
                ),
                path(
                    "device/<uuid:pk>/modem-firmware/",
                    views.device_modem_firmware_detail,
                    name="api_devicemodemfirmware_detail",
                ),
            ]
        ),
    ),
]
