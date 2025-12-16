import swapper
from django.core.exceptions import ValidationError
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, pagination, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict

from openwisp_modem_upgrader import private_storage
from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import DjangoModelPermissions

from ..swapper import load_model
from .filters import DeviceModemUpgradeOperationFilter, ModemUpgradeOperationFilter
from .serializers import (
    DeviceModemFirmwareSerializer,
    DeviceModemUpgradeOperationSerializer,
    ModemBatchUpgradeOperationListSerializer,
    ModemBatchUpgradeOperationSerializer,
    ModemBuildSerializer,
    ModemCategorySerializer,
    ModemFirmwareImageSerializer,
    ModemUpgradeOperationSerializer,
)

ModemBatchUpgradeOperation = load_model("ModemBatchUpgradeOperation")
ModemUpgradeOperation = load_model("ModemUpgradeOperation")
ModemBuild = load_model("ModemBuild")
ModemCategory = load_model("ModemCategory")
ModemFirmwareImage = load_model("ModemFirmwareImage")
DeviceModemFirmware = load_model("DeviceModemFirmware")
Device = swapper.load_model("config", "Device")


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProtectedAPIMixin(BaseProtectedAPIMixin, FilterByOrganizationManaged):
    throttle_scope = "modem_upgrader"
    pagination_class = ListViewPagination

    def get_queryset(self):
        qs = super().get_queryset()
        org_filtered = self.request.query_params.get("organization", None)
        try:
            if org_filtered:
                organization_filter = {self.organization_field + "__slug": org_filtered}
                qs = qs.filter(**organization_filter)
        except ValidationError:
            # when uuid is not valid
            qs = []
        return qs


class ModemBuildListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    queryset = ModemBuild.objects.all().select_related("category")
    serializer_class = ModemBuildSerializer
    organization_field = "category__organization"
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["category", "version", "modem_model"]
    ordering_fields = ["version", "created", "modified"]
    ordering = ["-created", "-version"]


class ModemBuildDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ModemBuild.objects.all().select_related("category")
    serializer_class = ModemBuildSerializer
    lookup_fields = ["pk"]
    organization_field = "category__organization"


class ModemBuildBatchUpgradeView(ProtectedAPIMixin, generics.GenericAPIView):
    model = ModemBuild
    queryset = ModemBuild.objects.all().select_related("category")
    serializer_class = serializers.Serializer
    lookup_fields = ["pk"]
    organization_field = "category__organization"

    def post(self, request, pk):
        """
        Upgrades all the devices' modems related to the specified build ID.
        """
        upgrade_all = request.POST.get("upgrade_all") is not None
        instance = self.get_object()
        batch = instance.batch_upgrade(firmwareless=upgrade_all)
        return Response({"batch": str(batch.pk)}, status=201)

    def get(self, request, pk):
        """
        Returns a list of objects (DeviceModemFirmware and Device)
        which would be upgraded if POST is used.
        """
        self.instance = self.get_object()
        data = ModemBatchUpgradeOperation.dry_run(build=self.instance)
        data["device_modem_firmwares"] = [
            str(device_fw.pk) for device_fw in data["device_modem_firmwares"]
        ]
        data["devices"] = [str(device.pk) for device in data["devices"]]
        return Response(data)


class ModemCategoryListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    queryset = ModemCategory.objects.all()
    serializer_class = ModemCategorySerializer
    organization_field = "organization"
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created", "modified"]
    ordering = ["-name", "-created"]


class ModemCategoryDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ModemCategory.objects.all()
    serializer_class = ModemCategorySerializer
    lookup_fields = ["pk"]
    organization_field = "organization"


class ModemBatchUpgradeOperationListView(ProtectedAPIMixin, generics.ListAPIView):
    queryset = ModemBatchUpgradeOperation.objects.all().select_related(
        "build", "build__category"
    )
    serializer_class = ModemBatchUpgradeOperationListSerializer
    organization_field = "build__category__organization"
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["build", "status"]
    ordering_fields = ["created", "modified"]
    ordering = ["-created"]


class ModemBatchUpgradeOperationDetailView(ProtectedAPIMixin, generics.RetrieveAPIView):
    queryset = (
        ModemBatchUpgradeOperation.objects.all()
        .select_related("build", "build__category")
        .prefetch_related("modemupgradeoperation_set")
    )
    serializer_class = ModemBatchUpgradeOperationSerializer
    lookup_fields = ["pk"]
    organization_field = "build__category__organization"


class ModemFirmwareImageMixin(ProtectedAPIMixin):
    queryset = ModemFirmwareImage.objects.all()
    parent = None

    def get_parent_queryset(self):
        return ModemBuild.objects.filter(pk=self.kwargs["build_pk"])

    def assert_parent_exists(self):
        try:
            assert self.get_parent_queryset().exists()
        except (AssertionError, ValidationError):
            raise NotFound(detail="modem build not found")

    def get_queryset(self):
        return super().get_queryset().filter(build=self.kwargs["build_pk"])

    def initial(self, *args, **kwargs):
        self.assert_parent_exists()
        super().initial(*args, **kwargs)


class ModemFirmwareImageListView(ModemFirmwareImageMixin, generics.ListCreateAPIView):
    serializer_class = ModemFirmwareImageSerializer
    organization_field = "build__category__organization"
    ordering_fields = ["type", "created", "modified"]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["type"]
    ordering_fields = ["type", "created", "modified"]
    ordering = ["-created"]


class ModemFirmwareImageDetailView(
    ModemFirmwareImageMixin, generics.RetrieveDestroyAPIView
):
    queryset = ModemFirmwareImage.objects.all()
    serializer_class = ModemFirmwareImageSerializer
    lookup_fields = ["pk"]
    organization_field = "build__category__organization"


class ModemFirmwareImageDownloadView(
    ModemFirmwareImageMixin, generics.RetrieveAPIView
):
    serializer_class = ModemFirmwareImageSerializer
    lookup_fields = ["pk"]
    organization_field = "build__category__organization"
    queryset = ModemFirmwareImage.objects.none()
    permission_classes = [DjangoModelPermissions]

    def retrieve(self, request, *args, **kwargs):
        return private_storage.views.modem_firmware_image_download(
            request, build_pk=kwargs["build_pk"], pk=kwargs["pk"]
        )


class DeviceModemUpgradeOperationMixin(ProtectedAPIMixin):
    queryset = ModemUpgradeOperation.objects.all()
    parent = None

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs["pk"])

    def assert_parent_exists(self):
        try:
            assert self.get_parent_queryset().exists()
        except (AssertionError, ValidationError):
            raise NotFound(detail="device not found")

    def get_queryset(self):
        return super().get_queryset().filter(device=self.kwargs["pk"])

    def initial(self, *args, **kwargs):
        self.assert_parent_exists()
        super().initial(*args, **kwargs)


class ModemUpgradeOperationListView(ProtectedAPIMixin, generics.ListAPIView):
    queryset = ModemUpgradeOperation.objects.select_related("device", "image")
    serializer_class = ModemUpgradeOperationSerializer
    organization_field = "device__organization"
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = ["device_id", "created", "modified"]
    ordering = ["-created"]
    filterset_class = ModemUpgradeOperationFilter


class ModemUpgradeOperationDetailView(ProtectedAPIMixin, generics.RetrieveAPIView):
    queryset = ModemUpgradeOperation.objects.select_related("device", "image").order_by(
        "-created"
    )
    serializer_class = ModemUpgradeOperationSerializer
    lookup_fields = ["pk"]
    organization_field = "device__organization"


class DeviceModemUpgradeOperationListView(
    DeviceModemUpgradeOperationMixin, generics.ListAPIView
):
    queryset = ModemUpgradeOperation.objects.select_related("device", "image").order_by(
        "-created"
    )
    serializer_class = DeviceModemUpgradeOperationSerializer
    organization_field = "device__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeviceModemUpgradeOperationFilter

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(device__pk=self.kwargs["pk"])


class DeviceModemFirmwareDetailView(
    ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = DeviceModemFirmwareSerializer
    queryset = DeviceModemFirmware.objects.select_related("device", "image")
    lookup_field = "device"
    lookup_url_kwarg = "pk"
    organization_field = "device__organization"

    def get_object(self):
        obj = super().get_object()
        if self.request.method not in ("GET", "HEAD") and obj.device.is_deactivated():
            raise PermissionDenied
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"device_id": self.kwargs["pk"]})
        return context

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if kwargs.get("instance"):
            image_qs = self._get_image_queryset(
                kwargs.get("instance"), kwargs.get("instance").device
            )
            serializer.fields["image"].queryset = image_qs
        else:
            device = self._get_device_object(serializer.context.get("device_id"))
            image_qs = self._get_image_queryset(device=device)
            serializer.fields["image"].queryset = image_qs
        return serializer

    def _get_device_object(self, device_id):
        try:
            device = Device.objects.get(id=device_id)
            return device
        except Device.DoesNotExist:
            return None

    def _get_image_queryset(self, device_modem_firmware=None, device=None):
        if not device_modem_firmware and not device:
            return
        return DeviceModemFirmware.get_image_queryset_for_device(
            device, device_modem_firmware
        )

    def _get_response_data(self, serializer, upgrade_operation=None):
        data = {**serializer.data}
        if upgrade_operation:
            data.update({"upgrade_operation": {"id": upgrade_operation.id}})
        return ReturnDict(data, serializer=serializer)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object_or_none()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if instance is None:
            self.perform_create(serializer)
            instance = self.get_object_or_none()
            uo = instance.device.modemupgradeoperation_set.latest("created")
            data = self._get_response_data(serializer, uo)
            image_qs = self._get_image_queryset(uo, instance.device)
            serializer.fields["image"].queryset = image_qs
            return Response(data, status=status.HTTP_201_CREATED)

        self.perform_update(serializer)
        uo = instance.device.modemupgradeoperation_set.latest("created")
        data = self._get_response_data(serializer, uo)
        image_qs = self._get_image_queryset(uo, instance.device)
        serializer.fields["image"].queryset = image_qs
        return Response(data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def get_object_or_none(self):
        try:
            return self.get_object()
        except Http404:
            if self.request.method == "PUT":
                # For PUT-as-create operation, we need to ensure that we have
                # relevant permissions, as if this was a POST request. This
                # will either raise a PermissionDenied exception, or simply
                # return None.
                self.check_permissions(clone_request(self.request, "POST"))
            else:
                # PATCH requests where the object does not exist should still
                # return a 404 response.
                raise


# Export view functions
modem_build_list = ModemBuildListView.as_view()
modem_build_detail = ModemBuildDetailView.as_view()
api_modem_batch_upgrade = ModemBuildBatchUpgradeView.as_view()
modem_category_list = ModemCategoryListView.as_view()
modem_category_detail = ModemCategoryDetailView.as_view()
modem_batch_upgrade_operation_list = ModemBatchUpgradeOperationListView.as_view()
modem_batch_upgrade_operation_detail = ModemBatchUpgradeOperationDetailView.as_view()
modem_firmware_image_list = ModemFirmwareImageListView.as_view()
modem_firmware_image_detail = ModemFirmwareImageDetailView.as_view()
modem_firmware_image_download = ModemFirmwareImageDownloadView.as_view()
modem_upgrade_operation_list = ModemUpgradeOperationListView.as_view()
modem_upgrade_operation_detail = ModemUpgradeOperationDetailView.as_view()
device_modem_upgrade_operation_list = DeviceModemUpgradeOperationListView.as_view()
device_modem_firmware_detail = DeviceModemFirmwareDetailView.as_view()
