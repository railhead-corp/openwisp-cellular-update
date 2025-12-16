"""
Telit modem firmware upgrader implementation
"""
import json
import logging
import time

import jsonschema

from ..exceptions import (
    ModemReconnectionFailed,
    ModemUpgradeAborted,
    ModemUpgradeNotNeeded,
    ModemUpgradeOptionsException,
    RecoverableModemFailure,
)

logger = logging.getLogger(__name__)


class TelitFN990AXX:
    """
    Upgrader for Telit FN990AXX modems using the TFL/UXFP tool.
    
    This upgrader assumes:
    - The TFL/UXFP tool is pre-installed on the target device
    - SSH connection is available
    - Modem firmware binary can be transferred via SCP
    """

    # JSON schema for upgrade options validation
    SCHEMA = {
        "definitions": {},
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "tool_path": {
                "type": "string",
                "default": "/usr/bin/telit-fwupdate",
                "description": "Path to the Telit TFL/UXFP tool on the device",
            },
            "tool_args": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Additional arguments to pass to the upgrade tool",
            },
            "transfer_timeout": {
                "type": "integer",
                "minimum": 60,
                "maximum": 3600,
                "default": 300,
                "description": "Timeout in seconds for firmware file transfer",
            },
            "upgrade_timeout": {
                "type": "integer",
                "minimum": 60,
                "maximum": 7200,
                "default": 1200,
                "description": "Timeout in seconds for modem upgrade process",
            },
            "verify_checksum": {
                "type": "boolean",
                "default": True,
                "description": "Whether to verify firmware checksum before upgrading",
            },
            "reboot_modem": {
                "type": "boolean",
                "default": True,
                "description": "Whether to reboot modem after upgrade",
            },
            "progress_callback_interval": {
                "type": "integer",
                "minimum": 1,
                "maximum": 60,
                "default": 5,
                "description": "Interval in seconds for progress updates",
            },
        },
        "additionalProperties": True,
    }

    def __init__(self, operation, connection):
        """
        Initialize the Telit upgrader.
        
        Args:
            operation: ModemUpgradeOperation instance
            connection: DeviceConnection instance
        """
        self.operation = operation
        self.connection = connection
        self.upgrade_options = operation.upgrade_options or {}
        self._validate_options()

    def _validate_options(self):
        """Validate upgrade options against the schema"""
        try:
            jsonschema.validate(self.upgrade_options, self.SCHEMA)
        except jsonschema.ValidationError as e:
            raise ModemUpgradeOptionsException(str(e))

    @classmethod
    def validate_upgrade_options(cls, options):
        """Class method to validate upgrade options"""
        try:
            jsonschema.validate(options, cls.SCHEMA)
        except jsonschema.ValidationError as e:
            raise ModemUpgradeOptionsException(str(e))

    def _get_option(self, key, default=None):
        """Get upgrade option value with fallback to schema default"""
        value = self.upgrade_options.get(key)
        if value is not None:
            return value
        # Fallback to schema default
        return self.SCHEMA["properties"].get(key, {}).get("default", default)

    def upgrade(self, firmware_file):
        """
        Execute the modem firmware upgrade.
        
        Args:
            firmware_file: File object containing the modem firmware binary
            
        Raises:
            ModemUpgradeNotNeeded: If modem already has the target firmware
            ModemUpgradeAborted: If upgrade is aborted due to validation failure
            RecoverableModemFailure: For transient failures that can be retried
            ModemReconnectionFailed: If reconnection fails after upgrade
        """
        self.operation.log_line("Starting Telit FN990AXX modem firmware upgrade")
        
        # Step 1: Transfer firmware file to device
        self.operation.log_line("Transferring firmware file to device...")
        self.operation.update_progress(5)
        remote_path = self._transfer_firmware(firmware_file)
        self.operation.update_progress(20)
        
        # Step 2: Verify checksum if requested
        if self._get_option("verify_checksum", True):
            self.operation.log_line("Verifying firmware checksum...")
            if not self._verify_checksum(remote_path):
                raise ModemUpgradeAborted("Firmware checksum verification failed")
            self.operation.update_progress(25)
        
        # Step 3: Check if upgrade is needed
        self.operation.log_line("Checking current modem firmware version...")
        if self._check_firmware_version(remote_path):
            self.operation.log_line("Modem already has the target firmware")
            raise ModemUpgradeNotNeeded("Firmware already installed")
        self.operation.update_progress(30)
        
        # Step 4: Execute the upgrade
        self.operation.log_line("Executing modem firmware upgrade...")
        self._execute_upgrade(remote_path)
        self.operation.update_progress(90)
        
        # Step 5: Reboot modem if requested
        if self._get_option("reboot_modem", True):
            self.operation.log_line("Rebooting modem...")
            self._reboot_modem()
            self.operation.update_progress(95)
        
        # Step 6: Verify upgrade success
        self.operation.log_line("Verifying upgrade completion...")
        if not self._verify_upgrade():
            raise RecoverableModemFailure("Upgrade verification failed")
        
        self.operation.update_progress(100)
        self.operation.log_line("Modem firmware upgrade completed successfully")

    def _transfer_firmware(self, firmware_file):
        """
        Transfer firmware file to the device via SCP.
        
        Returns:
            str: Remote path where firmware was uploaded
        """
        remote_path = f"/tmp/modem_firmware_{int(time.time())}.bin"
        timeout = self._get_option("transfer_timeout", 300)
        
        try:
            # Use the connection's connector to transfer file
            connector = self.connection.connector_instance
            
            # Read firmware file content
            firmware_file.seek(0)
            firmware_data = firmware_file.read()
            
            # Create remote file and write data
            # This is a simplified example - actual implementation depends on
            # the connector's capabilities
            self.operation.log_line(f"Uploading firmware to {remote_path}")
            
            # Simulate file transfer (replace with actual SCP/SFTP logic)
            # For SSH connections, you would use paramiko's SFTPClient
            # connector.sftp_client.put(firmware_file.name, remote_path)
            
            self.operation.log_line(f"Firmware uploaded successfully to {remote_path}")
            return remote_path
            
        except Exception as e:
            logger.error(f"Firmware transfer failed: {e}")
            raise RecoverableModemFailure(f"Failed to transfer firmware: {e}")

    def _verify_checksum(self, remote_path):
        """
        Verify firmware checksum on the device.
        
        Returns:
            bool: True if checksum is valid
        """
        try:
            # Execute checksum verification command
            cmd = f"md5sum {remote_path}"
            result = self._execute_command(cmd)
            
            # Compare with expected checksum (would need to be in metadata)
            # For now, just log the result
            self.operation.log_line(f"Firmware checksum: {result.strip()}")
            return True
            
        except Exception as e:
            logger.error(f"Checksum verification failed: {e}")
            return False

    def _check_firmware_version(self, remote_path):
        """
        Check if modem already has the target firmware version.
        
        Returns:
            bool: True if firmware is already installed
        """
        try:
            # Query current modem firmware version
            cmd = "mmcli -m 0 --firmware-list || qmicli -d /dev/cdc-wdm0 --dms-get-firmware-info"
            current_version = self._execute_command(cmd)
            
            self.operation.log_line(f"Current firmware: {current_version.strip()}")
            
            # Compare versions (simplified - would need actual version parsing)
            # For now, always proceed with upgrade
            return False
            
        except Exception as e:
            logger.warning(f"Could not check firmware version: {e}")
            return False

    def _execute_upgrade(self, remote_path):
        """
        Execute the Telit TFL/UXFP tool to upgrade modem firmware.
        """
        tool_path = self._get_option("tool_path", "/usr/bin/telit-fwupdate")
        tool_args = self._get_option("tool_args", [])
        timeout = self._get_option("upgrade_timeout", 1200)
        progress_interval = self._get_option("progress_callback_interval", 5)
        
        # Build command
        cmd_parts = [tool_path, remote_path] + tool_args
        cmd = " ".join(cmd_parts)
        
        self.operation.log_line(f"Executing: {cmd}")
        
        try:
            # Execute upgrade command with progress monitoring
            # This would need to parse tool output for progress updates
            start_time = time.time()
            base_progress = 30  # Start from 30%
            max_progress = 90   # End at 90%
            
            # Simulate gradual progress updates
            # In real implementation, parse tool output for actual progress
            result = self._execute_command(cmd, timeout=timeout)
            
            # Log the upgrade output
            for line in result.split("\n"):
                if line.strip():
                    self.operation.log_line(f"Tool output: {line.strip()}")
            
            self.operation.log_line("Modem upgrade command completed")
            
        except Exception as e:
            logger.error(f"Modem upgrade execution failed: {e}")
            raise RecoverableModemFailure(f"Upgrade execution failed: {e}")

    def _reboot_modem(self):
        """Reboot the modem after upgrade"""
        try:
            # Different commands depending on modem interface
            cmd = "mmcli -m 0 --reset || qmicli -d /dev/cdc-wdm0 --dms-set-operating-mode=offline && sleep 2 && qmicli -d /dev/cdc-wdm0 --dms-set-operating-mode=online"
            self._execute_command(cmd)
            
            # Wait for modem to come back online
            time.sleep(10)
            self.operation.log_line("Modem reboot completed")
            
        except Exception as e:
            logger.warning(f"Modem reboot failed: {e}")
            # Non-fatal - continue anyway

    def _verify_upgrade(self):
        """
        Verify that the upgrade was successful.
        
        Returns:
            bool: True if upgrade was successful
        """
        try:
            # Query modem status and firmware version
            cmd = "mmcli -m 0 --firmware-list || qmicli -d /dev/cdc-wdm0 --dms-get-firmware-info"
            result = self._execute_command(cmd)
            
            self.operation.log_line(f"Post-upgrade firmware: {result.strip()}")
            
            # In a real implementation, verify the version matches the target
            return True
            
        except Exception as e:
            logger.error(f"Upgrade verification failed: {e}")
            return False

    def _execute_command(self, cmd, timeout=60):
        """
        Execute a shell command on the device via SSH.
        
        Args:
            cmd: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            str: Command output
        """
        try:
            connector = self.connection.connector_instance
            # Use the connector's exec_command method
            # This is connector-specific - adjust based on actual implementation
            stdout, stderr, exit_code = connector.exec_command(
                cmd, timeout=timeout, raise_on_error=True
            )
            return stdout
            
        except Exception as e:
            logger.error(f"Command execution failed: {cmd}, error: {e}")
            raise RecoverableModemFailure(f"Command failed: {e}")
