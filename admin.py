import json
import logging
from datetime import timedelta

import reversion
import swapper
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.templatetags.static import static
from django.urls import resolve, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from reversion.admin import VersionAdmin

from openwisp_controller.config.admin import DeactivatedDeviceReadOnlyMixin, DeviceAdmin
from openwisp_users.multitenancy import MultitenantAdminMixin, MultitenantOrgFilter
from openwisp_utils.admin import ReadOnlyAdmin, TimeReadonlyAdminMixin

from .swapper import load_model
from .utils import get_modem_upgrader_schema_for_device
from .widgets import ModemFirmwareSchemaWidget

logger = logging.getLogger(__name__)
ModemBatchUpgradeOperation = load_model("ModemBatchUpgradeOperation")
ModemUpgradeOperation = load_model("ModemUpgradeOperation")
DeviceModemFirmware = load_model("DeviceModemFirmware")
ModemFirmwareImage = load_model("ModemFirmwareImage")
ModemCategory = load_model("ModemCategory")
ModemBuild = load_model("ModemBuild")
Device = swapper.load_model("config", "Device")


class BaseAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.ModelAdmin):
    save_on_top = True


class BaseVersionAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, VersionAdmin):
    history_latest_first = True
    save_on_top = True


@admin.register(ModemCategory)
class ModemCategoryAdmin(BaseVersionAdmin):
    list_display = ["name", "organization", "created", "modified"]
    list_filter = [MultitenantOrgFilter]
    list_select_related = ["organization"]
    search_fields = ["name"]
    ordering = ["-name", "-created"]
    change_form_template = "admin/modem_upgrader/modemcategory/change_form.html"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        app_label = self.model._meta.app_label
        extra_context["changelist_url"] = f"{app_label}_modemcategory_changelist"
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(ModemFirmwareImage)
class ModemFirmwareImageAdmin(BaseVersionAdmin):
    list_display = ["file", "build", "created", "modified"]
    list_filter = ["build__category__organization"]
    list_select_related = ["build", "build__category"]
    search_fields = ["build__version", "build__modem_model"]
    ordering = ["-created"]
    multitenant_parent = "build__category"


class ModemFirmwareImageInline(TimeReadonlyAdminMixin, admin.StackedInline):
    model = ModemFirmwareImage
    extra = 0
    min_num = 1
    max_num = 1

    class Media:
        extra = "" if getattr(settings, "DEBUG", False) else ".min"
        i18n_name = admin.widgets.SELECT2_TRANSLATIONS.get(get_language())
        i18n_file = (
            ("admin/js/vendor/select2/i18n/%s.js" % i18n_name,) if i18n_name else ()
        )
        js = (
            (
                "admin/js/vendor/jquery/jquery%s.js" % extra,
                "admin/js/vendor/select2/select2.full%s.js" % extra,
            )
            + i18n_file
            + ("admin/js/jquery.init.js", "modem-upgrader/js/modem-build.js")
        )

        css = {
            "screen": ("admin/css/vendor/select2/select2%s.css" % extra,),
        }

    def has_change_permission(self, request, obj=None):
        if obj:
            return False
        return True


class ModemBatchUpgradeConfirmationForm(forms.ModelForm):
    upgrade_options = forms.JSONField(
        widget=ModemFirmwareSchemaWidget(), required=False
    )
    build = forms.ModelChoiceField(
        widget=forms.HiddenInput(), required=False, queryset=ModemBuild.objects.all()
    )

    class Meta:
        model = ModemBatchUpgradeOperation
        fields = ("build", "upgrade_options")

    @property
    def media(self):
        js = [
            "modem-upgrader/js/upgrade-selected-confirmation.js",
        ]
        css = {"all": ["modem-upgrader/css/upgrade-selected-confirmation.css"]}
        return super().media + forms.Media(js=js, css=css)


@admin.register(ModemBuild)
class ModemBuildAdmin(BaseAdmin):
    list_display = ["__str__", "organization", "category", "modem_model", "created", "modified"]
    list_filter = ["category__organization", "category"]
    list_select_related = ["category", "category__organization"]
    search_fields = ["category__name", "version", "modem_model"]
    ordering = ["-created", "-version"]
    inlines = [ModemFirmwareImageInline]
    actions = ["upgrade_selected"]
    multitenant_parent = "category"
    autocomplete_fields = ["category"]

    change_form_template = "admin/modem_upgrader/change_form.html"

    def organization(self, obj):
        return obj.category.organization

    organization.short_description = _("organization")

    @admin.action(
        description=_("Mass-upgrade device modems related to the selected build"),
        permissions=["change"],
    )
    def upgrade_selected(self, request, queryset):
        opts = self.model._meta
        app_label = opts.app_label
        # multiple concurrent batch upgrades are not supported
        if queryset.count() > 1:
            self.message_user(
                request,
                _(
                    "Multiple mass upgrades requested but at the moment only "
                    "a single mass upgrade operation at time is supported."
                ),
                messages.ERROR,
            )
            return None
        upgrade_selected = request.POST.get("upgrade_selected")
        upgrade_options = request.POST.get("upgrade_options")
        form = ModemBatchUpgradeConfirmationForm()
        build = queryset.first()
        # upgrade has been confirmed
        if upgrade_all or upgrade_related:
            # Collect the device IDs that were checked in the confirmation form.
            # When no checkbox data is present the lists are empty (no devices selected).
            selected_device_fw_ids = request.POST.getlist("selected_related_fw_ids")
            selected_firmwareless_ids = request.POST.getlist(
                "selected_firmwareless_ids"
            )
            form = ModemBatchUpgradeConfirmationForm(
                data={"upgrade_options": upgrade_options, "build": build}
            )
            form.full_clean()
            if not form.errors:
                upgrade_options = form.cleaned_data["upgrade_options"]
                batch = build.batch_upgrade(
                    firmwareless=bool(selected_firmwareless_ids),
                    upgrade_options=upgrade_options,
                    selected_device_fw_ids=selected_device_fw_ids or None,
                    selected_firmwareless_ids=selected_firmwareless_ids or None,
                )
                text = _(
                    "You can track the progress of this modem mass upgrade operation "
                    "in this page. Refresh the page from time to time to check "
                    "its progress."
                )
                self.message_user(request, mark_safe(text), messages.SUCCESS)
                url = reverse(
                    f"admin:{app_label}_modembatchupgradeoperation_change",
                    args=[batch.pk],
                )
                return redirect(url)
        # upgrade needs to be confirmed
        result = ModemBatchUpgradeOperation.dry_run(build=build)
        related_device_fw = result["device_modem_firmwares"]
        firmwareless_devices = result["devices"]
        title = _("Confirm modem mass upgrade operation")
        context = self.admin_site.each_context(request)
        upgrader_schema = ModemBatchUpgradeOperation(build=build)._get_upgrader_schema(
            related_device_fw=related_device_fw,
            firmwareless_devices=firmwareless_devices,
        )

        context.update(
            {
                "title": title,
                "related_device_fw": related_device_fw,
                "related_count": len(related_device_fw),
                "firmwareless_devices": firmwareless_devices,
                "firmwareless_count": len(firmwareless_devices),
                "form": form,
                "modem_upgrader_schema": json.dumps(
                    upgrader_schema, cls=DjangoJSONEncoder
                ),
                "build": build,
                "opts": opts,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "media": self.media,
            }
        )
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            [
                "admin/%s/%s/upgrade_selected_confirmation.html"
                % (app_label, opts.model_name),
                "admin/%s/upgrade_selected_confirmation.html" % app_label,
                "admin/upgrade_selected_confirmation.html",
            ],
            context,
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        app_label = self.model._meta.app_label
        extra_context = extra_context or {}
        upgrade_url = f"{app_label}_modembuild_changelist"
        extra_context.update({"upgrade_url": upgrade_url})
        return super().change_view(request, object_id, form_url, extra_context)


class ModemUpgradeOperationForm(forms.ModelForm):
    class Meta:
        fields = ["device", "image", "status", "log", "progress_percent", "modified"]
        labels = {"modified": _("last updated")}


class ModemUpgradeOperationInline(admin.StackedInline):
    model = ModemUpgradeOperation
    form = ModemUpgradeOperationForm
    readonly_fields = ModemUpgradeOperationForm.Meta.fields
    extra = 0

    def has_delete_permission(self, request, obj):
        return False

    def has_add_permission(self, request, obj):
        return False

    class Media:
        css = {"all": ["modem-upgrader/css/upgrade-options.css"]}


class ReadonlyUpgradeOptionsMixin:
    @admin.display(description=_("Upgrade options"))
    def readonly_upgrade_options(self, obj):
        upgrader_schema = obj.upgrader_schema
        if not upgrader_schema:
            return _("Upgrade options are not supported for this upgrader.")
        options = []
        for key, value in upgrader_schema["properties"].items():
            option_used = "yes" if obj.upgrade_options.get(key, False) else "no"
            option_title = value.get("title", key)
            icon_url = static(f"admin/img/icon-{option_used}.svg")
            options.append(
                f'<li><img src="{icon_url}" alt="{option_used}">{option_title}</li>'
            )
        return format_html(
            mark_safe(f'<ul class="readonly-upgrade-options">{"".join(options)}</ul>')
        )


@admin.register(ModemBatchUpgradeOperation)
class ModemBatchUpgradeOperationAdmin(
    ReadonlyUpgradeOptionsMixin, ReadOnlyAdmin, BaseAdmin
):
    class Media:
        js = ('modem-upgrader/js/batch-operation-refresh.js',)

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm(
            'modem_upgrader.delete_modembatchupgradeoperation'
        )
    
    list_display = ["build", "organization", "status", "created", "modified"]
    list_filter = [
        "build__category__organization",
        "status",
        "build__category",
    ]
    list_select_related = ["build__category__organization"]
    ordering = ["-created"]
    inlines = [ModemUpgradeOperationInline]
    multitenant_parent = "build__category"
    fields = [
        "build",
        "status",
        "created",
        "modified",
    ]
    autocomplete_fields = ["build"]
    readonly_fields = [
        "build",
        "status",
        "completed",
        "success_rate",
        "failed_rate",
        "aborted_rate",
        "readonly_upgrade_options",
        "created",
        "modified",
    ]

    def organization(self, obj):
        return obj.build.category.organization

    organization.short_description = _("organization")

    @admin.display(description=_("Completed"))
    def completed(self, obj):
        return obj.progress_report

    @admin.display(description=_("Success Rate"))
    def success_rate(self, obj):
        return f"{obj.success_rate}%"

    @admin.display(description=_("Failed Rate"))
    def failed_rate(self, obj):
        return f"{obj.failed_rate}%"

    @admin.display(description=_("Aborted Rate"))
    def aborted_rate(self, obj):
        return f"{obj.aborted_rate}%"


@admin.register(ModemUpgradeOperation)
class ModemUpgradeOperationAdmin(
    ReadonlyUpgradeOptionsMixin, ReadOnlyAdmin, BaseAdmin
):
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm(
            'modem_upgrader.delete_modemupgradeoperation'
        )

    list_display = ["device", "image", "status", "progress_percent", "created", "modified"]
    list_filter = ["device__organization", "status"]
    list_select_related = ["device", "image"]
    search_fields = ["device__name", "device__mac_address"]
    ordering = ["-created"]
    multitenant_parent = "device"
    fields = [
        "device",
        "image",
        "status",
        "progress_percent",
        "log",
        "readonly_upgrade_options",
        "created",
        "modified",
    ]
    readonly_fields = [
        "device",
        "image",
        "status",
        "progress_percent",
        "log",
        "readonly_upgrade_options",
        "created",
        "modified",
    ]

    class Media:
        css = {"all": ["modem-upgrader/css/modem-upgrade-operation.css"]}
        js = ["modem-upgrader/js/modem-upgrade-operation.js"]


@admin.register(DeviceModemFirmware)
class DeviceModemFirmwareAdmin(BaseAdmin):
    list_display = ["device", "image", "installed", "created", "modified"]
    list_filter = ["device__organization", "installed"]
    list_select_related = ["device", "image"]
    search_fields = ["device__name", "device__mac_address"]
    ordering = ["-created"]
    multitenant_parent = "device"
    fields = ["device", "image", "installed", "created", "modified"]
    readonly_fields = ["installed", "created", "modified"]
    autocomplete_fields = ["device", "image"]


# ========== Device Admin Inlines ==========


class DeviceModemFirmwareForm(forms.ModelForm):
    upgrade_options = forms.JSONField(widget=ModemFirmwareSchemaWidget, required=False)

    class Meta:
        model = DeviceModemFirmware
        fields = "__all__"

    class Media:
        js = ["admin/js/jquery.init.js", "modem-upgrader/js/device-modem-firmware.js"]
        css = {"all": ["modem-upgrader/css/device-modem-firmware.css"]}

    def __init__(self, device, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].queryset = DeviceModemFirmware.get_image_queryset_for_device(
            device, device_modem_firmware=self.instance
        )

    def full_clean(self):
        super().full_clean()
        if not self.errors and hasattr(self, "cleaned_data"):
            upgrade_op = ModemUpgradeOperation(
                device=self.cleaned_data["device"],
                image=self.cleaned_data["image"],
                upgrade_options=self.cleaned_data["upgrade_options"],
            )
            try:
                upgrade_op.full_clean()
            except forms.ValidationError as error:
                self.add_error("__all__", error.messages[0])

    def save(self, commit=True):
        """
        Adapted from ModelForm.save()
        Passes upgrade_options to DeviceModemFirmware.save()
        """
        if commit:
            self.instance.save(upgrade_options=self.cleaned_data["upgrade_options"])
        return self.instance


class DeviceModemFormSet(forms.BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["device"] = self.instance
        return kwargs


class DeviceModemFirmwareInline(
    MultitenantAdminMixin, DeactivatedDeviceReadOnlyMixin, admin.StackedInline
):
    model = DeviceModemFirmware
    formset = DeviceModemFormSet
    form = DeviceModemFirmwareForm
    exclude = ["created"]
    select_related = ["device", "image"]
    readonly_fields = ["installed", "modified"]
    verbose_name = _("Modem Firmware")
    verbose_name_plural = verbose_name
    extra = 0
    multitenant_shared_relations = ["device"]
    template = "admin/modem_upgrader/device_modem_firmware_inline.html"
    sortable_options = {"disabled": True}

    def _get_conditional_queryset(self, request, obj, select_related=False):
        return bool(obj)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.firmware_installed = False
        if obj:
            try:
                DeviceConnection = swapper.load_model("connection", "DeviceConnection")
                schema = get_modem_upgrader_schema_for_device(obj)
                formset.extra_context = json.dumps(schema, cls=DjangoJSONEncoder)
            except DeviceConnection.DoesNotExist:
                pass
            try:
                device_fw = DeviceModemFirmware.objects.get(device=obj)
                # Show the note whenever a DeviceModemFirmware record exists,
                # so admins know saving without changing the image won't
                # trigger a new upgrade.
                formset.firmware_installed = True
            except DeviceModemFirmware.DoesNotExist:
                pass
        return formset


class DeviceModemUpgradeOperationForm(ModemUpgradeOperationForm):
    class Meta(ModemUpgradeOperationForm.Meta):
        pass

    def __init__(self, device, *args, **kwargs):
        self.device = device
        super().__init__(*args, **kwargs)


class DeviceModemUpgradeOperationInline(ReadonlyUpgradeOptionsMixin, ModemUpgradeOperationInline):
    verbose_name = _("Recent Modem Firmware Upgrades")
    verbose_name_plural = verbose_name
    formset = DeviceModemFormSet
    form = DeviceModemUpgradeOperationForm
    sortable_options = {"disabled": True}
    fields = [
        "device",
        "image",
        "status",
        "progress_percent",
        "log",
        "readonly_upgrade_options",
        "modified",
    ]
    readonly_fields = fields

    def get_queryset(self, request, select_related=True):
        """
        Return recent modem upgrade operations for this device
        (created within the last 7 days)
        """
        qs = super().get_queryset(request)
        resolved = resolve(request.path_info)
        if "object_id" in resolved.kwargs:
            seven_days = localtime() - timedelta(days=7)
            qs = qs.filter(
                device_id=resolved.kwargs["object_id"], created__gte=seven_days
            ).order_by("-created")
        if select_related:
            qs = qs.select_related()
        return qs

    def _get_conditional_queryset(self, request, obj, select_related=False):
        if obj:
            return self.get_queryset(request, select_related=False).exists()
        return False


# Register inlines with DeviceAdmin
DeviceAdmin.conditional_inlines += [DeviceModemFirmwareInline, DeviceModemUpgradeOperationInline]

# Remove "Preview configuration" button from DeviceAdmin
_original_get_extra_context = DeviceAdmin.get_extra_context


def _patched_get_extra_context(self, pk=None):
    ctx = _original_get_extra_context(self, pk)
    ctx.pop("additional_buttons", None)
    ctx.pop("download_url", None)
    return ctx


DeviceAdmin.get_extra_context = _patched_get_extra_context

# Register with reversion for versioning support
reversion.register(model=DeviceModemFirmware, follow=["device"])
reversion.register(model=ModemUpgradeOperation)
DeviceAdmin.add_reversion_following(follow=["devicemodemfirmware", "modemupgradeoperation_set"])

