from django.db import migrations

from . import create_permissions_for_default_groups


def create_permissions_for_default_groups_helper(apps, schema_editor):
    app_label = "modem_upgrader"
    create_permissions_for_default_groups(apps, schema_editor, app_label)


class Migration(migrations.Migration):
    dependencies = [
        ("modem_upgrader", "0002_alter_modemfirmwareimage_file"),
    ]

    operations = [
        migrations.RunPython(
            create_permissions_for_default_groups_helper,
            reverse_code=migrations.RunPython.noop,
        )
    ]
