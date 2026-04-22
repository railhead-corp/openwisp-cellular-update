# Quick Start Guide for WSL Deployment

## The Error You Got

```
OSError: [WinError 1] Incorrect function
```

**This error occurs because Ansible does NOT work on native Windows.** You must use WSL (Windows Subsystem for Linux).

---

## ✅ Solution: Use WSL

### IMPORTANT: Server Requires SSH Key Authentication

The server at `50.234.228.83` has password authentication **disabled**. You need to use the PPK file.

### Step 0: Convert PPK to OpenSSH Format

In **WSL terminal**, convert the PPK file to OpenSSH format that Ansible can use:

```bash
# Install puttygen if not already installed
sudo apt install -y putty-tools

# Convert PPK to OpenSSH format (adjust path to your PPK file)
# The PPK file is at: ../cchandanbatwe.ppk (relative to project root)
puttygen /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/cchandanbatwe.ppk \
  -O private-openssh -o ~/.ssh/cchandanbatwe_key

# Set correct permissions
chmod 600 ~/.ssh/cchandanbatwe_key

# Test SSH connection
ssh -i ~/.ssh/cchandanbatwe_key cchandanbatwe@50.234.228.83
```

### Step 1: Open WSL Terminal

In VS Code, open a new terminal and select **WSL** or open **Ubuntu** from Windows Start menu.

### Step 2: Run Setup Script

```bash
# Navigate to the project in WSL
cd /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment

# Make script executable
chmod +x setup-wsl.sh

# Run setup
./setup-wsl.sh
```

This will:
- Install Ansible
- Install required collections
- Install OpenWISP2 role

### Step 3: Deploy Your Changes

```bash
# Still in WSL terminal
ansible-playbook -i hosts update-playbook.yml -v
```

---

## Manual Setup (if script doesn't work)

```bash
# In WSL terminal
sudo apt update
sudo apt install -y ansible sshpass
ansible-galaxy collection install community.general
ansible-galaxy install openwisp.openwisp2
```

---

## Verifying WSL Installation

```bash
# Check Ansible version
ansible --version

# Check installed roles
ansible-galaxy list

# Should see: openwisp.openwisp2
```

---

## Common Issues

### Issue: "sudo: apt: command not found"
**Solution:** You're not in WSL. Make sure you're using WSL terminal, not PowerShell or CMD.

### Issue: "cannot find ansible-playbook"
**Solution:** Ansible not installed. Run:
```bash
sudo apt install -y ansible sshpass
```

### Issue: "Permission denied (publickey)"
**Solution:** The server requires SSH key authentication. Password authentication is disabled. Follow Step 0 above to convert your PPK file to OpenSSH format.

```bash
# Install putty-tools
sudo apt install -y putty-tools

# Convert PPK to OpenSSH key
puttygen /path/to/cchandanbatwe.ppk -O private-openssh -o ~/.ssh/cchandanbatwe_key

# Set permissions
chmod 600 ~/.ssh/cchandanbatwe_key
```

### Issue: "World writable directory warning"
**Solution:** This is just a warning and can be ignored. Ansible will still work. To fix:
```bash
# In WSL, directories on Windows drives (/mnt/d/) appear world-writable
# You can ignore this warning or copy files to WSL home directory
cp -r /mnt/d/path/to/ansible-deployment ~/ansible-deployment
cd ~/ansible-deployment
```

### Issue: "Permission denied" when running setup-wsl.sh
**Solution:** Make it executable:
```bash
chmod +x setup-wsl.sh
```

---

## Quick Deployment Commands

```bash
# 1. Navigate to ansible directory
cd /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment

# 2. Test connection
ansible -i hosts openwisp2 -m ping

# 3. Deploy
ansible-playbook -i hosts update-playbook.yml -v

# 4. Check service status after deployment
ansible -i hosts openwisp2 -m shell -a "systemctl status openwisp2" --become
```

---

## Why WSL is Required

- Ansible is built for Unix/Linux systems
- It uses Unix-specific features (fork, signals, etc.)
- Windows native Python doesn't support these features
- WSL provides a full Linux environment on Windows

For more info: https://docs.ansible.com/ansible/latest/os_guide/windows_faq.html
