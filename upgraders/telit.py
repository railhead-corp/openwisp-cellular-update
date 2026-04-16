"""
Telit modem firmware upgrader implementation
"""
import logging
import time
import shlex

import jsonschema

from ..exceptions import (
    ModemReconnectionFailed,
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
            "safe_update_path": {
                "type": "string",
                "default": "/usr/bin/safe_update.sh",
                "description": "Path to the safe_update.sh script on the device",
            },
            "verify_update_path": {
                "type": "string",
                "default": "/usr/bin/verify_update.sh",
                "description": "Path to the verify_update.sh script on the device",
            },
            "state_dir": {
                "type": "string",
                "default": "/root/modem-update",
                "description": "State directory for UXFP update scripts",
            },
            "transfer_timeout": {
                "type": "integer",
                "minimum": 60,
                "maximum": 3600,
                "default": 300,
                "description": "Timeout in seconds for firmware file transfer",
            },
            "reconnect_interval": {
                "type": "integer",
                "minimum": 30,
                "maximum": 600,
                "default": 120,
                "description": "Interval in seconds between reconnection attempts",
            },
            "reconnect_attempts": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "default": 10,
                "description": "Number of reconnection attempts after update",
            },
            "verify_checksum": {
                "type": "boolean",
                "default": True,
                "description": "Whether to verify firmware checksum before upgrading",
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
        state_dir = self._get_option("state_dir", "/root/modem-update")

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

        try:
            # Step 3: Validate firmware checksum
            self.operation.log_line("Validating firmware checksum...")
            self._verify_checksum(remote_path, firmware_file)
            self.operation.update_progress(35)

            # Step 4: Run safe_update.sh (device will disconnect)
            self.operation.log_line("Running safe_update.sh - device will disconnect...")
            self._run_safe_update(remote_path, state_dir)
            self.operation.update_progress(50)

            # Step 5: Reconnect to device after update
            self.operation.log_line("Waiting for device to come back online...")
            self._reconnect_after_update()
            self.operation.update_progress(70)

            # Step 6: Verify update status via verify_update.sh
            self.operation.log_line("Checking update result...")
            self._verify_update_status(state_dir)
            self.operation.update_progress(90)

            # Step 7: Read and log the UXFP log file
            self._read_uxfp_log(state_dir)

            self.operation.update_progress(100)
            self.operation.log_line("Modem firmware upgrade completed successfully")
        except Exception:
            # Cleanup firmware file from /tmp on failure
            self._cleanup_remote_file(remote_path)
            raise

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
        Compresses firmware with zstd before transfer to save bandwidth.
        
        Returns:
            str: Remote path where firmware was uploaded (decompressed)
        """
        import tempfile
        import os
        import subprocess
        import hashlib
        import zstandard as zstd
        
        remote_compressed_path = f"/tmp/modem_firmware_{int(time.time())}.bin.zst"
        remote_path = remote_compressed_path.replace('.zst', '')
        timeout = self._get_option("transfer_timeout", 600)
        
        try:
            # Read firmware file content
            firmware_file.seek(0)
            firmware_data = firmware_file.read()
            file_size_mb = len(firmware_data) / (1024 * 1024)
            
            # Calculate SHA256 checksum for verification
            sha256_hash = hashlib.sha256(firmware_data)
            self.expected_checksum = sha256_hash.hexdigest()
            self.operation.log_line(f"OpenWISP calculated checksum (SHA256): {self.expected_checksum}")
            self.operation.log_line(f"Original firmware size: {file_size_mb:.2f} MB")
            
            # Compress firmware using zstd
            self.operation.log_line("Compressing firmware with zstd...")
            cctx = zstd.ZstdCompressor(level=3)  # Level 3 for balanced compression/speed
            compressed_data = cctx.compress(firmware_data)
            compressed_size_mb = len(compressed_data) / (1024 * 1024)
            compression_ratio = (1 - len(compressed_data) / len(firmware_data)) * 100
            self.operation.log_line(f"Compressed size: {compressed_size_mb:.2f} MB ({compression_ratio:.1f}% reduction)")
            
            # Write compressed firmware to temporary local file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.bin.zst') as tmp_file:
                tmp_file.write(compressed_data)
                tmp_file_path = tmp_file.name
            
            self.operation.log_line(f"Created compressed temporary file: {tmp_file_path}")
            
            try:
                # Get connection details
                device = self.connection.device
                credentials = self.connection.credentials
                host = device.management_ip
                
                # Get credentials from params dictionary
                cred_params = credentials.params
                username = cred_params.get('username', 'root')
                password = cred_params.get('password')
                key = cred_params.get('key')
                port = cred_params.get('port', 22)
                
                # Build SCP command
                scp_target = f"{username}@{host}:{remote_compressed_path}"
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
                
                self.operation.log_line(f"Transferring compressed firmware to {host}:{remote_compressed_path}...")
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
                except Exception:
                    pass
                if 'key_file_path' in locals():
                    try:
                        os.unlink(key_file_path)
                    except Exception:
                        pass
            
            # Verify compressed file size on remote device
            self.operation.log_line("Verifying transferred compressed file...")
            result = self._execute_command(f"stat -c%s {shlex.quote(remote_compressed_path)} 2>/dev/null || wc -c < {shlex.quote(remote_compressed_path)}", timeout=60)
            remote_compressed_size = int(result.strip())
            
            if remote_compressed_size != len(compressed_data):
                raise RecoverableModemFailure(
                    f"Compressed file transfer verification failed: expected {len(compressed_data)} bytes, got {remote_compressed_size} bytes"
                )
            
            self.operation.log_line(f"Compressed firmware uploaded and verified: {remote_compressed_size} bytes")
            
            # Check if zstd is available on device before attempting decompression
            self.operation.log_line("Checking zstd availability on device...")
            try:
                self._execute_command("which zstd || command -v zstd", timeout=10)
                zstd_available = True
            except Exception:
                zstd_available = False

            if not zstd_available:
                # zstd not available on device — clean up compressed file and
                # fall back to plain SCP transfer
                self.operation.log_line(
                    "zstd not available on device; falling back to uncompressed transfer..."
                )
                self._cleanup_remote_file(remote_compressed_path)
                return self._transfer_firmware_plain(firmware_file, firmware_data)

            # Decompress firmware on device
            self.operation.log_line("Decompressing firmware on device...")
            decompress_cmd = f"zstd -d {shlex.quote(remote_compressed_path)} -o {shlex.quote(remote_path)} --rm"
            try:
                self._execute_command(decompress_cmd, timeout=180)
                self.operation.log_line("Firmware decompressed successfully")
            except Exception as e:
                # Clean up on decompression failure
                self._cleanup_remote_file(remote_compressed_path)
                raise RecoverableModemFailure(f"Firmware decompression failed: {e}")
            
            # Verify decompressed file size
            self.operation.log_line("Verifying decompressed firmware...")
            result = self._execute_command(f"stat -c%s {shlex.quote(remote_path)} 2>/dev/null || wc -c < {shlex.quote(remote_path)}", timeout=60)
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

    def _transfer_firmware_plain(self, firmware_file, firmware_data=None):
        """
        Transfer firmware file to the device via plain SCP (no compression).
        Used as fallback when zstd is not available on the target device.

        Returns:
            str: Remote path where firmware was uploaded
        """
        import tempfile
        import os
        import subprocess
        import hashlib

        remote_path = f"/tmp/modem_firmware_{int(time.time())}.bin"
        timeout = self._get_option("transfer_timeout", 600)

        if firmware_data is None:
            firmware_file.seek(0)
            firmware_data = firmware_file.read()

        file_size_mb = len(firmware_data) / (1024 * 1024)
        sha256_hash = hashlib.sha256(firmware_data)
        self.expected_checksum = sha256_hash.hexdigest()
        self.operation.log_line(f"OpenWISP calculated checksum (SHA256): {self.expected_checksum}")
        self.operation.log_line(f"Firmware size: {file_size_mb:.2f} MB")

        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp_file:
            tmp_file.write(firmware_data)
            tmp_file_path = tmp_file.name

        try:
            device = self.connection.device
            credentials = self.connection.credentials
            host = device.management_ip
            cred_params = credentials.params
            username = cred_params.get('username', 'root')
            password = cred_params.get('password')
            key = cred_params.get('key')
            port = cred_params.get('port', 22)

            scp_target = f"{username}@{host}:{remote_path}"
            scp_cmd = ["scp", "-O", "-P", str(port)]

            if key:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as key_file:
                    key_file.write(key)
                    key_file_path = key_file.name
                os.chmod(key_file_path, 0o600)
                scp_cmd.extend(["-i", key_file_path])
                self.operation.log_line("Using SSH key authentication")
            elif password:
                scp_cmd = ["sshpass", "-p", password] + scp_cmd
                self.operation.log_line("Using password authentication")
            else:
                raise Exception("No authentication credentials found (neither password nor key)")

            scp_cmd.extend([
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", f"ConnectTimeout={timeout}",
                tmp_file_path,
                scp_target,
            ])

            self.operation.log_line(f"Transferring firmware to {host}:{remote_path}...")
            self.operation.update_progress(15)

            process = subprocess.Popen(
                scp_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(timeout=timeout)

            if process.returncode != 0:
                error_msg = stderr.strip() if stderr else f"SCP exited with code {process.returncode}"
                raise Exception(f"SCP transfer failed: {error_msg}")

            self.operation.log_line("SCP transfer completed successfully")
            self.operation.update_progress(25)

        finally:
            try:
                os.unlink(tmp_file_path)
            except Exception:
                pass
            if 'key_file_path' in locals():
                try:
                    os.unlink(key_file_path)
                except Exception:
                    pass

        # Verify file size on remote device
        self.operation.log_line("Verifying transferred firmware...")
        result = self._execute_command(
            f"stat -c%s {shlex.quote(remote_path)} 2>/dev/null || wc -c < {shlex.quote(remote_path)}",
            timeout=60,
        )
        remote_size = int(result.strip())

        if remote_size != len(firmware_data):
            raise RecoverableModemFailure(
                f"File transfer verification failed: expected {len(firmware_data)} bytes, got {remote_size} bytes"
            )

        self.operation.log_line(f"Firmware uploaded and verified: {remote_size} bytes")
        return remote_path

    def _verify_checksum(self, remote_path, firmware_file):
        """
        Verify firmware checksum on the device by comparing with OpenWISP-side checksum.
        
        Args:
            remote_path: Path to firmware file on device
            firmware_file: Firmware file object from OpenWISP
        
        Returns:
            bool: True if checksum is valid
            
        Raises:
            RecoverableModemFailure: If checksums don't match (will trigger retry)
        """
        import hashlib
        
        try:
            # Calculate OpenWISP checksum from firmware file
            firmware_file.seek(0)
            firmware_data = firmware_file.read()
            sha256_hash = hashlib.sha256(firmware_data)
            openwisp_checksum = sha256_hash.hexdigest()
            self.operation.log_line(f"OpenWISP calculated checksum: {openwisp_checksum}")
            
            # Execute checksum verification command on device
            cmd = f"sha256sum {shlex.quote(remote_path)}"
            result = self._execute_command(cmd)
            
            # Log the device output (keep original OpenWISP format)
            self.operation.log_line(f"Firmware checksum: {result.strip()}")
            
            # Parse device checksum from output
            # Expected format: "Device firmware checksum - <checksum>  <filepath>"
            # Or standard sha256sum format: "<checksum>  <filepath>"
            device_checksum = None
            
            if "Device firmware checksum -" in result:
                # Custom format from device engineer
                parts = result.split(" - ")
                if len(parts) >= 2:
                    # Get checksum (first part after ' - ', before spaces)
                    device_checksum = parts[1].split()[0].strip()
            else:
                # Standard sha256sum format
                device_checksum = result.split()[0].strip()
            
            if not device_checksum:
                error_msg = "Failed to parse device checksum from output"
                logger.error(error_msg)
                self.operation.log_line(error_msg)
                raise RecoverableModemFailure(error_msg)
            
            self.operation.log_line(f"Device firmware checksum: {device_checksum}")
            
            # Compare checksums (case-insensitive)
            if device_checksum.lower() != openwisp_checksum.lower():
                error_msg = f"Checksum mismatch! Device: {device_checksum}, OpenWISP: {openwisp_checksum}"
                logger.error(error_msg)
                self.operation.log_line(error_msg)
                raise RecoverableModemFailure("Firmware checksum validation failed - will retry upgrade")
            
            self.operation.log_line("✓ Checksum validation successful - firmware integrity verified")
            return True
            
        except RecoverableModemFailure:
            raise
        except Exception as e:
            error_msg = f"Checksum verification failed: {e}"
            logger.error(error_msg)
            self.operation.log_line(error_msg)
            raise RecoverableModemFailure(error_msg)

    def _run_safe_update(self, remote_path, state_dir):
        """
        Run safe_update.sh on the device. The device will disconnect
        during the update process.
        """
        safe_update_path = self._get_option(
            "safe_update_path", "/usr/bin/safe_update.sh"
        )
        cmd = f"{safe_update_path} --state-dir {shlex.quote(state_dir)}"
        self.operation.log_line(f"Executing: {cmd}")

        try:
            self._execute_command(cmd, timeout=60, raise_on_error=False)
        except Exception:
            # Expected: device disconnects during update, SSH will drop
            pass

        self.operation.log_line(
            "safe_update.sh triggered - device is updating and disconnected"
        )

    def _reconnect_after_update(self):
        """
        Try reconnecting to device via SSH after the update.
        Retries every reconnect_interval seconds for reconnect_attempts times.

        Raises:
            ModemReconnectionFailed: If all reconnection attempts fail
        """
        interval = self._get_option("reconnect_interval", 120)
        max_attempts = self._get_option("reconnect_attempts", 10)

        for attempt in range(1, max_attempts + 1):
            self.operation.log_line(
                f"Reconnection attempt {attempt}/{max_attempts} "
                f"(waiting {interval}s)..."
            )
            time.sleep(interval)

            try:
                # Close existing connection and reconnect
                try:
                    self.connection.disconnect()
                except Exception:
                    pass
                self.connection.connect()
                if self._verify_connectivity():
                    self.operation.log_line(
                        f"Reconnected to device on attempt {attempt}"
                    )
                    return
            except Exception as e:
                logger.info(
                    f"Reconnection attempt {attempt} failed: {e}"
                )

        raise ModemReconnectionFailed(
            f"Device not responding after {max_attempts} reconnection attempts "
            f"({max_attempts * interval}s total)"
        )

    def _verify_update_status(self, state_dir):
        """
        Run verify_update.sh to check if the update succeeded or failed.
        If state is RUNNING, keeps polling every 60 seconds until
        it becomes SUCCESS or FAILED.

        Raises:
            RecoverableModemFailure: If update status is FAILED or polling exhausted
        """
        verify_path = self._get_option(
            "verify_update_path", "/usr/bin/verify_update.sh"
        )
        cmd = f"{verify_path} status --state-dir {shlex.quote(state_dir)}"
        poll_interval = 60  # Check every 60 seconds when RUNNING
        max_polls = 30  # Up to 30 minutes of polling

        for poll in range(1, max_polls + 1):
            self.operation.log_line(f"Executing: {cmd}")
            result = self._execute_command(cmd, timeout=60, raise_on_error=False)

            # Log the raw output
            for line in result.strip().split("\n"):
                if line.strip():
                    self.operation.log_line(f"verify_update: {line.strip()}")

            # Parse state from output
            state = None
            exit_code = None
            for line in result.strip().split("\n"):
                line = line.strip()
                if line.startswith("state="):
                    state = line.split("=", 1)[1].strip().upper()
                elif line.startswith("exit_code="):
                    exit_code = line.split("=", 1)[1].strip()

            if state == "SUCCESS":
                self.operation.log_line("Update verified: SUCCESS")
                return

            if state == "FAILED":
                error_msg = (
                    f"Modem firmware update FAILED on device "
                    f"(exit_code={exit_code})"
                )
                self.operation.log_line(error_msg)
                raise RecoverableModemFailure(error_msg)

            if state == "RUNNING":
                self.operation.log_line(
                    f"Update still RUNNING (poll {poll}/{max_polls}), "
                    f"waiting {poll_interval}s before next check..."
                )
                time.sleep(poll_interval)
                continue

            # Unknown or missing state
            error_msg = f"Unexpected update state: {state}"
            self.operation.log_line(error_msg)
            raise RecoverableModemFailure(error_msg)

        # Exhausted all polling attempts while still RUNNING
        error_msg = (
            f"Update still RUNNING after {max_polls} status checks "
            f"({max_polls * poll_interval}s total)"
        )
        self.operation.log_line(error_msg)
        raise RecoverableModemFailure(error_msg)

    def _read_uxfp_log(self, state_dir):
        """
        Read and log the UXFP log file from the device.
        """
        log_path = f"{state_dir}/modem.log"
        try:
            result = self._execute_command(
                f"cat {shlex.quote(log_path)}", timeout=30
            )
            self.operation.log_line(f"--- UXFP log ({log_path}) ---")
            for line in result.strip().split("\n"):
                if line.strip():
                    self.operation.log_line(line.strip())
            self.operation.log_line("--- End UXFP log ---")
        except Exception as e:
            logger.warning(f"Could not read UXFP log: {e}")
            self.operation.log_line(f"Warning: Could not read UXFP log: {e}")

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
            try:
                result = connector.exec_command(cmd, timeout=timeout)
            except Exception as e:
                # The SSH connector may raise an exception even for commands
                # that return output (e.g., non-zero exit code with stdout).
                # When raise_on_error=False, return the error message as output
                # so callers can parse it.
                if not raise_on_error:
                    error_output = str(e)
                    logger.info(
                        f"Command returned error (non-fatal): {cmd[:100]}..., "
                        f"output: {error_output}"
                    )
                    return error_output
                raise
            
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