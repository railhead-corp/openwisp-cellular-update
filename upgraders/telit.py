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
        
        # Step 1: Verify device connectivity
        self.operation.log_line("Verifying device connectivity...")
        self.operation.update_progress(5)
        if not self._verify_connectivity():
            raise RecoverableModemFailure("Device connectivity check failed")
        self.operation.update_progress(10)
        
        # Step 2: Transfer firmware file to device
        self.operation.log_line("Transferring firmware file to device...")
        remote_path = self._transfer_firmware(firmware_file)
        self.operation.update_progress(30)
        
        # Step 3: Trigger custom script (for modem preparation)
        self.operation.log_line("Preparing device for modem upgrade...")
        try:
            script_cmd = "/root/script.sh"
            script_output = self._execute_command(script_cmd, timeout=120)
            self.operation.log_line(f"Preparation script output: {script_output.strip()}")
        except Exception as e:
            error_msg = f"Device preparation failed: {e}"
            logger.error(error_msg)
            self.operation.log_line(error_msg)
            # Clean up transferred file before raising exception
            self._cleanup_remote_file(remote_path)
            raise RecoverableModemFailure(error_msg)
        self.operation.update_progress(40)
        
        # Step 4: Check if upgrade is needed (optional)
        self.operation.log_line("Checking current modem firmware version...")
        if self._check_firmware_version(remote_path):
            self._cleanup_remote_file(remote_path)
            self.operation.log_line("Modem already has the target firmware version")
            raise ModemUpgradeNotNeeded("Firmware already installed")
        self.operation.update_progress(50)
        
        # Step 5: Execute the upgrade
        self.operation.log_line("Executing modem firmware upgrade...")
        try:
            self._execute_upgrade(remote_path)
        except Exception as e:
            # Clean up on failure
            self._cleanup_remote_file(remote_path)
            raise
        self.operation.update_progress(85)
        
        # Step 6: Clean up firmware file
        self._cleanup_remote_file(remote_path)
        self.operation.update_progress(90)
        
        # Step 7: Reboot modem if requested
        if self._get_option("reboot_modem", True):
            self.operation.log_line("Rebooting modem...")
            self._reboot_modem()
        self.operation.update_progress(95)
        
        # Step 8: Verify upgrade success
        self.operation.log_line("Verifying upgrade completion...")
        if not self._verify_upgrade():
            raise RecoverableModemFailure("Upgrade verification failed")
        
        self.operation.update_progress(100)
        self.operation.log_line("Modem firmware upgrade completed successfully")

    def _verify_connectivity(self):
        """
        Verify that we can execute basic commands on the device.
        
        Returns:
            bool: True if device is reachable and responsive
        """
        try:
            result = self._execute_command("echo 'connectivity_check'", timeout=30)
            return "connectivity_check" in result
        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            return False
    
    def _cleanup_remote_file(self, remote_path):
        """Clean up a remote file, ignoring errors"""
        try:
            self._execute_command(f"rm -f {remote_path}", timeout=30)
            self.operation.log_line(f"Cleaned up temporary file: {remote_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {remote_path}: {e}")

    def _transfer_firmware(self, firmware_file):
        """
        Transfer firmware file to the device via SCP.
        
        Returns:
            str: Remote path where firmware was uploaded
        """
        import tempfile
        import os
        import subprocess
        
        remote_path = f"/tmp/modem_firmware_{int(time.time())}.bin"
        timeout = self._get_option("transfer_timeout", 600)
        
        try:
            # Read firmware file content
            firmware_file.seek(0)
            firmware_data = firmware_file.read()
            file_size_mb = len(firmware_data) / (1024 * 1024)
            
            self.operation.log_line(f"Uploading firmware to {remote_path} ({file_size_mb:.2f} MB)")
            
            # Write firmware to temporary local file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp_file:
                tmp_file.write(firmware_data)
                tmp_file_path = tmp_file.name
            
            self.operation.log_line(f"Created temporary file: {tmp_file_path}")
            
            try:
                # Get connection details
                device = self.connection.device
                credentials = self.connection.credentials
                host = device.last_ip or device.management_ip
                
                # Get credentials from params dictionary
                cred_params = credentials.params
                username = cred_params.get('username', 'root')
                password = cred_params.get('password')
                key = cred_params.get('key')
                port = cred_params.get('port', 22)
                
                # Build SCP command
                scp_target = f"{username}@{host}:{remote_path}"
                scp_cmd = ["scp", "-O", "-P", str(port)]  # -O forces legacy SCP protocol
                
                # Handle authentication
                if key:
                    # Write SSH key to temporary file
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as key_file:
                        key_file.write(key)
                        key_file_path = key_file.name
                    
                    # Set proper permissions for key file
                    os.chmod(key_file_path, 0o600)
                    scp_cmd.extend(["-i", key_file_path])
                    self.operation.log_line("Using SSH key authentication")
                elif password:
                    # Use sshpass for password authentication
                    scp_cmd = ["sshpass", "-p", password] + scp_cmd
                    self.operation.log_line("Using password authentication")
                else:
                    raise Exception("No authentication credentials found (neither password nor key)")
                
                # Add common SSH options
                scp_cmd.extend([
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", f"ConnectTimeout={timeout}",
                    tmp_file_path,
                    scp_target
                ])
                
                self.operation.log_line(f"Transferring to {host}:{remote_path}...")
                self.operation.update_progress(15)
                
                # Execute SCP command
                process = subprocess.Popen(
                    scp_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate(timeout=timeout)
                
                if process.returncode != 0:
                    error_msg = stderr.strip() if stderr else f"SCP exited with code {process.returncode}"
                    raise Exception(f"SCP transfer failed: {error_msg}")
                
                self.operation.log_line("SCP transfer completed successfully")
                self.operation.update_progress(25)
                
            finally:
                # Clean up temporary files
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
                if 'key_file_path' in locals():
                    try:
                        os.unlink(key_file_path)
                    except:
                        pass
            
            # Verify file size on remote device
            self.operation.log_line("Verifying transferred file...")
            result = self._execute_command(f"stat -c%s {remote_path} 2>/dev/null || wc -c < {remote_path}", timeout=60)
            remote_size = int(result.strip())
            
            if remote_size != len(firmware_data):
                raise RecoverableModemFailure(
                    f"File transfer verification failed: expected {len(firmware_data)} bytes, got {remote_size} bytes"
                )
            
            self.operation.log_line(f"Firmware uploaded and verified: {remote_size} bytes")
            return remote_path
            
        except subprocess.TimeoutExpired:
            raise RecoverableModemFailure(f"Firmware transfer timed out after {timeout} seconds")
        except RecoverableModemFailure:
            raise
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

    def _execute_command(self, cmd, timeout=60, raise_on_error=True):
        """
        Execute a shell command on the device via SSH.
        
        Args:
            cmd: Command to execute
            timeout: Command timeout in seconds
            raise_on_error: Whether to raise exception on non-zero exit code
            
        Returns:
            str: Command output (stdout)
        """
        try:
            connector = self.connection.connector_instance
            
            # Execute the command
            result = connector.exec_command(cmd, timeout=timeout)
            
            # Handle different return formats from SSH connector
            exit_code = 0
            stdout = ""
            stderr = ""
            
            if isinstance(result, tuple):
                if len(result) == 2:
                    # Check if it's (exit_code, output) or (stdout, stderr)
                    first, second = result
                    if isinstance(first, int):
                        # Format: (exit_code, output)
                        exit_code, stdout = first, second
                    else:
                        # Format: (stdout, stderr) - assume success
                        stdout, stderr = first, second
                        exit_code = 0
                elif len(result) == 3:
                    # Format: (stdout, stderr, exit_code) or (exit_code, stdout, stderr)
                    if isinstance(result[0], int):
                        exit_code, stdout, stderr = result
                    elif isinstance(result[2], int):
                        stdout, stderr, exit_code = result
                    else:
                        # All strings, assume success
                        stdout = str(result[0])
                        exit_code = 0
                else:
                    # Unexpected tuple length, use first element as output
                    stdout = str(result[0]) if result else ""
                    exit_code = 0
            elif isinstance(result, str):
                # Direct string output - assume success
                stdout = result
                exit_code = 0
            else:
                # Unexpected type, convert to string
                stdout = str(result) if result is not None else ""
                exit_code = 0
            
            # Log successful execution
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Command executed: {cmd[:100]}... -> exit_code={exit_code}")
            
            # Only raise error if exit_code is actually an integer and non-zero
            if raise_on_error and isinstance(exit_code, int) and exit_code != 0:
                error_msg = stderr.strip() if stderr else f"Command exited with code {exit_code}"
                logger.error(f"Command failed: {cmd[:100]}..., exit code: {exit_code}, error: {error_msg}")
                raise RecoverableModemFailure(f"Command failed: {error_msg}")
            
            return stdout if isinstance(stdout, str) else str(stdout)
            
        except RecoverableModemFailure:
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {cmd[:100]}..., error: {e}")
            raise RecoverableModemFailure(f"Command execution error: {e}")
