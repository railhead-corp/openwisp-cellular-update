#!/bin/bash
# Setup Ansible in WSL for OpenWISP Deployment

set -e

echo "======================================"
echo "Setting up Ansible for OpenWISP"
echo "======================================"
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version; then
    echo "WARNING: This script is designed for WSL (Windows Subsystem for Linux)"
    echo "Are you sure you want to continue? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/5] Updating package lists..."
sudo apt update

echo ""
echo "[2/5] Installing Ansible and sshpass..."
sudo apt install -y ansible sshpass

echo ""
echo "[3/5] Installing required collections..."
ansible-galaxy collection install community.general

echo ""
echo "[4/5] Installing OpenWISP2 Ansible Role..."
ansible-galaxy install openwisp.openwisp2

echo ""
echo "[5/5] Verifying installation..."
ansible --version
echo ""
echo "Installed roles:"
ansible-galaxy list

echo ""
echo "======================================"
echo "✓ Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Navigate to ansible-deployment directory:"
echo "     cd /mnt/d/OneDrive\\ -\\ SoftDEL\\ Systems\\ Pvt.\\ Ltd/workspace/Railhead/railhead-corporation-openwisp-server/ansible-deployment"
echo ""
echo "  2. Test connection:"
echo "     ansible -i hosts openwisp2 -m ping"
echo ""
echo "  3. Deploy your changes:"
echo "     ansible-playbook -i hosts update-playbook.yml -v"
echo ""
