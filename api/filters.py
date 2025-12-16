from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from openwisp_users.api.mixins import FilterDjangoByOrgManaged

from ..swapper import load_model

ModemUpgradeOperation = load_model("ModemUpgradeOperation")


class ModemUpgradeOperationFilter(FilterDjangoByOrgManaged):
    device = filters.CharFilter(
        field_name="device",
    )
    image = filters.CharFilter(
        field_name="image",
    )

    def _set_valid_filterform_labels(self):
        self.filters["device__organization"].label = _("Organization")
        self.filters["device__organization__slug"].label = _("Organization slug")

    def __init__(self, *args, **kwargs):
        super(ModemUpgradeOperationFilter, self).__init__(*args, **kwargs)
        self._set_valid_filterform_labels()

    class Meta:
        model = ModemUpgradeOperation
        fields = [
            "device__organization",
            "device__organization__slug",
            "device",
            "image",
            "status",
        ]


class DeviceModemUpgradeOperationFilter(FilterDjangoByOrgManaged):
    class Meta:
        model = ModemUpgradeOperation
        fields = ["status"]
