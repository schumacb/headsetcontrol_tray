# steelseries_tray/headset_service.py
import subprocess
import hid
from typing import Optional, List, Tuple

from . import app_config

class HeadsetService:
    """
    Service class to interact with the SteelSeries headset via CLI and HID.
    """
    def __init__(self):
        self.hid_device: Optional[hid.device] = None
        self.device_path: Optional[bytes] = None
        self._connect_hid_device()

    def _connect_hid_device(self) -> bool:
        """Attempts to connect to the headset via HID."""
        if self.hid_device:
            return True
        
        devices = hid.enumerate(app_config.STEELSERIES_VID, 0) # Enumerate all SteelSeries PIDs
        target_device_info = None

        for dev_info in devices:
            # For Arctis Nova 7, multiple interfaces might be present.
            # We need to find the one that responds to control commands.
            # This often means looking for a specific usage page/usage or interface number.
            # For now, we'll try PIDs and assume the first match is usable.
            # A more robust method would involve checking interface numbers or report descriptors.
            if dev_info['product_id'] in app_config.TARGET_PIDS:
                # Example criteria for some SteelSeries devices:
                # if dev_info['interface_number'] == 3 or dev_info['usage_page'] == 0xFFC0:
                target_device_info = dev_info
                break
        
        if target_device_info:
            try:
                self.hid_device = hid.device()
                self.hid_device.open_path(target_device_info['path'])
                self.device_path = target_device_info['path']
                # print(f"HID device connected: {target_device_info['product_string']}")
                return True
            except Exception as e: # hid.HIDException can be too broad, OSError occurs too
                # print(f"Error connecting to HID device {target_device_info.get('path', 'N/A')}: {e}")
                self.hid_device = None
                self.device_path = None
                return False
        # print("HID device not found.")
        return False

    def _ensure_hid_connection(self) -> bool:
        if not self.hid_device:
            return self._connect_hid_device()
        # Check if device is still valid (e.g. by trying a benign read or by re-enumerating)
        # For simplicity, we'll rely on operations failing if disconnected.
        # A more robust check could re-enumerate and match self.device_path.
        try:
            # A small, non-blocking read or a feature report get could test connection
            # For now, assume if self.hid_device object exists, it might be usable.
            # hidapi does not have a simple is_connected() method.
            pass
        except hid.HIDException: # Or other relevant exceptions
            self.close()
            return self._connect_hid_device()
        return True


    def close(self) -> None:
        if self.hid_device:
            try:
                self.hid_device.close()
            except Exception: # Catch if it was already invalid
                pass
            self.hid_device = None
            self.device_path = None

    def _execute_headsetcontrol(self, args: List[str]) -> Tuple[bool, str]:
        """Executes headsetcontrol CLI tool."""
        try:
            process = subprocess.run(['headsetcontrol'] + args, capture_output=True, text=True, check=True)
            return True, process.stdout.strip()
        except FileNotFoundError:
            return False, "headsetcontrol not found. Please install it."
        except subprocess.CalledProcessError as e:
            return False, f"headsetcontrol error: {e.stderr.strip()}"

    def _write_hid_report(self, report_id: int, data: List[int], report_length: int = 64) -> bool:
        """
        Writes a report to the HID device.
        Prepends report_id if it's > 0.
        Pads data to report_length.
        """
        if not self._ensure_hid_connection() or not self.hid_device:
            return False
        
        payload = bytes(data)
        if report_id > 0: # Numbered report
            # For Windows, report ID is prefixed. For Linux/macOS with hidapi, it's often not.
            # This depends on hidapi backend and OS. Test this.
            # Typically, for feature reports, report_id is the first byte of the buffer.
            # For output reports, if report_id is used, it's also the first byte.
            # If report_id is 0, it's an unnumbered report.
            final_report = bytes([report_id]) + payload
        else: # Unnumbered report
            final_report = payload

        # Pad to expected report length if necessary (some devices require full length reports)
        # This padding might not always be needed, depends on device firmware.
        # final_report = final_report.ljust(report_length, b'\x00')
        
        try:
            # If using Feature Reports:
            # self.hid_device.send_feature_report(final_report)
            # If using Output Reports:
            bytes_written = self.hid_device.write(final_report)
            return bytes_written > 0 # Or check against len(final_report)
        except Exception as e: # hid.HIDException or OSError
            # print(f"HID write error: {e}")
            self.close() # Assume device disconnected
            return False

    def _read_hid_report(self, report_id_to_request: Optional[int] = None, report_length: int = 64, timeout_ms: int = 1000) -> Optional[List[int]]:
        """
        Reads a report from the HID device.
        If report_id_to_request is provided, it's for Feature Reports.
        """
        if not self._ensure_hid_connection() or not self.hid_device:
            return None
        try:
            # If reading an Input Report:
            data = self.hid_device.read(report_length, timeout_ms=timeout_ms)
            # If reading a Feature Report:
            # buffer = bytes([report_id_to_request]) + b'\x00' * (report_length -1)
            # data = self.hid_device.get_feature_report(report_id_to_request, report_length)
            
            return list(data) if data else None
        except Exception as e: # hid.HIDException or OSError
            # print(f"HID read error: {e}")
            self.close() # Assume device disconnected
            return None

    def is_device_connected(self) -> bool:
        return self._ensure_hid_connection()

    # --- Public API ---

    def get_battery_level(self) -> Optional[int]:
        """Gets battery level. Prefers CLI for simplicity unless HID is well-defined."""
        # HID Method (Placeholder - requires specific report knowledge)
        # if self._ensure_hid_connection():
        #     # Example: send command [app_config.HID_REPORT_ID_COMMAND, app_config.HID_CMD_GET_BATTERY[0], app_config.HID_CMD_GET_BATTERY[1], ...]
        #     # data = self._read_hid_report(...)
        #     # if data and len(data) > X: return data[X] # Parse battery level
        #     pass

        # CLI Fallback (more reliable for battery without precise HID docs)
        success, output = self._execute_headsetcontrol(['-b'])
        if success and output.isdigit():
            return int(output)
        
        # Try JSON output if simple -b fails or for more info
        success, output = self._execute_headsetcontrol(['-o', 'json'])
        if success:
            try:
                import json
                data = json.loads(output)
                if "battery" in data and isinstance(data["battery"], int):
                    return data["battery"]
            except json.JSONDecodeError:
                pass # Could not parse JSON
        return None

    def get_sidetone_level(self) -> Optional[int]:
        """Gets current sidetone level via HID. (Requires HID implementation)"""
        if not self._ensure_hid_connection(): return None
        # print("Placeholder: HID get_sidetone_level() - requires specific report.")
        # Example: Send request for sidetone report
        # self._write_hid_report(REPORT_ID, CMD_GET_SIDETONE_BYTES)
        # response = self._read_hid_report()
        # if response: return parse_sidetone_from_response(response)
        return None # No CLI method to get sidetone

    def set_sidetone_level(self, level: int) -> bool:
        """Sets sidetone level (0-128) via CLI."""
        level = max(0, min(128, level))
        success, _ = self._execute_headsetcontrol(['-s', str(level)])
        return success

    def get_inactive_timeout(self) -> Optional[int]:
        """Gets current inactive timeout. (Requires HID or not supported by headsetcontrol)"""
        # headsetcontrol does not support reading this value.
        # This would require a HID implementation.
        # print("Placeholder: HID get_inactive_timeout() - requires specific report.")
        return None # Return None, rely on stored config

    def set_inactive_timeout(self, minutes: int) -> bool:
        """Sets inactive timeout (0-90 minutes) via CLI."""
        minutes = max(0, min(90, minutes))
        success, _ = self._execute_headsetcontrol(['-i', str(minutes)])
        return success

    def get_current_eq_values(self) -> Optional[List[int]]:
        """Gets current 10-band EQ values via HID. (Requires HID implementation)"""
        if not self._ensure_hid_connection(): return None
        # print("Placeholder: HID get_current_eq_values() - requires specific report.")
        # Example: Send request for EQ report
        # self._write_hid_report(REPORT_ID, CMD_GET_EQ_VALUES_BYTES)
        # response = self._read_hid_report()
        # if response: return parse_eq_values_from_response(response) # Should be 10 values
        return None

    def set_eq_values(self, values: List[int]) -> bool:
        """Sets 10-band EQ values (each -10 to 10) via CLI."""
        if not (isinstance(values, list) and len(values) == 10):
            return False
        values_str = ",".join(map(str, values))
        success, _ = self._execute_headsetcontrol(['-e', values_str])
        return success

    def get_current_eq_preset_id(self) -> Optional[int]:
        """Gets currently active hardware EQ preset ID (0-3) via HID. (Requires HID implementation)"""
        if not self._ensure_hid_connection(): return None
        # print("Placeholder: HID get_current_eq_preset_id() - requires specific report.")
        # Example: Send request for active preset report
        # self._write_hid_report(REPORT_ID, CMD_GET_ACTIVE_PRESET_BYTES)
        # response = self._read_hid_report()
        # if response: return parse_preset_id_from_response(response)
        return None

    def set_eq_preset_id(self, preset_id: int) -> bool:
        """Sets hardware EQ preset ID (0-3) via CLI."""
        if not (0 <= preset_id <= 3): # Assuming 4 presets
            return False
        success, _ = self._execute_headsetcontrol(['-p', str(preset_id)])
        return success