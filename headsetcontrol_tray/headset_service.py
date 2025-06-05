import subprocess
import hid 
import logging
import re
import json

import os
import tempfile
from typing import Optional, List, Tuple, Dict, Any, TypedDict


from . import app_config
from .app_config import STEELSERIES_VID, TARGET_PIDS

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# --- Notes on HID Report Implementation (based on HID_RESEARCH.md) ---
# For Arctis Nova 7, most commands on the primary HID interface (interface 3, usage page 0xffc0, usage 0x0001)
# appear to start with a 0x00 byte when sent via hid_write in HeadsetControl.
# This 0x00 could be:
#   1. The Report ID for reports on this interface. If so, `_write_hid_report` should be called
#      with `report_id=0x00` and `data` being the rest of the command bytes.
#      `_read_hid_report` might also expect input reports to start with `0x00` if it's a Report ID,
#      and may need to strip it.
#   2. Part of an "unnumbered" report's data payload. In this case, `_write_hid_report`
#      might be called with `report_id=0` (or a convention for unnumbered) and `data` including the 0x00.
#
# The `python-hid` library's `device.write(data)` method:
#   - If the HID device uses numbered reports, `data[0]` is the Report ID.
#   - If it uses unnumbered reports, `data[0]` is the first byte of the actual data.
#
# Current `_write_hid_report(self, report_id: int, data: List[int], report_length: int = 64)`:
#   - If `report_id > 0`, it prepends it.
#   - If `report_id == 0` (as used in placeholder calls), it sends `data` as-is.
#
# This means:
#   - If `app_config.HID_REPORT_FIXED_FIRST_BYTE` (0x00) IS the report ID, calls should be:
#     `self._write_hid_report(app_config.HID_REPORT_FIXED_FIRST_BYTE, actual_command_bytes_after_0x00, ...)`
#   - If `0x00` is part of the data for an unnumbered report (or report ID 0 is implicit):
#     `self._write_hid_report(0, command_bytes_including_0x00, ...)`
#
# The HeadsetControl C code directly calls `hid_write(device_handle, buffer, size)` where `buffer` often starts with `0x00`.
# This suggests the second case is more likely for most commands (0x00 is part of the data, sent as unnumbered or report_id=0).
# The `HID_CMD_SAVE_SETTINGS = [0x06, 0x09]` is an exception and likely uses Report ID 0x06.
#
# The placeholder implementations below will generally assume `report_id=0` for `_write_hid_report`
# when the command from `app_config` already starts with `HID_REPORT_FIXED_FIRST_BYTE`.
# For `HID_CMD_SAVE_SETTINGS`, `report_id=0x06` would be used.

# Format VID and PIDs as 4-digit lowercase hex strings
VID_HEX = f"{STEELSERIES_VID:04x}"
RULE_LINES = [
    f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{VID_HEX}", ATTRS{{idProduct}}=="{pid:04x}", TAG+="uaccess"'
    for pid in TARGET_PIDS
]
UDEV_RULE_CONTENT = "\n".join(RULE_LINES)
UDEV_RULE_FILENAME = "99-steelseries-headsets.rules"

# Define BatteryDetails TypedDict
class BatteryDetails(TypedDict):
    level: Optional[int]
    status_text: Optional[str]

class HeadsetService:
    """
    Service class to interact with the SteelSeries headset via CLI and HID.
    """
    def __init__(self):
        self.hid_device: Optional[hid.Device] = None
        self.device_path: Optional[bytes] = None
        self.udev_setup_details = None # Initialize details for udev rule setup
        self.headsetcontrol_available: bool = False # Default to False

        # Check for headsetcontrol availability
        try:
            # Use a non-disruptive command like --version or --help
            # Ensure check=True is used to raise CalledProcessError on non-zero exit codes
            # which might indicate headsetcontrol is present but not fully functional for this command.
            # However, --version is usually safe.
            process = subprocess.run(['headsetcontrol', '--version'], capture_output=True, text=True, check=True)
            if process.returncode == 0 and "HeadsetControl" in process.stdout: # Basic check of output
                self.headsetcontrol_available = True
                logger.info("HeadsetService: `headsetcontrol` CLI tool is available.")
            else:
                # This case might occur if --version exists but output is unexpected or error code not 0
                logger.warning(f"HeadsetService: `headsetcontrol --version` ran with code {process.returncode} or unexpected output. Assuming unavailable.")
                self.headsetcontrol_available = False
        except FileNotFoundError:
            logger.info("HeadsetService: `headsetcontrol` CLI tool not found. Direct HID will be primary if interface is available.")
            self.headsetcontrol_available = False
        except subprocess.CalledProcessError as e:
            # This catches non-zero exit codes if check=True
            logger.warning(f"HeadsetService: `headsetcontrol --version` failed (exit code {e.returncode}): {e.stderr.strip()}. Assuming unavailable.")
            self.headsetcontrol_available = False
        except Exception as e: # Catch any other unexpected errors during the check
            logger.error(f"HeadsetService: An unexpected error occurred while checking for `headsetcontrol`: {e}. Assuming unavailable.")
            self.headsetcontrol_available = False

        logger.debug("HeadsetService initialized. Attempting initial HID connection.")
        self._connect_hid_device()

    # _check_udev_rules method removed

    def _create_udev_rules(self) -> bool:
        """
        Creates the udev rule file in a temporary location and instructs the user.
        Stores information about the created temporary file if successful.
        """
        final_rules_path_str = os.path.join("/etc/udev/rules.d/", UDEV_RULE_FILENAME)
        logger.info(f"Attempting to guide user for udev rule creation for {final_rules_path_str}")
        self.udev_setup_details = None # Reset in case of prior failure

        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="headsetcontrol_") as tmp_file:
                temp_file_name = tmp_file.name
                tmp_file.write(UDEV_RULE_CONTENT + "\n") # Add a newline for good measure

            # Store details
            self.udev_setup_details = {
                "temp_file_path": temp_file_name,
                "final_file_path": final_rules_path_str,
                "rule_filename": UDEV_RULE_FILENAME
            }
            logger.info(f"Successfully wrote udev rule content to temporary file: {temp_file_name}")
            logger.info("--------------------------------------------------------------------------------")
            logger.info("ACTION REQUIRED: To complete headset setup, please run the following commands:")
            logger.info(f"1. Copy the rule file: sudo cp \"{temp_file_name}\" \"{final_rules_path_str}\"")
            logger.info("2. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger")
            logger.info("3. Replug your SteelSeries headset.")
            logger.info(f"(The temporary file {temp_file_name} can be deleted after copying.)")
            logger.info("--------------------------------------------------------------------------------")
            return True
        except IOError as e:
            logger.error(f"Could not write temporary udev rule file: {e}")
            self.udev_setup_details = None # Ensure it's None on failure
            return False
        except Exception as e_global: # Catch any other unexpected errors during temp file handling
            logger.error(f"An unexpected error occurred during temporary udev rule file creation: {e_global}")
            self.udev_setup_details = None # Ensure it's None on failure
            return False

    def _connect_hid_device(self) -> bool:
        """Attempts to connect to the headset via HID by trying suitable interfaces."""
        # Udev check removed from here

        if self.hid_device: 
            logger.debug("_connect_hid_device: Already connected.")
            return True
        
        logger.debug(f"_connect_hid_device: Trying to connect. Target PIDs: {app_config.TARGET_PIDS}")
        try:
            devices_enum = hid.enumerate(STEELSERIES_VID, 0) # Use imported STEELSERIES_VID
            logger.debug(f"Found {len(devices_enum)} SteelSeries VID devices during enumeration.")
        except Exception as e_enum: 
            logger.error(f"Error enumerating HID devices: {e_enum}")
            devices_enum = []
            
        potential_devices_to_try = []
        for dev_info in devices_enum:
            logger.debug(f"  Enumerated device: PID=0x{dev_info['product_id']:04x}, Release=0x{dev_info['release_number']:04x}, "
                         f"Interface={dev_info.get('interface_number', 'N/A')}, UsagePage=0x{dev_info.get('usage_page', 0):04x}, "
                         f"Usage=0x{dev_info.get('usage', 0):04x}, Path={dev_info['path'].decode('utf-8', errors='replace')}, "
                         f"Product='{dev_info.get('product_string', 'N/A')}'")
            if dev_info['product_id'] in TARGET_PIDS: # Use imported TARGET_PIDS
                logger.debug(f"    Device matches target PID 0x{dev_info['product_id']:04x}. Adding to potential list.")
                potential_devices_to_try.append(dev_info)

        if not potential_devices_to_try:
            logger.debug("_connect_hid_device: No devices found matching target PIDs after enumeration (normal if headset is off).")
            return False

        def sort_key(d_info):
            # Prioritize exact match for Arctis Nova 7 communication interface
            if d_info['vendor_id'] == app_config.STEELSERIES_VID and \
               d_info['product_id'] in app_config.TARGET_PIDS and \
               d_info.get('interface_number') == app_config.HID_REPORT_INTERFACE and \
               d_info.get('usage_page') == app_config.HID_REPORT_USAGE_PAGE and \
               d_info.get('usage') == app_config.HID_REPORT_USAGE_ID:
                logger.debug(f"  SortKey: Prioritizing exact Arctis Nova 7 interface (0) for PID 0x{d_info.get('product_id'):04x}")
                return -2 # Highest priority

            # Original Arctis Nova 7 (0x2202) interface 0 prioritization (keep as fallback)
            if d_info.get('product_id') == 0x2202 and d_info.get('interface_number') == 0:
                logger.debug(f"  SortKey: Prioritizing interface 0 for PID 0x{d_info.get('product_id'):04x} (-1)")
                return -1

            # Existing general prioritization (adjust their return values to be lower priority)
            if d_info.get('interface_number') == 3: # This was interface 3, which matches our specific one.
                                                    # The above exact match is more specific if usage page/id also match.
                logger.debug(f"  SortKey: Prioritizing interface 3 (generic) for PID 0x{d_info.get('product_id'):04x} (0)")
                return 0
            if d_info.get('usage_page') == 0xFFC0: # This was usage page 0xFFC0
                logger.debug(f"  SortKey: Prioritizing usage page 0xFFC0 (generic) for PID 0x{d_info.get('product_id'):04x} (1)")
                return 1  

            logger.debug(f"  SortKey: Default priority 2 for PID 0x{d_info.get('product_id'):04x}, Interface {d_info.get('interface_number', 'N/A')}, UsagePage 0x{d_info.get('usage_page',0):04x}")
            return 2

        potential_devices_to_try.sort(key=sort_key)
        logger.debug(f"Sorted potential devices to try: {[(d['path'].decode('utf-8', errors='replace'), d.get('interface_number','N/A'), d.get('usage_page',0)) for d in potential_devices_to_try]}")
        
        for dev_info_to_try in potential_devices_to_try:
            h_temp = None 
            logger.debug(f"  Attempting to open path: {dev_info_to_try['path'].decode('utf-8', errors='replace')} "
                         f"(Interface: {dev_info_to_try.get('interface_number', 'N/A')}, "
                         f"UsagePage: 0x{dev_info_to_try.get('usage_page', 0):04x}, "
                         f"PID: 0x{dev_info_to_try['product_id']:04x})")
            try:
                h_temp = hid.Device(path=dev_info_to_try['path'])
                
                self.hid_device = h_temp
                self.device_path = dev_info_to_try['path']
                # This log indicates a low-level HID path was opened, not necessarily full headset function.
                logger.debug(f"Low-level HID device path opened: {dev_info_to_try.get('product_string', 'N/A')} "
                            f"on interface {dev_info_to_try.get('interface_number', -1)} "
                            f"path {dev_info_to_try['path'].decode('utf-8', errors='replace')}")
                return True
            except Exception as e_open: 
                logger.warning(f"    Failed to open HID device path {dev_info_to_try['path'].decode('utf-8', errors='replace')}: {e_open}")
                if h_temp: 
                    try:
                        h_temp.close() 
                    except Exception: 
                        pass 
                continue 
        
        self.hid_device = None 
        self.device_path = None

        # If loop finishes and hid_device is still None, no device was connected.
        # This is where we now trigger the udev rule creation if needed.
        if self.hid_device is None:
            logger.warning("Failed to connect to any suitable HID interface for the headset. Udev rules might be missing or incorrect.")
            self._create_udev_rules() # Prepare instructions and populate self.udev_setup_details

        logger.debug("_connect_hid_device: No suitable HID device interface found or all attempts to open failed (if hid_device is None).")
        return False

    def _ensure_hid_connection(self) -> bool:
        if not self.hid_device:
            logger.debug("_ensure_hid_connection: No HID device, attempting to connect.")
            return self._connect_hid_device()
        # If hid_device exists, we assume it's open. headsetcontrol will verify functionality.
        return True


    def close(self) -> None:
        if self.hid_device:
            logger.debug("Closing HID device.")
            try:
                self.hid_device.close()
            except Exception as e: 
                logger.warning(f"Exception while closing HID device: {e}")
            self.hid_device = None
            self.device_path = None
        else:
            logger.debug("Close called, but no HID device was open.")


    def _execute_headsetcontrol(self, args: List[str]) -> Tuple[bool, str]:
        """Executes headsetcontrol CLI tool."""
        cmd_str = ' '.join(['headsetcontrol'] + args)
        logger.debug(f"Executing headsetcontrol: {cmd_str}")
        try:
            process = subprocess.run(['headsetcontrol'] + args, capture_output=True, text=True, check=True)
            logger.debug(f"headsetcontrol output for '{cmd_str}': {process.stdout.strip()}")
            return True, process.stdout.strip()
        except FileNotFoundError:
            logger.error("headsetcontrol command not found. Please ensure it is installed and in PATH.")
            return False, "headsetcontrol not found. Please install it."
        except subprocess.CalledProcessError as e:
            # For '--connected', a non-zero exit code is expected if not connected, stderr might be empty.
            # For other commands, a non-zero exit usually means an actual error.
            if '--connected' not in args:
                 logger.error(f"headsetcontrol error for '{cmd_str}' (stderr): {e.stderr.strip()}")
            else:
                 logger.debug(f"headsetcontrol --connected indicated device not connected (exit code {e.returncode}). stderr: {e.stderr.strip()}")
            return False, f"headsetcontrol error: {e.stderr.strip()}"

    def _get_headset_device_json(self) -> Optional[Dict[str, Any]]:
        """Gets the first device object from 'headsetcontrol -o json'."""
        logger.debug("Trying CLI method for status ('headsetcontrol -o json').")
        success_json, output_json = self._execute_headsetcontrol(['-o', 'json'])
        if success_json:
            try:
                data = json.loads(output_json)
                if "devices" in data and isinstance(data["devices"], list) and len(data["devices"]) > 0:
                    # Assuming the first device is the target
                    return data["devices"][0]
                else:
                    logger.warning(f"'devices' key missing, not list, or empty in JSON output: {data}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from headsetcontrol: {e}. Output was: {output_json}")
        else:
             logger.warning(f"Failed to get status from 'headsetcontrol -o json'. Output was: {output_json}")
        return None


    def _write_hid_report(self, report_id: int, data: List[int], report_length: int = 64) -> bool:
        """
        Writes a report to the HID device.
        Prepends report_id if it's > 0.
        Pads data to report_length.

        The `report_id` is prefixed to `data` if `report_id > 0`.
        The combined message is then passed to `self.hid_device.write()`.
        This method is intended for sending command/control data to the headset
        once the correct report IDs and data structures are known.
        """
        if not self._ensure_hid_connection() or not self.hid_device: # Check low-level first
            logger.warning("_write_hid_report: No HID device connected (low-level).")
            return False
        
        # Additional check for functional connection might be needed if headsetcontrol is primary
        # For now, assume if HID is open, writes can be attempted. Failures will be caught.

        # TODO: Determine if report_length padding is needed here or if hid.write handles it.
        # For feature reports, the report_id is often included as the first byte of the buffer passed to hid.write().
        # For output reports on an interrupt OUT endpoint, it might also be the first byte, or handled by the endpoint itself.
        payload = bytes(data)
        if report_id > 0: 
            final_report = bytes([report_id]) + payload
        else: 
            final_report = payload
        
        logger.debug(f"Writing HID report: ID={report_id}, Data={final_report.hex()}")
        try:
            bytes_written = self.hid_device.write(final_report) # This might fail if headset is off
            logger.debug(f"Bytes written: {bytes_written}")
            if bytes_written <= 0: # Some HID libraries might return 0 or -1 on error
                logger.warning(f"HID write returned {bytes_written}, closing potentially stale HID handle.")
                self.close()
                return False
            return True
        except Exception as e: 
            logger.error(f"HID write error: {e}. Closing potentially stale HID handle.")
            self.close() 
            return False

    def _read_hid_report(self, report_id_to_request: Optional[int] = None, report_length: int = 64, timeout_ms: int = 1000) -> Optional[List[int]]:
        """
        Reads a report from the HID device.
        If report_id_to_request is provided, it's for Feature Reports.

        If `report_id_to_request` is provided (typically for Feature Reports), it is sent
        to the device using `self.hid_device.get_feature_report()`. Otherwise,
        `self.hid_device.read()` is used for Input Reports (typically from Interrupt IN endpoint).

        This method is intended for reading status, configuration, or responses
        from the headset once report IDs and data structures are known.
        The interpretation of the returned `List[int]` depends on the specific
        report being read.
        """
        if not self._ensure_hid_connection() or not self.hid_device: # Check low-level first
            logger.warning("_read_hid_report: No HID device connected (low-level).")
            return None
        
        logger.debug(f"Reading HID report: ReportIDToRequest={report_id_to_request}, Length={report_length}, Timeout={timeout_ms}ms")
        try:
            data: Optional[List[int]] = None
            if report_id_to_request is not None:
                # For Feature Reports, report_id_to_request usually includes the actual report ID.
                # The buffer size should be report_length + 1 if report_id_to_request is prepended by some libraries,
                # but python-hid/hidapi expects the report_id as a separate first argument for get_feature_report.
                # However, hid.Device does not have get_feature_report. This needs hid.FeatureReport(device, id)
                # This part of python-hid is a bit confusing.
                # For now, assuming 'read' is for interrupt/input reports and feature reports need more specific handling.
                # If we were to use get_feature_report, it might look something like:
                # report_data = bytearray([report_id_to_request] + [0] * report_length)
                # bytes_read = self.hid_device.get_feature_report(report_data, len(report_data))
                # data = list(report_data[:bytes_read])
                # This needs to be verified with how python-hid handles feature reports.
                # For now, we'll assume report_id_to_request means we are expecting an Input report
                # that *starts* with this ID if it's a numbered report.
                # The current hid.Device.read() reads from an IN endpoint.
                logger.debug(f"Attempting to read Input report, expecting report ID {report_id_to_request} if numbered.")
                raw_data = self.hid_device.read(report_length, timeout_ms=timeout_ms)
                if raw_data and report_id_to_request is not None and raw_data[0] == report_id_to_request:
                    data = raw_data[1:] # Strip the report ID if it's present and matches
                    logger.debug(f"Stripped report ID {report_id_to_request} from received data.")
                elif raw_data and report_id_to_request is None:
                    data = raw_data # Unnumbered report or ID stripping not requested
                else:
                    data = raw_data # Return raw data if ID doesn't match or not expecting one
            else:
                # Standard input report read
                data = self.hid_device.read(report_length, timeout_ms=timeout_ms)

            if data:
                logger.debug(f"HID read data: {bytes(data).hex()}")
                return list(data)
            else:
                logger.debug("HID read no data (timeout or empty report).")
                return None # Could indicate issue, or just no data for that report.
        except Exception as e: 
            logger.error(f"HID read error: {e}. Closing potentially stale HID handle.")
            self.close() 
            return None

    def is_device_connected(self) -> bool:
        if self.headsetcontrol_available:
            logger.debug("is_device_connected: `headsetcontrol` is available, using CLI for robust connection check.")

            # Original Step 1: Basic HID interface check. If this fails, it's unlikely headsetcontrol will find it.
            if not self._ensure_hid_connection():
                logger.warning("is_device_connected (CLI mode): _ensure_hid_connection failed (cannot open a relevant HID path). Device likely disconnected.")
                # self.close() is called by _ensure_hid_connection if it fails to fully connect.
                return False

            # Original Step 2: Use headsetcontrol -o json to verify functional connection.
            device_info = self._get_headset_device_json()

            if device_info is None:
                # This means headsetcontrol -o json failed or found no devices.
                logger.debug("is_device_connected (CLI mode): _get_headset_device_json() returned None (headsetcontrol found no functional device). Closing our HID handle.")
                self.close() # Close our HID handle as headsetcontrol confirms no functional device.
                return False

            # If device_info is present, headsetcontrol sees a functional device.
            logger.debug("is_device_connected (CLI mode): _ensure_hid_connection was OK and _get_headset_device_json() successful.")
            return True
        else: # headsetcontrol is NOT available
            logger.info("is_device_connected: `headsetcontrol` is NOT available. Relying solely on direct HID interface accessibility for commands.")
            # If headsetcontrol is not available, we rely on being able to open our command HID interface.
            # _ensure_hid_connection() attempts to connect using sort_key that prioritizes the command interface.
            if self._ensure_hid_connection() and self.hid_device is not None:
                # This means we successfully opened a HID path that should be our command interface.
                logger.info("is_device_connected (HID mode): Successfully ensured HID connection to a potential command interface.")
                return True
            else:
                logger.warning("is_device_connected (HID mode): Failed to ensure HID connection to any suitable command interface.")
                # self.close() is called by _ensure_hid_connection if it fails.
                return False


    # --- Public API ---

    def get_battery_level(self) -> Optional[int]:
        logger.debug("get_battery_level: Attempting via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get('headset_online') and status.get('battery_percent') is not None:
            logger.verbose(f"Battery level from HID: {status['battery_percent']}%")
            return status['battery_percent']

        # Fallback only if headsetcontrol is available
        if self.headsetcontrol_available:
            logger.warning("get_battery_level: Could not retrieve via HID or HID reported offline. Falling back to headsetcontrol.")
            if not self.is_device_connected(): # is_device_connected itself now respects headsetcontrol_available
                logger.debug("get_battery_level (fallback): Device not connected per is_device_connected, skipping CLI call.")
                return None

            logger.debug("Attempting to get battery level (fallback to headsetcontrol CLI).")
        success_b, output_b = self._execute_headsetcontrol(['-b'])

        if success_b:
            if "BATTERY_UNAVAILABLE" in output_b:
                logger.debug("Battery status is UNAVAILABLE via headsetcontrol -b fallback.")
                return None

            match = re.search(r"Level:\s*(\d+)%", output_b)
            if match:
                level = int(match.group(1))
                logger.verbose(f"Battery level from CLI (-b fallback, regex parse): {level}%")
                return level
            elif output_b.isdigit(): 
                logger.verbose(f"Battery level from CLI (-b, direct parse): {output_b}%")
                return int(output_b)
            else: # Output changed, e.g. "Status: BATTERY_UNAVAILABLE"
                logger.warning(f"Could not parse battery level from 'headsetcontrol -b' output: {output_b}")
        
        # Fallback to JSON if direct -b fails to parse, but only if device is still seen as connected
        # (which it should be if we reached here, unless -b itself caused a disconnect detection not yet reflected)
        if self.is_device_connected(): # Re-check as -b might have issues if device just went off
            device_data = self._get_headset_device_json()
            if device_data and "battery" in device_data and isinstance(device_data["battery"], dict):
                battery_info = device_data["battery"]
                if "level" in battery_info and isinstance(battery_info["level"], int):
                    level = battery_info["level"]
                    logger.verbose(f"Battery level from CLI (-o json): {level}%")
                    return level
                else:
                    logger.warning(f"'level' key missing or not int in battery_info (JSON): {battery_info}")
            elif not device_data:
                     logger.warning("get_battery_level (fallback): Could not get device_data for JSON fallback.")
        else:
            logger.warning("get_battery_level: Direct HID failed and headsetcontrol is not available.")
        
        return None

    # --- Hypothetical HID-based methods (for future implementation) ---

    def _get_parsed_status_hid(self) -> Optional[Dict[str, Any]]:
        """
        Gets and parses the combined status report (battery, chatmix)
        via direct HID communication.
        """
        logger.debug("Attempting _get_parsed_status_hid.") # Changed from info to debug for less noise
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_get_parsed_status_hid: No HID device connected or connection failed.")
            return None

        # 1. Send the status request command.
        # Based on HID_RESEARCH.md and headsetcontrol C code:
        # Most commands (like GET_STATUS) starting with HID_REPORT_FIXED_FIRST_BYTE (0x00)
        # are likely sent as unnumbered reports or where Report ID 0 is implicit.
        # _write_hid_report with report_id=0 sends the data payload as-is.
        command_payload = app_config.HID_CMD_GET_STATUS
        success_write = self._write_hid_report(
            report_id=0, # Assuming 0x00 is part of data for unnumbered/implicit ID 0 report
            data=command_payload,
            report_length=len(command_payload) # Send minimal length, device should ignore padding if any
        )

        if not success_write:
            logger.warning("_get_parsed_status_hid: Failed to write HID status request command.")
            # self.close() # Consider if closing is appropriate on write failure
            return None

        # 2. Read the response.
        # The response is an 8-byte input report.
        response_data = self._read_hid_report(
            report_id_to_request=None, # Not a Feature Report, reading an Input report.
                                       # If input reports were numbered and started with an ID (e.g. 0x00),
                                       # _read_hid_report's logic for stripping it would apply.
                                       # For Arctis Nova 7, status response doesn't seem to be prefixed by its own ID.
            report_length=app_config.HID_INPUT_REPORT_LENGTH_STATUS,
            timeout_ms=1000  # Increased timeout slightly for reliability
        )

        if not response_data:
            logger.warning("_get_parsed_status_hid: No response data from HID device.")
            # self.close() # Consider closing if read fails critically
            return None

        if len(response_data) < app_config.HID_INPUT_REPORT_LENGTH_STATUS:
            logger.warning(
                f"_get_parsed_status_hid: Incomplete response. Expected {app_config.HID_INPUT_REPORT_LENGTH_STATUS} bytes, got {len(response_data)}: {response_data}"
            )
            return None

        # 3. Parse the response.
        parsed_status = {'headset_online': True} # Assume online if we got this far

        # Battery Level
        raw_battery_level = response_data[app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE]
        if raw_battery_level == 0x00: parsed_status['battery_percent'] = 0
        elif raw_battery_level == 0x01: parsed_status['battery_percent'] = 25
        elif raw_battery_level == 0x02: parsed_status['battery_percent'] = 50
        elif raw_battery_level == 0x03: parsed_status['battery_percent'] = 75
        elif raw_battery_level == 0x04: parsed_status['battery_percent'] = 100
        else:
            logger.warning(f"_get_parsed_status_hid: Unknown raw battery level: {raw_battery_level}")
            parsed_status['battery_percent'] = None

        # Battery Status
        raw_battery_status = response_data[app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE]
        if raw_battery_status == 0x00:  # Offline / Not connected
            logger.info("_get_parsed_status_hid: Headset reported offline by status byte.")
            # This is a specific state reported by the headset itself.
            parsed_status['battery_charging'] = None
            parsed_status['headset_online'] = False # Explicitly set based on device report
            # Do not return None here, let the caller decide based on 'headset_online'
        elif raw_battery_status == 0x01:  # Charging
            parsed_status['battery_charging'] = True
        else:  # Discharging / Available (e.g., 0x02, 0x03, etc.)
            parsed_status['battery_charging'] = False

        # ChatMix (only parse if headset is considered online)
        if parsed_status['headset_online']:
            raw_game = response_data[app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE]
            raw_chat = response_data[app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE]

            # Mapping from headsetcontrol: map(value, 0, 100, 0, 64) for game, map(value, 0, 100, 0, -64) for chat
            # Approximate linear map: (val / 100.0) * 64.0
            # Ensure raw_game and raw_chat are within 0-100 to prevent unexpected values.
            raw_game_clamped = max(0, min(100, raw_game))
            raw_chat_clamped = max(0, min(100, raw_chat))

            mapped_game = int((raw_game_clamped / 100.0) * 64.0)
            mapped_chat = int((raw_chat_clamped / 100.0) * -64.0) # chat part is negative in formula
            chatmix_value = 64 - (mapped_chat + mapped_game)
            parsed_status['chatmix'] = max(0, min(128, chatmix_value)) # Clamp to 0-128
        else:
            parsed_status['chatmix'] = None

        logger.debug(f"_get_parsed_status_hid: Parsed status: {parsed_status}")
        return parsed_status

    # Add example public methods that would use _get_parsed_status_hid()
    def get_battery_level_hid(self) -> Optional[int]:
        logger.debug("get_battery_level_hid: Attempting to get battery via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get('headset_online') and status.get('battery_percent') is not None:
            return status['battery_percent']
        logger.warning("get_battery_level_hid: Could not retrieve battery level via HID.")
        return None

    def get_chatmix_hid(self) -> Optional[int]:
        logger.debug("get_chatmix_hid: Attempting to get chatmix via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get('headset_online') and status.get('chatmix') is not None:
            return status['chatmix']
        logger.warning("get_chatmix_hid: Could not retrieve chatmix via HID.")
        return None

    def is_charging_hid(self) -> Optional[bool]: # Renamed from is_charging
        """Checks if the headset is currently charging using HID.""" # Docstring added
        logger.debug("is_charging_hid: Attempting to get charging status via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get('headset_online') and status.get('battery_charging') is not None:
            return status['battery_charging']
        logger.warning("is_charging_hid: Could not retrieve charging status via HID.")
        return None

    def get_chatmix_value(self) -> Optional[int]:
        logger.debug("get_chatmix_value: Attempting via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get('headset_online') and status.get('chatmix') is not None:
            logger.verbose(f"ChatMix value from HID: {status['chatmix']}")
            return status['chatmix']

        if self.headsetcontrol_available:
            logger.warning("get_chatmix_value: Could not retrieve via HID or HID reported offline. Falling back to headsetcontrol.")
            if not self.is_device_connected():
                logger.debug("get_chatmix_value (fallback): Device not connected, skipping CLI call.")
                return None

            logger.debug("Attempting to get ChatMix value (fallback to headsetcontrol CLI).")
            device_data = self._get_headset_device_json() # Relies on headsetcontrol
            if device_data and "chatmix" in device_data:
                chatmix_val = device_data["chatmix"]
                if isinstance(chatmix_val, (int, float)):
                    chatmix_int = int(chatmix_val)
                    logger.verbose(f"ChatMix value from CLI (-o json): {chatmix_int}")
                    return chatmix_int
                else:
                    logger.warning(f"'chatmix' value is not a number in device_data (JSON): {chatmix_val}")
            elif not device_data:
                 logger.warning("get_chatmix_value (fallback): Could not get device_data for JSON.")
        else:
            logger.warning("get_chatmix_value: Direct HID failed and headsetcontrol is not available.")

        return None

    def is_charging(self) -> Optional[bool]:
        """Checks if the headset is currently charging."""
        logger.debug("is_charging: Attempting via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get('headset_online') and status.get('battery_charging') is not None:
            logger.verbose(f"Charging status from HID: {status['battery_charging']}")
            return status['battery_charging']

        if self.headsetcontrol_available:
            logger.warning("is_charging: Could not retrieve via HID or HID reported offline. Falling back to headsetcontrol.")
            if not self.is_device_connected():
                 logger.debug("is_charging (fallback): Device not connected.")
                 return None

            device_data = self._get_headset_device_json() # Relies on headsetcontrol
            if device_data and "battery" in device_data and isinstance(device_data["battery"], dict):
                battery_info = device_data["battery"]
                if "charging" in battery_info and isinstance(battery_info["charging"], bool):
                    logger.verbose(f"Charging status from headsetcontrol JSON: {battery_info['charging']}")
                    return battery_info["charging"]
                if "status" in battery_info and isinstance(battery_info["status"], str):
                    is_charging_str = "charging" in battery_info["status"].lower()
                    logger.verbose(f"Charging status from headsetcontrol JSON (string parse): {is_charging_str}")
                    return is_charging_str
            logger.debug("is_charging (fallback): Could not determine charging status from headsetcontrol JSON.")
        else:
            logger.warning("is_charging: Direct HID failed and headsetcontrol is not available.")

        return None

    def get_sidetone_level(self) -> Optional[int]:
        # logger.debug("get_sidetone_level: Using headsetcontrol. Direct HID implementation pending configuration.") # This log is still relevant
        if not self.is_device_connected():
            logger.debug("get_sidetone_level: Device not connected, skipping.")
            return None
        device_data = self._get_headset_device_json()
        if device_data and "sidetone" in device_data:
            sidetone_val = device_data["sidetone"]
            if isinstance(sidetone_val, int):
                logger.verbose(f"Sidetone level from CLI (-o json): {sidetone_val}")
                return sidetone_val
            else:
                logger.warning(f"Sidetone value from JSON is not an int: {sidetone_val}")
        elif not device_data:
            logger.warning("get_sidetone_level: Could not get device_data for JSON.")
        return None 

    def set_sidetone_level(self, level: int) -> bool:
        logger.debug(f"set_sidetone_level: Attempting to set level to {level} via direct HID.")

        # Sanitize input level just in case, though HID mapping handles ranges.
        level = max(0, min(128, level))

        if self._set_sidetone_level_hid(level):
            return True

        if self.headsetcontrol_available:
            logger.warning(f"set_sidetone_level: Failed to set sidetone to {level} via HID. Falling back to headsetcontrol.")
            # is_device_connected call here is mostly for logging consistency if HID failed due to disconnect
            if not self.is_device_connected():
                logger.warning("set_sidetone_level (fallback): Device not connected, cannot set via CLI.")
                return False

            logger.info(f"Setting sidetone level to {level} (fallback to headsetcontrol CLI).")
            success_hc, _ = self._execute_headsetcontrol(['-s', str(level)])
            if not success_hc:
                logger.error(f"Failed to set sidetone level to {level} using headsetcontrol.")
            return success_hc
        else:
            logger.warning(f"set_sidetone_level: Direct HID failed for level {level} and headsetcontrol is not available.")
            return False

    def _set_sidetone_level_hid(self, level: int) -> bool:
        """
        Sets sidetone level via direct HID communication.
        Returns True on success, False on failure.
        """
        logger.debug(f"Attempting _set_sidetone_level_hid to {level}.")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_set_sidetone_level_hid: No HID device connected or connection failed.")
            return False

        # 1. Map the level (0-128) to hardware value (0-3)
        # Mapping from headsetcontrol: 0-25->0, 26-50->1, 51-75->2, >75->3
        mapped_value = 0
        # Refined mapping based on app_config comments (0-25->0x0, 26-50->0x1, 51-75->0x2, >75->0x3)
        # Sidetone levels in app_config.SIDETONE_OPTIONS might be a better source for steps.
        # For now, using the direct mapping from headsetcontrol C code:
        if level < 26: mapped_value = 0x00
        elif level < 51: mapped_value = 0x01
        elif level < 76: mapped_value = 0x02
        else: mapped_value = 0x03
        logger.debug(f"_set_sidetone_level_hid: Input level {level} mapped to hardware value {mapped_value}.")

        # 2. Prepare the command
        # Command is [HID_REPORT_FIXED_FIRST_BYTE, 0x39, mapped_value]
        command_payload = list(app_config.HID_CMD_SET_SIDETONE_PREFIX) # Creates a mutable copy [0x00, 0x39]
        command_payload.append(mapped_value)

        success = self._write_hid_report(
            report_id=0, # Assuming 0x00 is part of data for unnumbered/implicit ID 0 report
            data=command_payload,
            report_length=len(command_payload)
        )

        if success:
            logger.info(f"_set_sidetone_level_hid: Successfully sent command for level {level} (mapped: {mapped_value}).")
            # Arctis Nova 7 sidetone does not seem to require a separate save command based on headsetcontrol.
        else:
            logger.warning(f"_set_sidetone_level_hid: Failed to send command for level {level}.")
            # self.close() # Consider if closing is appropriate on write failure
        return success

    def _set_inactive_timeout_hid(self, minutes: int) -> bool:
        """
        Sets inactive timeout via direct HID communication.
        Returns True on success, False on failure.
        """
        logger.debug(f"Attempting _set_inactive_timeout_hid to {minutes} minutes.")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_set_inactive_timeout_hid: No HID device connected or connection failed.")
            return False

        # Validate minutes (0-90 as per headsetcontrol help text for this type of device)
        # The raw command might support more, but stick to known safe values.
        if not (0 <= minutes <= 90):
            logger.warning(f"_set_inactive_timeout_hid: Invalid value for minutes ({minutes}). Must be 0-90.")
            # Consider if this should return False or raise ValueError,
            # For consistency with current set_inactive_timeout, it just logs and sends.
            # Let's clamp it to be safe for the HID command.
            # However, the original set_inactive_timeout also clamps.
            # The C code for Arctis Nova 7 doesn't show explicit range checks for the byte value itself,
            # but higher level headsetcontrol CLI does.
            # For direct HID, it's good practice to validate/clamp if the hardware range is known.
            # Assuming 'minutes' byte can take 0-255, but functional range is 0-90.
            # We'll rely on the public method's clamping for now.
            pass


        # Prepare the command: [HID_REPORT_FIXED_FIRST_BYTE, 0xa3, minutes]
        command_payload = list(app_config.HID_CMD_SET_INACTIVE_TIME_PREFIX) # Creates [0x00, 0xa3]
        command_payload.append(minutes)

        success = self._write_hid_report(
            report_id=0, # Assuming 0x00 is part of data for unnumbered/implicit ID 0 report
            data=command_payload,
            report_length=len(command_payload)
        )

        if success:
            logger.info(f"_set_inactive_timeout_hid: Successfully sent command for {minutes} minutes.")
            # Based on headsetcontrol C code for Arctis Nova 7, no separate save command needed for this.
        else:
            logger.warning(f"_set_inactive_timeout_hid: Failed to send command for {minutes} minutes.")
            # self.close() # Consider if closing is appropriate on write failure
        return success

    def get_inactive_timeout(self) -> Optional[int]:
        if not self.is_device_connected():
            logger.debug("get_inactive_timeout: Device not connected, skipping.")
            return None
        device_data = self._get_headset_device_json()
        if device_data and "inactive_time" in device_data: 
            timeout_val = device_data["inactive_time"]
            if isinstance(timeout_val, int):
                logger.verbose(f"Inactive timeout from CLI (-o json): {timeout_val} minutes")
                return timeout_val
            else:
                logger.warning(f"Inactive timeout from JSON is not an int: {timeout_val}")
        elif not device_data:
            logger.warning("get_inactive_timeout: Could not get device_data for JSON.")
        return None 

    def set_inactive_timeout(self, minutes: int) -> bool:
        # logger.debug("set_inactive_timeout: Using headsetcontrol. Direct HID implementation pending configuration.") # Old log
        logger.debug(f"set_inactive_timeout: Attempting to set to {minutes} minutes via direct HID.")

        # Clamp minutes to the known safe and functional range (0-90 for headsetcontrol compatibility)
        # The actual byte might support 0-255, but UI/HC uses 0-90.
        clamped_minutes = max(0, min(90, minutes))
        if clamped_minutes != minutes:
            logger.info(f"set_inactive_timeout: Requested minutes {minutes} clamped to {clamped_minutes}.")

        if self._set_inactive_timeout_hid(clamped_minutes):
            return True

        if self.headsetcontrol_available:
            logger.warning(f"set_inactive_timeout: Failed to set inactive timeout to {clamped_minutes} via HID. Falling back to headsetcontrol.")
            if not self.is_device_connected():
                logger.warning("set_inactive_timeout (fallback): Device not connected, cannot set via CLI.")
                return False

            logger.info(f"Setting inactive timeout to {clamped_minutes} minutes (fallback to headsetcontrol CLI).")
            success_hc, _ = self._execute_headsetcontrol(['-i', str(clamped_minutes)])
            if not success_hc:
                logger.error(f"Failed to set inactive timeout to {clamped_minutes} using headsetcontrol.")
            return success_hc
        else:
            logger.warning(f"set_inactive_timeout: Direct HID failed for {clamped_minutes} minutes and headsetcontrol is not available.")
            return False

    def get_current_eq_values(self) -> Optional[List[int]]:
        if not self.is_device_connected():
            logger.debug("get_current_eq_values: Device not connected, skipping.")
            return None
        # This would require a specific headsetcontrol command or HID report if supported
        logger.debug("Placeholder: HID get_current_eq_values() / or needs headsetcontrol support")
        return None

    def set_eq_values(self, values: List[int]) -> bool:
        logger.debug("set_eq_values: Using headsetcontrol. Direct HID implementation pending configuration.")
        if not self.is_device_connected():
            logger.warning("set_eq_values: Device not connected, cannot set.")
            return False
        logger.info(f"Setting EQ values to: {values}")
        if not (isinstance(values, list) and len(values) == 10):
            logger.error(f"Invalid EQ values provided: {values}")
            return False
        values_str = ",".join(map(str, values))
        success, _ = self._execute_headsetcontrol(['-e', values_str])
        if not success:
             logger.error(f"Failed to set EQ values: {values_str}")
        return success

    def get_current_eq_preset_id(self) -> Optional[int]:
        if not self.is_device_connected():
            logger.debug("get_current_eq_preset_id: Device not connected, skipping.")
            return None
        device_data = self._get_headset_device_json()
        if device_data and "equalizer" in device_data and isinstance(device_data["equalizer"], dict):
            eq_info = device_data["equalizer"]
            if "preset" in eq_info and isinstance(eq_info["preset"], int):
                preset_id = eq_info["preset"]
                logger.verbose(f"Current HW EQ Preset ID from CLI (-o json): {preset_id}")
                return preset_id
            else:
                logger.warning(f"'preset' key missing or not int in eq_info (JSON): {eq_info}")
        elif not device_data:
            logger.warning("get_current_eq_preset_id: Could not get device_data for JSON.")
        return None

    def set_eq_preset_id(self, preset_id: int) -> bool:
        logger.debug("set_eq_preset_id: Using headsetcontrol. Direct HID implementation pending configuration.")
        if not self.is_device_connected():
            logger.warning("set_eq_preset_id: Device not connected, cannot set.")
            return False
        logger.info(f"Setting HW EQ preset to ID: {preset_id}")
        if not (0 <= preset_id <= 3): 
            logger.error(f"Invalid HW EQ preset ID: {preset_id}")
            return False
        success, _ = self._execute_headsetcontrol(['-p', str(preset_id)])
        if not success:
            logger.error(f"Failed to set HW EQ preset ID: {preset_id}")
        return success

# --- Methods Still Reliant on headsetcontrol CLI ---
# The following public methods currently rely exclusively on parsing
# the output of the `headsetcontrol` command-line tool.
# Future work could involve implementing direct HID communication for them,
# similar to battery, chatmix, sidetone, and inactive timeout.
#
# - get_sidetone_level() (reads from JSON, which is from headsetcontrol)
# - get_inactive_timeout() (reads from JSON)
# - get_current_eq_values() (placeholder, implies headsetcontrol or HID)
# - set_eq_values()
# - get_current_eq_preset_id() (reads from JSON)
# - set_eq_preset_id()
#
# The is_device_connected() method also uses _get_headset_device_json()
# as a primary way to check functional connectivity.