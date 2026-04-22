# railhead-corporation-openwisp-server

Railhead Corporation OpenWISP Server — includes the standard OpenWISP firmware upgrader and the custom `openwisp_modem_upgrader` module for cellular modem firmware management.

---

## Table of Contents

1. [Overview](#overview)
2. [Adding `openwisp_modem_upgrader` to an Existing OpenWISP Server](#adding-openwisp_modem_upgrader-to-an-existing-openwisp-server)
   - [Prerequisites](#prerequisites)
   - [Step 1: Install the Module](#step-1-install-the-module)
   - [Step 2: settings.py — Add to INSTALLED_APPS](#step-2-settingspy--add-to-installed_apps)
   - [Step 3: urls.py — Add URL Patterns](#step-3-urlspy--add-url-patterns)
   - [Step 4: Celery — Verify Autodiscovery](#step-4-celery--verify-autodiscovery)
   - [Step 5: Run Migrations](#step-5-run-migrations)
   - [Step 6: Collect Static Files](#step-6-collect-static-files)
   - [Step 7: Restart Services](#step-7-restart-services)
   - [Step 8: Verify](#step-8-verify)
   - [Optional Settings](#optional-settings)
   - [Management Command](#management-command)
   - [Supported Hardware](#supported-hardware)

---

## Overview

This repository contains two Django apps for OpenWISP firmware management:

| Module | Purpose |
|---|---|
| `openwisp_firmware_upgrader` | Device/router OS (OpenWrt) upgrades |
| `openwisp_modem_upgrader` | Cellular modem firmware upgrades (Telit FN990AXX and variants) |

Both mirror the same architectural patterns (swappable models, Celery tasks, private storage, REST API) but target different hardware.

---

## Adding `openwisp_modem_upgrader` to an Existing OpenWISP Server

**Module version:** v1.3.0  
**Target hardware:** Telit FN990AXX cellular modems (extensible to other manufacturers)

### Prerequisites

Your existing server must have:

- Python 3.8+, Django 4.x
- OpenWISP Controller (`openwisp_controller`, `openwisp_users`, `openwisp_utils`)
- Redis (Celery broker and Django cache)
- Celery worker + beat services running
- `django-private-storage ~= 3.1.0`
- PostgreSQL + PostGIS (production) or SpatiaLite (development)

Verify your environment before proceeding:

```bash
source /opt/openwisp/venv/bin/activate
python manage.py check
python -c "import openwisp_controller; print('OK')"
```

---

### Step 1: Install the Module

**Option A — Extract zip into site-packages (recommended):**

```bash
# Copy the package to the server
scp openwisp_modem_upgrader-v1.3.0.zip user@your-server:/tmp/

# On the server
ssh user@your-server
source /opt/openwisp/venv/bin/activate
unzip /tmp/openwisp_modem_upgrader-v1.3.0.zip \
  -d /opt/openwisp/venv/lib/python3.x/site-packages/
# Replace python3.x with your actual Python version (e.g., python3.10)
```

**Option B — Place in project root (if project root is on PYTHONPATH):**

```bash
unzip /tmp/openwisp_modem_upgrader-v1.3.0.zip -d /opt/openwisp/
```

Install additional Python dependencies:

```bash
pip install "jsonschema>=4.0.0" "zstandard>=0.22.0"
```

Verify the module is importable:

```bash
python -c "import openwisp_modem_upgrader; print(openwisp_modem_upgrader.__file__)"
```

If this fails, check that extraction went to the correct site-packages directory:

```bash
python -c "import site; print(site.getsitepackages())"
```

---

### Step 2: `settings.py` — Add to INSTALLED_APPS

Add `"openwisp_modem_upgrader"` **after** OpenWISP controller apps and **before** `openwisp_utils.admin_theme`:

```python
INSTALLED_APPS = [
    # ... existing Django apps ...
    "private_storage",                         # already present

    # OpenWISP controller (already present)
    "openwisp_controller.pki",
    "openwisp_controller.config",
    "openwisp_controller.connection",
    "openwisp_controller.geo",

    "openwisp_firmware_upgrader",              # if already installed

    "openwisp_modem_upgrader",                 # ← ADD THIS

    "openwisp_users",
    "openwisp_notifications",
    "openwisp_ipam",
    "openwisp_utils.admin_theme",              # must come after
    # ...
]
```

Ensure `PRIVATE_STORAGE_ROOT` is configured (already required by `openwisp_firmware_upgrader`):

```python
import os
PRIVATE_STORAGE_ROOT = os.path.join(BASE_DIR, "private", "firmware")
```

Create the directory and set permissions:

```bash
mkdir -p /opt/openwisp/private/firmware
chown -R www-data:www-data /opt/openwisp/private/firmware
chmod -R 750 /opt/openwisp/private/firmware
```

---

### Step 3: `urls.py` — Add URL Patterns

Add the modem upgrader URLs to your root URL configuration:

```python
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("openwisp_controller.urls")),
    path("", include("openwisp_firmware_upgrader.urls")),  # if already present
    path("", include("openwisp_modem_upgrader.urls")),     # ← ADD THIS
    # ... rest of your URL patterns ...
]
```

This registers:
- **Admin UI** pages for managing modem firmware categories, builds, images, and upgrade operations
- **REST API** endpoints at `/api/v1/modem/` (enabled by default via `OPENWISP_MODEM_UPGRADER_API=True`)
- **Private storage** download URLs at `/modem-firmware/`

---

### Step 4: Celery — Verify Autodiscovery

Your `celery.py` must call `autodiscover_tasks()` — this should already be the case in a standard OpenWISP setup:

```python
from celery import Celery

app = Celery("openwisp2")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

The module automatically registers the following background tasks:

| Task | Purpose |
|---|---|
| `upgrade_modem_firmware` | Perform a single device modem firmware upgrade |
| `batch_modem_upgrade_operation` | Execute a batch upgrade across multiple devices |
| `create_device_modem_firmware` | Auto-detect and assign modem firmware to a device |
| `create_all_device_modem_firmwares` | Auto-detect modem firmware for all eligible devices |
| `delete_modem_firmware_files` | Clean up firmware files after deletion |

After adding the module, restart Celery services:

```bash
# If using systemd
sudo systemctl restart celery-worker celery-beat

# If running manually
celery -A openwisp2 worker -l info --detach
celery -A openwisp2 beat -l info --detach
```

---

### Step 5: Run Migrations

```bash
source /opt/openwisp/venv/bin/activate
cd /opt/openwisp/
python manage.py migrate modem_upgrader
```

Expected output:

```
Operations to perform:
  Apply all migrations: modem_upgrader
Running migrations:
  Applying modem_upgrader.0001_initial... OK
  Applying modem_upgrader.0002_alter_modemfirmwareimage_file... OK
  Applying modem_upgrader.0003_default_permissions... OK
  Applying modem_upgrader.0004_alter_modemfirmwareimage_type... OK
```

If you see migration dependency errors, ensure all OpenWISP controller migrations are up to date first:

```bash
python manage.py migrate
```

---

### Step 6: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

If admin assets do not appear correctly, force a clean collection:

```bash
python manage.py collectstatic --clear --noinput
```

---

### Step 7: Restart Services

```bash
sudo systemctl restart openwisp celery-worker celery-beat
```

Or if using Supervisor:

```bash
sudo supervisorctl restart openwisp
```

---

### Step 8: Verify

**Django system check:**

```bash
python manage.py check
```

Should complete with no errors (warnings about unused settings are acceptable).

**Verify Celery tasks are registered:**

```bash
celery -A openwisp2 inspect registered | grep modem
```

**Test the REST API:**

```bash
# List modem categories
curl -H "Authorization: Bearer <your-api-token>" \
     https://your-server/api/v1/modem/category/

# List modem builds
curl -H "Authorization: Bearer <your-api-token>" \
     https://your-server/api/v1/modem/build/
```

**Verify admin interface:**

Open `/admin/` in your browser. You should see a new **"Modem Firmware"** menu group containing:

- Modem Categories
- Modem Builds
- Modem Firmware Images
- Device Modem Firmware
- Modem Batch Upgrade Operations
- Modem Upgrade Operations

---

### Optional Settings

All settings below are optional and have sensible defaults. Add them to `settings.py` only if you need to override the defaults.

```python
# Register custom upgrader classes (default: Telit FN990AXX)
OPENWISP_MODEM_UPGRADERS_MAP = {
    "telit": "openwisp_modem_upgrader.upgraders.telit.TelitFN990AXX",
}

# Add custom modem model/board mappings
OPENWISP_CUSTOM_TELIT_IMAGES = (
    ("custom-modem-v1", {
        "label": "Custom Modem Model",
        "boards": ("CustomBoard1", "CustomBoard2"),
    }),
)

# Maximum firmware file upload size in bytes (default: 250 MB)
OPENWISP_MODEM_UPGRADER_MAX_FILE_SIZE = 250 * 1024 * 1024

# Celery task timeout in seconds (default: 2400 = 40 minutes)
# Set high enough to cover: file transfer + modem update + reconnection cycle
OPENWISP_MODEM_UPGRADER_TASK_TIMEOUT = 2400

# Celery retry configuration (default: no retries — device-side scripts handle retries)
OPENWISP_MODEM_UPGRADER_RETRY_OPTIONS = {
    "max_retries": 0,
}

# Disable the REST API entirely (default: True = enabled)
OPENWISP_MODEM_UPGRADER_API = False

# Base URL prefix for API endpoints (default: "/")
OPENWISP_MODEM_API_BASEURL = "/"

# Swap the private storage backend (default: local filesystem)
OPENWISP_MODEM_PRIVATE_STORAGE_INSTANCE = (
    "openwisp_modem_upgrader.private_storage.storage.file_system_private_storage"
)
```

---

### Management Command

The module provides a `cancel_modem_upgrades` management command to cancel in-progress or pending upgrade operations:

```bash
# Cancel all in-progress/pending upgrades
python manage.py cancel_modem_upgrades

# Dry run — preview what would be cancelled without making changes
python manage.py cancel_modem_upgrades --dry-run

# Cancel upgrades for a specific device (by MAC address)
python manage.py cancel_modem_upgrades --mac <device-mac-address>

# Cancel upgrades for a specific batch operation
python manage.py cancel_modem_upgrades --batch <batch-operation-id>
```

---

### Supported Hardware

Out of the box the module supports **Telit FN990AXX** and its variants:

| Board / Model | Notes |
|---|---|
| `Telit FN990AXX` | Primary target hardware |
| `FN990AXX`, `FN990A28` | Telit modem variants |
| `Raspberry Pi 3 Model B Rev 1.2` | RPi 3B with attached Telit modem |
| `Raspberry Pi 3 Model B`, `Raspberry Pi 3B` | RPi 3B variants |
| `Raspberry Pi 4 Model B`, `Raspberry Pi 4B` | RPi 4B with attached Telit modem |

To add support for other modem manufacturers:
1. Implement a custom upgrader class exposing a `SCHEMA` attribute and an `upgrade(firmware_file)` method.
2. Register it via `OPENWISP_MODEM_UPGRADERS_MAP` in `settings.py`.
3. Add board mappings via `OPENWISP_CUSTOM_TELIT_IMAGES`.

---

### Quick Reference — Full Command Summary

```bash
# 1. Copy and extract module
scp openwisp_modem_upgrader-v1.3.0.zip user@server:/tmp/
ssh user@server
source /opt/openwisp/venv/bin/activate
unzip /tmp/openwisp_modem_upgrader-v1.3.0.zip \
  -d /opt/openwisp/venv/lib/python3.x/site-packages/

# 2. Install dependencies
pip install "jsonschema>=4.0.0" "zstandard>=0.22.0"

# 3. Edit settings.py — add "openwisp_modem_upgrader" to INSTALLED_APPS
# 4. Edit urls.py  — add: path("", include("openwisp_modem_upgrader.urls"))

# 5. Run migrations
python manage.py migrate modem_upgrader

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Restart services
sudo systemctl restart openwisp celery-worker celery-beat

# 8. Verify
python manage.py check
celery -A openwisp2 inspect registered | grep modem
```
