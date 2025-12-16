from django import forms


class ModemFirmwareSchemaWidget(forms.Textarea):
    """
    Custom widget for modem firmware upgrade options JSON field.
    Renders as a textarea with schema validation support.
    """

    def __init__(self, attrs=None):
        default_attrs = {
            "class": "vLargeTextField modem-upgrade-options-field",
            "rows": 10,
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    class Media:
        css = {"all": ["modem-upgrader/css/upgrade-options.css"]}
        js = ["modem-upgrader/js/upgrade-options.js"]
