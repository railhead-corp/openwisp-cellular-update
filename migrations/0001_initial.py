import uuid

import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import swapper
from django.conf import settings
from django.db import migrations, models
from swapper import dependency, split

import openwisp_users.mixins

from ..hardware import MODEM_IMAGE_TYPE_CHOICES
from ..swapper import get_model_name


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("config", "0015_default_groups_permissions"),
        dependency(*split(settings.AUTH_USER_MODEL), version="0004_default_groups"),
        swapper.dependency("modem_upgrader", "ModemCategory"),
        swapper.dependency("modem_upgrader", "ModemBuild"),
        swapper.dependency("modem_upgrader", "ModemFirmwareImage"),
        swapper.dependency("modem_upgrader", "DeviceModemFirmware"),
        swapper.dependency("modem_upgrader", "ModemBatchUpgradeOperation"),
        swapper.dependency("modem_upgrader", "ModemUpgradeOperation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModemBatchUpgradeOperation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "upgrade_options",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("idle", "idle"),
                            ("in-progress", "in progress"),
                            ("success", "completed successfully"),
                            ("failed", "completed with some failures"),
                        ],
                        default="idle",
                        max_length=12,
                    ),
                ),
            ],
            options={
                "swappable": swapper.swappable_setting(
                    "modem_upgrader", "ModemBatchUpgradeOperation"
                ),
                "verbose_name_plural": "Modem Mass Upgrade Operations",
                "verbose_name": "Modem Mass Upgrade Operation",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ModemBuild",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                ("version", models.CharField(db_index=True, max_length=32)),
                (
                    "modem_model",
                    models.CharField(
                        blank=True,
                        help_text="Modem model identifier (e.g., FN990AXX) used to automatically recognize compatible devices",
                        max_length=64,
                        null=True,
                        verbose_name="Modem model identifier",
                    ),
                ),
                (
                    "changelog",
                    models.TextField(
                        blank=True,
                        help_text="Descriptive text indicating what has changed since the previous version",
                        verbose_name="change log",
                    ),
                ),
            ],
            options={
                "swappable": swapper.swappable_setting("modem_upgrader", "ModemBuild"),
                "ordering": ("-created",),
                "verbose_name": "Modem Build",
                "verbose_name_plural": "Modem Builds",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ModemCategory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                ("name", models.CharField(db_index=True, max_length=64)),
                ("description", models.TextField(blank=True)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name("openwisp_users", "Organization"),
                        verbose_name="organization",
                    ),
                ),
            ],
            options={
                "swappable": swapper.swappable_setting("modem_upgrader", "ModemCategory"),
                "verbose_name": "Modem Category",
                "verbose_name_plural": "Modem Categories",
                "abstract": False,
            },
            bases=(openwisp_users.mixins.ValidateOrgMixin, models.Model),
        ),
        migrations.CreateModel(
            name="DeviceModemFirmware",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                ("installed", models.BooleanField(default=False)),
                (
                    "device",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name("config", "Device"),
                    ),
                ),
            ],
            options={
                "swappable": swapper.swappable_setting(
                    "modem_upgrader", "DeviceModemFirmware"
                ),
                "abstract": False,
                "verbose_name": "Device Modem Firmware",
            },
        ),
        migrations.CreateModel(
            name="ModemFirmwareImage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                ("file", models.FileField(upload_to="", max_length=255)),
                (
                    "type",
                    models.CharField(
                        blank=True,
                        choices=MODEM_IMAGE_TYPE_CHOICES,
                        help_text="Modem firmware image type: model or manufacturer. Leave blank to attempt automatic detection",
                        max_length=128,
                    ),
                ),
                (
                    "build",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=get_model_name("ModemBuild"),
                    ),
                ),
            ],
            options={
                "swappable": swapper.swappable_setting(
                    "modem_upgrader", "ModemFirmwareImage"
                ),
                "abstract": False,
                "verbose_name": "Modem Firmware Image",
                "verbose_name_plural": "Modem Firmware Images",
            },
        ),
        migrations.CreateModel(
            name="ModemUpgradeOperation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "upgrade_options",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in-progress", "in progress"),
                            ("success", "success"),
                            ("failed", "failed"),
                            ("aborted", "aborted"),
                        ],
                        default="in-progress",
                        max_length=12,
                    ),
                ),
                ("log", models.TextField(blank=True)),
                (
                    "progress_percent",
                    models.IntegerField(
                        default=0,
                        help_text="Download/upgrade progress percentage (0-100)",
                    ),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=get_model_name("ModemBatchUpgradeOperation"),
                    ),
                ),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name("config", "Device"),
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=get_model_name("ModemFirmwareImage"),
                    ),
                ),
            ],
            options={
                "swappable": swapper.swappable_setting(
                    "modem_upgrader", "ModemUpgradeOperation"
                ),
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="devicemodemfirmware",
            name="image",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name("ModemFirmwareImage"),
            ),
        ),
        migrations.AddField(
            model_name="modembuild",
            name="category",
            field=models.ForeignKey(
                help_text="Group modem firmware by manufacturer, model series, or deployment scenario",
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name("ModemCategory"),
                verbose_name="modem category",
            ),
        ),
        migrations.AddField(
            model_name="modembatchupgradeoperation",
            name="build",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=get_model_name("ModemBuild"),
            ),
        ),
        migrations.AlterUniqueTogether(
            name="modemfirmwareimage",
            unique_together={("build", "type")},
        ),
        migrations.AlterUniqueTogether(
            name="modemcategory",
            unique_together={("name", "organization")},
        ),
        migrations.AlterUniqueTogether(
            name="modembuild",
            unique_together={("category", "version")},
        ),
    ]
