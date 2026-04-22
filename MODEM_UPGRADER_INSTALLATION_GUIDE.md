# OpenWISP Modem Upgrader — Installation Guide

**Version:** v1.2.0  
**Module:** `openwisp_modem_upgrader`  
**Target Hardware:** Telit FN990AXX cellular modems (extensible to other manufacturers)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation Steps](#2-installation-steps)
3. [Django Configuration](#3-django-configuration)
4. [URL Configuration](#4-url-configuration)
5. [Celery Configuration](#5-celery-configuration)
6. [Database Migration](#6-database-migration)
7. [Static Files](#7-static-files)
8. [Verification](#8-verification)
9. [Optional Settings](#9-optional-settings)
10. [Management Commands](#10-management-commands)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

Before installing the modem upgrader module, ensure you have a working OpenWISP server with the following components already installed and running:

- **Python** 3.8+
- **Django** 4.x
- **OpenWISP Controller** (branch 1.3+) — includes `openwisp-controller`, `openwisp-users`, `openwisp-utils`
- **Redis** — for Celery broker and Django caching
- **Celery** — worker and beat services running
- **django-private-storage** ~= 3.1.0
- **PostgreSQL** with PostGIS (recommended for production) or SpatiaLite (development only)

### Verify existing OpenWISP installation

```bash
# Ensure your virtual environment is activated
source /opt/openwisp/venv/bin/activate  # adjust path as needed

# Verify Django is working
python manage.py check

# Verify OpenWISP controller is installed
python -c "import openwisp_controller; print('OK')"
```

---

## 2. Installation Steps

### Step 1: Extract the module

Copy the `openwisp_modem_upgrader-v1.2.0.zip` file to your OpenWISP server:

```bash
# Copy zip to the server (from your local machine)
scp openwisp_modem_upgrader-v1.2.0.zip user@your-server:/tmp/

# On the server, navigate to your OpenWISP project's Python packages directory
# This is typically the site-packages of your virtual environment or the project root
cd /opt/openwisp/  # adjust to your OpenWISP installation path
```

### Step 2: Unzip the module

```bash
# Unzip into the Python path where Django can find it
# Option A: Install into site-packages (recommended)
unzip /tmp/openwisp_modem_upgrader-v1.2.0.zip -d /opt/openwisp/venv/lib/python3.x/site-packages/
# Replace python3.x with your actual Python version (e.g., python3.10)

# Option B: Install into the project root (if your project root is on PYTHONPATH)
unzip /tmp/openwisp_modem_upgrader-v1.2.0.zip -d /opt/openwisp/
```

### Step 3: Install additional Python dependencies

```bash
source /opt/openwisp/venv/bin/activate  # activate your virtualenv

pip install "jsonschema>=4.0.0"
pip install "zstandard>=0.22.0"

# django-private-storage should already be installed with openwisp-controller
# Verify it:
pip show django-private-storage
```

### Step 4: Verify the module is importable

```bash
python -c "import openwisp_modem_upgrader; print('Module imported successfully')"
```

---

## 3. Django Configuration

Edit your Django project's **settings.py** file (e.g., `/opt/openwisp/openwisp2/settings.py` or wherever your project settings reside).

### 3.1 Add to INSTALLED_APPS

Add `"openwisp_modem_upgrader"` to your `INSTALLED_APPS` list. It should be placed **after** `openwisp_controller` apps and **before** `openwisp_utils.admin_theme`:

```python
INSTALLED_APPS = [
    # ... existing Django apps ...

    # OpenWISP controller apps (should already exist)
    "openwisp_controller.pki",
    "openwisp_controller.config",
    "openwisp_controller.connection",
    "openwisp_controller.geo",

    # OpenWISP Firmware Upgrader (if already installed)
    "openwisp_firmware_upgrader",

    # ADD THIS LINE — OpenWISP Modem Upgrader
    "openwisp_modem_upgrader",

    # OpenWISP core apps (should already exist)
    "openwisp_users",
    "openwisp_notifications",
    "openwisp_ipam",

    # ... rest of your apps ...
]
```

### 3.2 Ensure PRIVATE_STORAGE_ROOT is configured

This setting should already exist if you use `openwisp-firmware-upgrader` or `django-private-storage`. If not, add it:

```python
import os

PRIVATE_STORAGE_ROOT = os.path.join(BASE_DIR, "private", "firmware")
```

Make sure this directory exists and is writable by the Django process:

```bash
mkdir -p /opt/openwisp/private/firmware
chown -R www-data:www-data /opt/openwisp/private/firmware  # adjust user as needed
```

---

## 4. URL Configuration

Edit your project's **urls.py** (root URL configuration) to include the modem upgrader URLs.

Add the following line alongside your existing OpenWISP URL includes:

```python
from django.urls import include, path

urlpatterns = [
    # ... existing URL patterns ...

    # OpenWISP Controller (should already exist)
    path("", include("openwisp_controller.urls")),

    # OpenWISP Firmware Upgrader (if already installed)
    path("", include("openwisp_firmware_upgrader.urls")),

    # ADD THIS LINE — OpenWISP Modem Upgrader
    path("", include("openwisp_modem_upgrader.urls")),

    # ... rest of your URL patterns ...
]
```

This registers:
- **Admin interface pages** for managing modem firmware categories, builds, images, and upgrade operations
- **REST API endpoints** under `/api/v1/modem/` (if `OPENWISP_MODEM_UPGRADER_API=True`, which is the default)
- **Private storage download URLs** for firmware file downloads under `/modem-firmware/`

---

## 5. Celery Configuration

The modem upgrader requires Celery for background task processing. Your existing OpenWISP Celery setup should work — just ensure task autodiscovery is enabled.

### 5.1 Verify Celery autodiscovery

In your project's `celery.py` file, ensure `autodiscover_tasks()` is called:

```python
from celery import Celery

app = Celery("openwisp2")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

### 5.2 Restart Celery services

After adding the module, restart both the Celery worker and beat services:

```bash
# If using systemd
sudo systemctl restart celery-worker
sudo systemctl restart celery-beat

# If running manually
celery -A openwisp2 worker -l info --detach
celery -A openwisp2 beat -l info --detach
```

### Celery tasks registered by the modem upgrader

The module registers these background tasks automatically via autodiscovery:

| Task | Purpose |
|------|---------|
| `upgrade_modem_firmware` | Perform a single device modem firmware upgrade |
| `batch_modem_upgrade_operation` | Execute a batch upgrade across multiple devices |
| `create_device_modem_firmware` | Auto-detect and assign modem firmware to a device |
| `create_all_device_modem_firmwares` | Auto-detect modem firmware for all eligible devices |
| `delete_modem_firmware_files` | Clean up firmware files after deletion |

---

## 6. Database Migration

Run Django migrations to create the modem upgrader database tables:

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

---

## 7. Static Files

Collect static files so the admin interface assets (CSS/JS) are served properly:

```bash
python manage.py collectstatic --noinput
```

---

## 8. Verification

### 8.1 Run Django system check

```bash
python manage.py check
```

This should complete with no errors. Warnings about unused settings are acceptable.

### 8.2 Verify admin interface

1. Restart your Django application server (gunicorn, daphne, etc.):

   ```bash
   # If using systemd
   sudo systemctl restart openwisp

   # If using supervisor
   sudo supervisorctl restart openwisp
   ```

2. Open your OpenWISP admin panel in a browser (e.g., `https://your-server/admin/`).

3. You should see a new **"Modem Upgrader"** section in the admin menu with:
   - Modem Categories
   - Modem Builds
   - Modem Firmware Images
   - Device Modem Firmware
   - Modem Batch Upgrade Operations
   - Modem Upgrade Operations

### 8.3 Verify API endpoints

If the API is enabled (default), test the endpoints:

```bash
# List modem categories (requires authentication)
curl -H "Authorization: Bearer <your-api-token>" \
     https://your-server/api/v1/modem/category/

# List modem builds
curl -H "Authorization: Bearer <your-api-token>" \
     https://your-server/api/v1/modem/build/
```

### 8.4 Verify Celery tasks are registered

```bash
celery -A openwisp2 inspect registered | grep modem
```

You should see the modem upgrader tasks listed.

---

## 9. Optional Settings

Add these to your `settings.py` to customize behavior. All settings have sensible defaults and are **optional**.

```python
# ─── Modem Upgrader Map ───
# Register custom upgrader classes (default includes Telit FN990AXX)
# OPENWISP_MODEM_UPGRADERS_MAP = {
#     "telit": "openwisp_modem_upgrader.upgraders.telit.TelitFN990AXX",
# }

# ─── Custom Modem Images ───
# Add custom modem model/board mappings
# OPENWISP_CUSTOM_TELIT_IMAGES = (
#     ("custom-modem-v1", {
#         "label": "Custom Modem Model",
#         "boards": ("CustomBoard1", "CustomBoard2"),
#     }),
# )

# ─── File Size Limit ───
# Maximum firmware file upload size in bytes (default: 250 MB)
# OPENWISP_MODEM_UPGRADER_MAX_FILE_SIZE = 250 * 1024 * 1024

# ─── Task Timeout ───
# Celery task timeout in seconds (default: 2400 = 40 minutes)
# OPENWISP_MODEM_UPGRADER_TASK_TIMEOUT = 2400

# ─── Retry Options ───
# Celery retry configuration for upgrade tasks (default: no retries)
# OPENWISP_MODEM_UPGRADER_RETRY_OPTIONS = {
#     "max_retries": 0,
# }

# ─── API Toggle ───
# Enable/disable the REST API (default: True)
# OPENWISP_MODEM_UPGRADER_API = True

# ─── API Base URL ───
# Base URL prefix for API endpoints (default: "/")
# OPENWISP_MODEM_API_BASEURL = "/"
```

---

## 10. Management Commands

The modem upgrader provides the following management command:

### `cancel_modem_upgrades`

Cancel in-progress or pending modem upgrade operations.

```bash
# Cancel all in-progress upgrades
python manage.py cancel_modem_upgrades

# Dry run — see what would be cancelled without making changes
python manage.py cancel_modem_upgrades --dry-run

# Cancel upgrades for a specific device (by MAC address)
python manage.py cancel_modem_upgrades --mac <device-mac-address>

# Cancel upgrades for a specific batch operation
python manage.py cancel_modem_upgrades --batch <batch-operation-id>
```

---

## 11. Troubleshooting

### Module not found error

```
ModuleNotFoundError: No module named 'openwisp_modem_upgrader'
```

**Solution:** Ensure the `openwisp_modem_upgrader` directory is placed in a location on your Python path. Verify with:

```bash
python -c "import openwisp_modem_upgrader; print(openwisp_modem_upgrader.__file__)"
```

If it fails, check that the zip was extracted to the correct `site-packages` directory:

```bash
python -c "import site; print(site.getsitepackages())"
```

### Migration errors

If you see migration dependency errors, ensure `openwisp_controller` migrations are up to date:

```bash
python manage.py migrate
```

### Static files not loading in admin

Re-run static file collection:

```bash
python manage.py collectstatic --clear --noinput
```

### Celery tasks not executing

1. Verify Redis is running: `redis-cli ping` → should return `PONG`
2. Verify worker is running: `celery -A openwisp2 inspect active`
3. Check Celery logs for errors
4. Ensure `CELERY_BROKER_URL` is correctly set in your settings

### Permission issues with firmware file uploads

Ensure the `PRIVATE_STORAGE_ROOT` directory is owned by the web server user:

```bash
ls -la /opt/openwisp/private/firmware/
sudo chown -R www-data:www-data /opt/openwisp/private/firmware/
sudo chmod -R 750 /opt/openwisp/private/firmware/
```

---

## Quick Reference — Commands Summary

```bash
# 1. Copy and extract module
scp openwisp_modem_upgrader-v1.2.0.zip user@server:/tmp/
ssh user@server
cd /opt/openwisp
source venv/bin/activate
unzip /tmp/openwisp_modem_upgrader-v1.2.0.zip -d venv/lib/python3.x/site-packages/

# 2. Install dependencies
pip install "jsonschema>=4.0.0" "zstandard>=0.22.0"

# 3. Edit settings.py — add "openwisp_modem_upgrader" to INSTALLED_APPS
# 4. Edit urls.py — add: path("", include("openwisp_modem_upgrader.urls"))

# 5. Run migrations
python manage.py migrate modem_upgrader

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Restart services
sudo systemctl restart openwisp celery-worker celery-beat

# 8. Verify
python manage.py check
```