import subprocess
import hid 
import logging # Standard logging
import re
import json
from typing import Optional, List, Tuple, Dict, Any

from . import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

class HeadsetService:
    """
    Service class to interact with the SteelSeries headset via CLI and HID.
    """
    def __init__(self):
        self.hid_device: Optional[hid.Device] = None 
        self.device_path: Optional[bytes] = None
        logger.debug("HeadsetService initialized. Attempting initial HID connection.")
        self._connect_hid_device()

    def _connect_hid_device(self) -> bool:
        """Attempts to connect to the headset via HID by trying suitable interfaces."""
        if self.hid_device: 
            logger.debug("_connect_hid_device: Already connected.")
            return True
        
        logger.debug(f"_connect_hid_device: Trying to connect. Target PIDs: {app_config.TARGET_PIDS}")
        try:
            devices_enum = hid.enumerate(app_config.STEELSERIES_VID, 0)
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
            if dev_info['product_id'] in app_config.TARGET_PIDS:
                logger.debug(f"    Device matches target PID 0x{dev_info['product_id']:04x}. Adding to potential list.")
                potential_devices_to_try.append(dev_info)

        if not potential_devices_to_try:
            logger.debug("_connect_hid_device: No devices found matching target PIDs after enumeration (normal if headset is off).")
            return False

        def sort_key(d_info):
            # Special handling for Arctis Nova 7 (0x2202) - prioritize interface 0
            # and potentially other PIDs that exhibit similar behavior when charging.
            # For Arctis Nova 7, PID is 0x2202.
            if d_info.get('product_id') == 0x2202 and d_info.get('interface_number') == 0:
                logger.debug(f"  SortKey: Prioritizing interface 0 for PID 0x{d_info.get('product_id'):04x}")
                return -1 # Highest priority for specific PID and interface 0

            # Existing general prioritization
            if d_info.get('interface_number') == 3: 
                logger.debug(f"  SortKey: Prioritizing interface 3 for PID 0x{d_info.get('product_id'):04x}")
                return 0  
            if d_info.get('usage_page') == 0xFFC0: 
                logger.debug(f"  SortKey: Prioritizing usage page 0xFFC0 for PID 0x{d_info.get('product_id'):04x}")
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
        logger.debug("_connect_hid_device: No suitable HID device interface found or all attempts to open failed.")
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
        # Step 1: Ensure a basic HID interface is openable.
        # This is important because other functions (like set_sidetone, etc.) might rely on an open HID path.
        if not self._ensure_hid_connection():
            logger.debug("is_device_connected: _ensure_hid_connection failed (no HID path/cannot open).")
            return False

        # Step 2: Use headsetcontrol -o json to verify functional connection.
        # This is considered more reliable, especially for USB-C connected devices where '--connected' might
        # give false negatives after a while.
        device_info = self._get_headset_device_json() # This method already logs errors internally
        
        if device_info is None:
            # _get_headset_device_json() failed to get device info (e.g., headsetcontrol -o json failed,
            # returned empty/invalid JSON, or no devices were found).
            logger.debug("is_device_connected: _get_headset_device_json() returned None. Closing HID handle.")
            self.close() # Close the HID handle as we can't confirm a functional device.
            return False
        
        # If device_info is not None, it means headsetcontrol -o json found and parsed a device.
        # This implies the headset is functionally connected.
        logger.debug("is_device_connected: HID present and _get_headset_device_json() successful.")
        return True


    # --- Public API ---

    def get_battery_level(self) -> Optional[int]:
        logger.debug("get_battery_level: Using headsetcontrol. Direct HID implementation pending configuration.")
        # This explicit check is somewhat redundant if SystemTrayIcon calls is_device_connected first,
        # but makes the method safer if called directly.
        if not self.is_device_connected(): # Verifies functional connection
            logger.debug("get_battery_level: Device not connected, skipping.")
            return None

        logger.debug("Attempting to get battery level.")
        success_b, output_b = self._execute_headsetcontrol(['-b'])
        if success_b:
            match = re.search(r"Level:\s*(\d+)%", output_b)
            if match:
                level = int(match.group(1))
                logger.verbose(f"Battery level from CLI (-b, regex parse): {level}%")
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
                 logger.warning("get_battery_level: Could not get device_data for JSON fallback.")
        
        # logger.error("Could not determine battery level after trying all methods.") # Too strong if just unavailable
        return None

    # --- Hypothetical HID-based methods (for future implementation) ---

    def get_battery_level_hid(self) -> Optional[int]:
        """
        Hypothetical: Gets battery level via direct HID communication.
        This method is NOT FUNCTIONAL and serves as a template.
        Requires app_config.HID_CMD_GET_BATTERY and related HID constants
        to be correctly defined.
        """
        logger.info("Attempting get_battery_level_hid (currently non-functional placeholder).")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("get_battery_level_hid: No HID device connected.")
            return None

        # 1. Prepare the command (example from app_config placeholders)
        # Ensure app_config.HID_REPORT_ID_COMMAND_OUTPUT and app_config.HID_CMD_GET_BATTERY are defined.
        # command_to_send = app_config.HID_CMD_GET_BATTERY
        # report_id_output = app_config.HID_REPORT_ID_COMMAND_OUTPUT
        # report_length = app_config.HID_REPORT_LENGTH

        # logger.debug(f"get_battery_level_hid: Sending command {command_to_send} with report ID {report_id_output}")
        # success_write = self._write_hid_report(report_id_output, command_to_send, report_length)

        # if not success_write:
        #     logger.warning("get_battery_level_hid: Failed to write HID command.")
        #     return None

        # 2. Read the response (example)
        # Ensure app_config.HID_REPORT_ID_DATA_INPUT is defined.
        # report_id_input = app_config.HID_REPORT_ID_DATA_INPUT # Or None if not expecting a specific ID prefix
        # response_data = self._read_hid_report(report_id_to_request=report_id_input,
        #                                       report_length=report_length,
        #                                       timeout_ms=1000)

        # if not response_data:
        #     logger.warning("get_battery_level_hid: No response from HID device.")
        #     return None

        # 3. Parse the response (highly speculative)
        # Example: Assuming battery level is in the Nth byte, after the (optional) report ID.
        # response_offset = 0 # if report_id_input was None or _read_hid_report strips it
        # if response_data and len(response_data) > app_config.HID_RESPONSE_BATTERY_BYTE_INDEX + response_offset:
        #     battery_level = response_data[app_config.HID_RESPONSE_BATTERY_BYTE_INDEX + response_offset]
        #     # Optionally, parse charging status from another byte/bit
        #     # charging_status_byte = response_data[app_config.HID_RESPONSE_BATTERY_CHARGING_BYTE_INDEX + response_offset]
        #     # is_charging = (charging_status_byte & app_config.HID_RESPONSE_BATTERY_CHARGING_BIT) != 0
        #     logger.info(f"get_battery_level_hid: Parsed battery level (hypothetical): {battery_level}%")
        #     return battery_level
        # else:
        #    logger.warning(f"get_battery_level_hid: Invalid or too short response: {response_data}")

        logger.warning("get_battery_level_hid: Logic is placeholder and not implemented.")
        return None

    def get_chatmix_value(self) -> Optional[int]:
        if not self.is_device_connected():
            logger.debug("get_chatmix_value: Device not connected, skipping.")
            return None
        logger.debug("Attempting to get ChatMix value.")
        device_data = self._get_headset_device_json() # This internally uses headsetcontrol
        if device_data and "chatmix" in device_data:
            chatmix_val = device_data["chatmix"]
            if isinstance(chatmix_val, (int, float)): 
                chatmix_int = int(chatmix_val)
                logger.verbose(f"ChatMix value from CLI (-o json): {chatmix_int}")
                return chatmix_int
            else:
                logger.warning(f"'chatmix' value is not a number in device_data (JSON): {chatmix_val}")
        elif not device_data: # _get_headset_device_json returned None
             logger.warning("get_chatmix_value: Could not get device_data for JSON.")
            
        # logger.error("Could not determine ChatMix value.") # Too strong if unavailable
        return None

    def get_sidetone_level(self) -> Optional[int]:
        logger.debug("get_sidetone_level: Using headsetcontrol. Direct HID implementation pending configuration.")
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
        logger.debug("set_sidetone_level: Using headsetcontrol. Direct HID implementation pending configuration.")
        if not self.is_device_connected():
            logger.warning("set_sidetone_level: Device not connected, cannot set.")
            return False
        logger.info(f"Setting sidetone level to {level}.")
        level = max(0, min(128, level)) 
        success, _ = self._execute_headsetcontrol(['-s', str(level)])
        if not success:
            logger.error(f"Failed to set sidetone level to {level}.")
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
        if not self.is_device_connected():
            logger.warning("set_inactive_timeout: Device not connected, cannot set.")
            return False
        logger.info(f"Setting inactive timeout to {minutes} minutes.")
        minutes = max(0, min(90, minutes)) 
        success, _ = self._execute_headsetcontrol(['-i', str(minutes)])
        if not success:
            logger.error(f"Failed to set inactive timeout to {minutes}.")
        return success

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