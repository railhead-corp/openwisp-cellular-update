import swapper
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

from ..swapper import load_model

ModemBatchUpgradeOperation = load_model("ModemBatchUpgradeOperation")
ModemBuild = load_model("ModemBuild")
ModemCategory = load_model("ModemCategory")
ModemFirmwareImage = load_model("ModemFirmwareImage")
ModemUpgradeOperation = load_model("ModemUpgradeOperation")
DeviceModemFirmware = load_model("DeviceModemFirmware")
Device = swapper.load_model("config", "Device")


class BaseMeta:
    read_only_fields = ["created", "modified"]


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    pass


class ModemCategorySerializer(BaseSerializer):
    def validate_organization(self, value):
        if not value and not self.context.get("request").user.is_superuser:
            raise serializers.ValidationError(
                _("Only superusers can create or edit shared modem categories")
            )
        return value

    class Meta(BaseMeta):
        model = ModemCategory
        fields = "__all__"


class ModemCategoryRelationSerializer(BaseSerializer):
    class Meta:
        model = ModemCategory
        fields = ["name", "organization"]


class ModemFirmwareImageSerializer(BaseSerializer):
    def validate_file(self, value):
        if value and not value.name.lower().endswith('.bin'):
            raise serializers.ValidationError(
                _("Only .bin firmware files are allowed.")
            )
        return value

    def validate(self, data):
        data["build"] = self.context["view"].get_parent_queryset().get()
        return super().validate(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get("request")
        if request and getattr(instance, "pk", None):
            ret["file"] = request.build_absolute_uri(
                reverse(
                    "modem_upgrader:api_modem_firmware_download",
                    args=[instance.build.pk, instance.pk],
                )
            )
        elif hasattr(instance, "file"):
            ret["file"] = reverse(
                "modem_upgrader:api_modem_firmware_download",
                args=[instance.build.pk, instance.pk],
            )
        return ret

    class Meta(BaseMeta):
        model = ModemFirmwareImage
        fields = "__all__"
        read_only_fields = BaseMeta.read_only_fields + ["build"]


class ModemBuildSerializer(BaseSerializer):
    category_relation = ModemCategoryRelationSerializer(
        read_only=True, source="category"
    )

    class Meta(BaseMeta):
        model = ModemBuild
        fields = "__all__"


class ModemUpgradeOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModemUpgradeOperation
        fields = (
            "id",
            "device",
            "image",
            "status",
            "log",
            "progress_percent",
            "modified",
            "created",
        )


class DeviceModemUpgradeOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModemUpgradeOperation
        fields = (
            "id",
            "device",
            "image",
            "status",
            "log",
            "progress_percent",
            "modified",
        )


class ModemBatchUpgradeOperationListSerializer(BaseSerializer):
    build = ModemBuildSerializer(read_only=True)

    class Meta:
        model = ModemBatchUpgradeOperation
        fields = "__all__"


class ModemBatchUpgradeOperationSerializer(ModemBatchUpgradeOperationListSerializer):
    progress_report = serializers.CharField(max_length=200)
    success_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    failed_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    aborted_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    modemupgradeoperations = ModemUpgradeOperationSerializer(
        read_only=True, source="modemupgradeoperation_set", many=True
    )

    class Meta:
        model = ModemBatchUpgradeOperation
        fields = "__all__"


class DeviceModemFirmwareSerializer(ValidatedModelSerializer):
    class Meta:
        model = DeviceModemFirmware
        fields = ("id", "image", "installed", "modified")
        read_only_fields = ("installed", "modified")

    def validate(self, data):
        if not data.get("device"):
            device_id = self.context.get("device_id")
            device = self._get_device_object(device_id)
            data.update({"device": device})
        image = data.get("image")
        device = data.get("device")
        if (
            image
            and device
            and image.build.category.organization is not None
            and image.build.category.organization != device.organization
        ):
            raise ValidationError(
                {
                    "image": _(
                        "The organization of the image doesn't "
                        "match the organization of the device"
                    )
                }
            )
        return super().validate(data)

    def _get_device_object(self, device_id):
        try:
            device = Device.objects.get(id=device_id)
            return device
        except Device.DoesNotExist:
            return None
