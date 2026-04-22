# Converting PPK to OpenSSH Format for Ansible

## The Issue

Ansible error:
```
cchandanbatwe@50.234.228.83: Permission denied (publickey)
```

**Cause:** The server only accepts SSH key authentication, not passwords.

---

## Solution: Convert Your PPK File

### Step 1: Install putty-tools (in WSL)

```bash
sudo apt install -y putty-tools
```

### Step 2: Locate Your PPK File

The PPK file should be at:
```
/mnt/d/OneDrive - SoftDEL Systems Pvt. Ltd/workspace/Railhead/cchandanbatwe.ppk
```

Or wherever you have saved it.

### Step 3: Convert PPK to OpenSSH Format

```bash
# Create .ssh directory if it doesn't exist
mkdir -p ~/.ssh

# Convert the PPK file (adjust path if needed)
puttygen /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/cchandanbatwe.ppk \
  -O private-openssh \
  -o ~/.ssh/cchandanbatwe_key

# Set correct permissions (IMPORTANT!)
chmod 600 ~/.ssh/cchandanbatwe_key
```

### Step 4: Test SSH Connection

```bash
# Test that you can connect with the key
ssh -i ~/.ssh/cchandanbatwe_key cchandanbatwe@50.234.228.83

# If successful, type 'exit' to disconnect
```

### Step 5: Update Ansible Inventory (Already Done)

The `hosts` file is already configured to use the key:
```ini
ansible_ssh_private_key_file=~/.ssh/cchandanbatwe_key
```

### Step 6: Test Ansible Connection

```bash
cd /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment

ansible -i hosts openwisp2 -m ping
```

You should see:
```
50.234.228.83 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

---

## Alternative: If You Don't Have the PPK File

If you don't have the PPK file, you need to:

1. **Get it from the server administrator**, OR
2. **Generate a new SSH key pair:**

```bash
# Generate new SSH key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cchandanbatwe_key

# Copy public key to server (you'll need the password one time)
ssh-copy-id -i ~/.ssh/cchandanbatwe_key.pub cchandanbatwe@50.234.228.83
```

---

## Troubleshooting

### "No such file or directory" when converting PPK
Check the PPK file path:
```bash
ls /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/*.ppk
```

### "Permission denied" even with key
Check key permissions:
```bash
ls -la ~/.ssh/cchandanbatwe_key
# Should show: -rw------- (600)

# Fix if needed:
chmod 600 ~/.ssh/cchandanbatwe_key
```

### "puttygen: command not found"
Install putty-tools:
```bash
sudo apt install -y putty-tools
```

---

## Quick Commands Summary

```bash
# 1. Install putty-tools
sudo apt install -y putty-tools

# 2. Convert PPK (adjust path to your PPK file location)
mkdir -p ~/.ssh
puttygen /mnt/d/path/to/cchandanbatwe.ppk -O private-openssh -o ~/.ssh/cchandanbatwe_key
chmod 600 ~/.ssh/cchandanbatwe_key

# 3. Test SSH
ssh -i ~/.ssh/cchandanbatwe_key cchandanbatwe@50.234.228.83

# 4. Test Ansible
cd /mnt/d/OneDrive\ -\ SoftDEL\ Systems\ Pvt.\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment
ansible -i hosts openwisp2 -m ping

# 5. Deploy if test successful
ansible-playbook -i hosts update-playbook.yml -v
```
