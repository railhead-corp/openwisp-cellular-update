# Ansible Deployment for OpenWISP Server

## Overview

This directory contains Ansible playbooks for deploying OpenWISP to the production server at `50.234.228.83`.

Based on the official OpenWISP Ansible documentation: https://openwisp.io/docs/dev/ansible/user/installing-on-vm.html

## Prerequisites

### IMPORTANT: Ansible Does NOT Work on Native Windows

Ansible requires a Unix-like environment. You **must** use one of these options on Windows:

### 1. Install Ansible in WSL (Recommended)

**Open WSL terminal** and run:

```bash
# Update package lists
sudo apt update

# Install Ansible
sudo apt install -y ansible

# Install required collections
ansible-galaxy collection install community.general

# Install OpenWISP2 Ansible Role
ansible-galaxy install openwisp.openwisp2
```

### 2. Alternative: Use Docker

```bash
# Pull Ansible Docker image
docker pull cytopia/ansible:latest

# Run Ansible commands in container
docker run --rm -v ${PWD}:/ansible cytopia/ansible ansible-galaxy install openwisp.openwisp2
```

### 3. Verify Installation

```bash
# In WSL
ansible --version
ansible-galaxy list
```

## Running the Deployment

### From WSL Terminal

```bash
# Navigate to the project (adjust path as needed)
cd /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment

# Test connection
ansible -i hosts openwisp2 -m ping

# Run the deployment
ansible-playbook -i hosts update-playbook.yml -v
```

## Files

- **`hosts`** - Ansible inventory file with server connection details
- **`playbook.yml`** - Full OpenWISP installation playbook (for fresh install)
- **`update-playbook.yml`** - Update existing OpenWISP with your changes (recommended)
- **`README.md`** - This file

## Deployment Methods

### Method 1: Update Existing Installation (Recommended)

This is for deploying your modem upgrader changes to the existing OpenWISP installation.

**In WSL terminal:**

```bash
# Navigate to ansible-deployment directory (adjust path to your setup)
cd /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment

# Run the update playbook
ansible-playbook -i hosts update-playbook.yml -v
```

**What it does:**
- Uploads your `openwisp_modem_upgrader` module
- Updates `openwisp_firmware_upgrader` if modified
- Runs database migrations
- Collects static files
- Restarts services (openwisp2, celery, celerybeat, nginx)

### Method 2: Fresh Installation (NOT recommended for production)

Only use this if you need to reinstall OpenWISP from scratch:

```bash
ansible-playbook -i hosts playbook.yml -v
```

## Troubleshooting

### SSH Connection Issues

If you get SSH errors, test the connection:
```bash
ansible -i hosts openwisp2 -m ping
```

### Permission Errors

The playbook uses sudo, ensure the user has sudo privileges:
```bash
ssh cchandanbatwe@50.234.228.83 "sudo -v"
```

### Check Service Status

After deployment, verify services are running:
```bash
ansible -i hosts openwisp2 -m shell -a "systemctl status openwisp2" --become
ansible -i hosts openwisp2 -m shell -a "systemctl status celery" --become
```

### View Logs

```bash
# OpenWISP logs
ansible -i hosts openwisp2 -m shell -a "tail -50 /var/log/openwisp2/openwisp2.log" --become

# Celery logs
ansible -i hosts openwisp2 -m shell -a "journalctl -u celery -n 50" --become
```

## Manual Commands

If Ansible has issues, you can run commands manually:

```bash
# Connect to server
ssh cchandanbatwe@50.234.228.83

# Navigate to OpenWISP directory
cd /opt/openwisp2

# Run migrations
sudo python manage.py migrate

# Collect static files
sudo python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart openwisp2
sudo systemctl restart celery
sudo systemctl restart celerybeat
```

## Configuration

### Customizing Variables

Edit `update-playbook.yml` to change:
- `openwisp_path`: Default is `/opt/openwisp2`
- Service names
- Database settings

### Adding SSH Key Authentication

Instead of password authentication, you can use SSH keys:

1. Generate SSH key pair (if you don't have one):
   ```bash
   ssh-keygen -t rsa -b 4096
   ```

2. Copy public key to server:
   ```bash
   ssh-copy-id cchandanbatwe@50.234.228.83
   ```

3. Update `hosts` file to remove password:
   ```ini
   [openwisp2]
   50.234.228.83 ansible_user=cchandanbatwe
   ```

## Post-Deployment Verification

1. **Check Web Interface**
   - Navigate to: `http://50.234.228.83` or `https://50.234.228.83`
   - Login with admin credentials

2. **Verify Modem Upgrader**
   ```bash
   ssh cchandanbatwe@50.234.228.83
   cd /opt/openwisp2
   sudo python manage.py shell
   ```
   In Python shell:
   ```python
   from openwisp_modem_upgrader.upgraders.telit import TelitFN990AXX
   print("Modem upgrader loaded successfully!")
   ```

3. **Check Service Status**
   ```bash
   ansible -i hosts openwisp2 -m shell -a "systemctl status openwisp2 celery celerybeat" --become
   ```

## Quick Reference

```bash
# Test connection
ansible -i hosts openwisp2 -m ping

# Deploy updates
ansible-playbook -i hosts update-playbook.yml -v

# Check specific service
ansible -i hosts openwisp2 -m shell -a "systemctl status openwisp2" --become

# View recent logs
ansible -i hosts openwisp2 -m shell -a "journalctl -u openwisp2 -n 50" --become

# Restart specific service
ansible -i hosts openwisp2 -m systemd -a "name=celery state=restarted" --become
```

## Notes

- The server is already running OpenWISP at `/opt/openwisp2/`
- It's a traditional Django deployment (not Docker)
- Services are managed by systemd
- Database is PostgreSQL
- Web server is Nginx with gunicorn/uwsgi

## Support

For OpenWISP Ansible role documentation:
- https://openwisp.io/docs/dev/ansible/
- https://github.com/openwisp/ansible-openwisp2
