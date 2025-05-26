import subprocess
import hid 
import logging
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
            logger.warning("_connect_hid_device: No devices found matching target PIDs after enumeration.")
            return False

        def sort_key(d_info):
            if d_info.get('interface_number') == 3: 
                return 0  
            if d_info.get('usage_page') == 0xFFC0: 
                return 1  
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
                logger.info(f"HID device connected: {dev_info_to_try.get('product_string', 'N/A')} "
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
        logger.error("_connect_hid_device: No suitable HID device interface found or all attempts to open failed.")
        return False

    def _ensure_hid_connection(self) -> bool:
        if not self.hid_device:
            logger.debug("_ensure_hid_connection: No HID device, attempting to connect.")
            return self._connect_hid_device()
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
            logger.debug(f"headsetcontrol output: {process.stdout.strip()}")
            return True, process.stdout.strip()
        except FileNotFoundError:
            logger.error("headsetcontrol command not found. Please ensure it is installed and in PATH.")
            return False, "headsetcontrol not found. Please install it."
        except subprocess.CalledProcessError as e:
            logger.error(f"headsetcontrol error (stderr): {e.stderr.strip()}")
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
             logger.warning(f"Failed to get status from 'headsetcontrol -o json'. Success: {success_json}, Output: {output_json}")
        return None


    def _write_hid_report(self, report_id: int, data: List[int], report_length: int = 64) -> bool:
        """
        Writes a report to the HID device.
        Prepends report_id if it's > 0.
        Pads data to report_length.
        """
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_write_hid_report: No HID device connected.")
            return False
        
        payload = bytes(data)
        if report_id > 0: 
            final_report = bytes([report_id]) + payload
        else: 
            final_report = payload
        
        logger.debug(f"Writing HID report: ID={report_id}, Data={final_report.hex()}")
        try:
            bytes_written = self.hid_device.write(final_report)
            logger.debug(f"Bytes written: {bytes_written}")
            return bytes_written > 0 
        except Exception as e: 
            logger.error(f"HID write error: {e}")
            self.close() 
            return False

    def _read_hid_report(self, report_id_to_request: Optional[int] = None, report_length: int = 64, timeout_ms: int = 1000) -> Optional[List[int]]:
        """
        Reads a report from the HID device.
        If report_id_to_request is provided, it's for Feature Reports.
        """
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_read_hid_report: No HID device connected.")
            return None
        
        logger.debug(f"Reading HID report: ReportIDToRequest={report_id_to_request}, Length={report_length}, Timeout={timeout_ms}ms")
        try:
            data = self.hid_device.read(report_length, timeout_ms=timeout_ms)
            if data:
                logger.debug(f"HID read data: {bytes(data).hex()}")
                return list(data)
            else:
                logger.debug("HID read no data (timeout or empty report).")
                return None
        except Exception as e: 
            logger.error(f"HID read error: {e}")
            self.close() 
            return None

    def is_device_connected(self) -> bool:
        is_conn = self._ensure_hid_connection()
        if is_conn:
            success, _ = self._execute_headsetcontrol(['--connected']) 
            if not success:
                 logger.warning("HID connected, but headsetcontrol --connected failed. Device might not be fully responsive.")
            else:
                logger.debug("is_device_connected: HID connected and headsetcontrol --connected successful.")

        logger.debug(f"is_device_connected returning: {is_conn}")
        return is_conn


    # --- Public API ---

    def get_battery_level(self) -> Optional[int]:
        logger.debug("Attempting to get battery level.")
        logger.debug("Trying CLI method for battery ('headsetcontrol -b').")
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
            else:
                logger.warning(f"Could not parse battery level from 'headsetcontrol -b' output: {output_b}")
        
        device_data = self._get_headset_device_json()
        if device_data and "battery" in device_data and isinstance(device_data["battery"], dict):
            battery_info = device_data["battery"]
            if "level" in battery_info and isinstance(battery_info["level"], int):
                level = battery_info["level"]
                logger.verbose(f"Battery level from CLI (-o json): {level}%")
                return level
            else:
                logger.warning(f"'level' key missing or not int in battery_info (JSON): {battery_info}")
        
        logger.error("Could not determine battery level after trying all methods.")
        return None

    def get_chatmix_value(self) -> Optional[int]:
        """Gets ChatMix value (0-128)."""
        logger.debug("Attempting to get ChatMix value.")
        device_data = self._get_headset_device_json()
        if device_data and "chatmix" in device_data:
            chatmix_val = device_data["chatmix"]
            if isinstance(chatmix_val, (int, float)): 
                chatmix_int = int(chatmix_val)
                logger.verbose(f"ChatMix value from CLI (-o json): {chatmix_int}")
                return chatmix_int
            else:
                logger.warning(f"'chatmix' value is not a number in device_data (JSON): {chatmix_val}")
        else:
            logger.warning(f"'chatmix' key missing in device_data (JSON) or device_data is None.")
            
        logger.error("Could not determine ChatMix value.")
        return None

    def get_sidetone_level(self) -> Optional[int]:
        device_data = self._get_headset_device_json()
        if device_data and "sidetone" in device_data: # Assuming 'sidetone' key exists at device level in JSON
            sidetone_val = device_data["sidetone"]
            if isinstance(sidetone_val, int):
                logger.verbose(f"Sidetone level from CLI (-o json): {sidetone_val}")
                return sidetone_val
            else:
                logger.warning(f"Sidetone value from JSON is not an int: {sidetone_val}")

        if not self.is_device_connected(): return None 
        logger.debug("Placeholder: HID get_sidetone_level() - requires specific report.")
        return None 

    def set_sidetone_level(self, level: int) -> bool:
        logger.info(f"Setting sidetone level to {level}.")
        level = max(0, min(128, level)) 
        success, _ = self._execute_headsetcontrol(['-s', str(level)])
        if not success:
            logger.error(f"Failed to set sidetone level to {level}.")
        return success

    def get_inactive_timeout(self) -> Optional[int]:
        device_data = self._get_headset_device_json()
        if device_data and "inactive_time" in device_data: 
            timeout_val = device_data["inactive_time"]
            if isinstance(timeout_val, int):
                logger.verbose(f"Inactive timeout from CLI (-o json): {timeout_val} minutes")
                return timeout_val
            else:
                logger.warning(f"Inactive timeout from JSON is not an int: {timeout_val}")
        
        logger.debug("Placeholder: HID get_inactive_timeout() - requires specific report.")
        return None 

    def set_inactive_timeout(self, minutes: int) -> bool:
        logger.info(f"Setting inactive timeout to {minutes} minutes.")
        minutes = max(0, min(90, minutes)) 
        success, _ = self._execute_headsetcontrol(['-i', str(minutes)])
        if not success:
            logger.error(f"Failed to set inactive timeout to {minutes}.")
        return success

    def get_current_eq_values(self) -> Optional[List[int]]:
        if not self.is_device_connected(): return None 
        logger.debug("Placeholder: HID get_current_eq_values() - requires specific report.")
        return None

    def set_eq_values(self, values: List[int]) -> bool:
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
        device_data = self._get_headset_device_json()
        if device_data and "equalizer" in device_data and isinstance(device_data["equalizer"], dict):
            eq_info = device_data["equalizer"]
            if "preset" in eq_info and isinstance(eq_info["preset"], int):
                preset_id = eq_info["preset"]
                logger.verbose(f"Current HW EQ Preset ID from CLI (-o json): {preset_id}")
                return preset_id
            else:
                logger.warning(f"'preset' key missing or not int in eq_info (JSON): {eq_info}")

        if not self.is_device_connected(): return None 
        logger.debug("Placeholder: HID get_current_eq_preset_id() - requires specific report.")
        return None

    def set_eq_preset_id(self, preset_id: int) -> bool:
        logger.info(f"Setting HW EQ preset to ID: {preset_id}")
        if not (0 <= preset_id <= 3): 
            logger.error(f"Invalid HW EQ preset ID: {preset_id}")
            return False
        success, _ = self._execute_headsetcontrol(['-p', str(preset_id)])
        if not success:
            logger.error(f"Failed to set HW EQ preset ID: {preset_id}")
        return success