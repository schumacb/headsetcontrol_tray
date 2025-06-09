import logging
import hid
from typing import List, Optional, Dict, Any # Added Dict, Any

from . import app_config # Assuming app_config is in the same directory
# Import HIDConnectionManager to type hint the constructor, but it's not strictly needed for runtime in this class if device is passed in
# from .hid_manager import HIDConnectionManager # Or forward reference if that causes issues

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

class HIDCommunicator:
    def __init__(self, hid_device: hid.Device, device_info: Dict[str, Any]):
        if hid_device is None:
            # This case should ideally be prevented by the caller (e.g. HeadsetService ensuring connection first)
            logger.error("HIDCommunicator initialized with a None hid_device. This is unexpected.")
            raise ValueError("HIDCommunicator requires a valid hid.Device object.")
        self.hid_device: hid.Device = hid_device

        # Extract and store info for logging
        # Path is bytes in device_info, product_string is str
        _path_bytes = device_info.get("path")
        self.device_path_str: str = _path_bytes.decode('utf-8', 'replace') if isinstance(_path_bytes, bytes) else "Unknown Path"
        # Ensure product_string is treated as potentially None and provide a default
        _product_str_temp = device_info.get("product_string")
        self.device_product_str: str = _product_str_temp if isinstance(_product_str_temp, str) else "Unknown Product"

        logger.debug(f"HIDCommunicator initialized for device: {self.device_product_str} ({self.device_path_str})")

    def write_report(self, report_id: int, data: List[int]) -> bool:
        # (Adapt logic from HeadsetService._write_hid_report)
        # This method now assumes self.hid_device is valid and open.
        # The responsibility of ensuring the device is connected and stays connected
        # could lie with HeadsetService or HIDConnectionManager.
        # If write fails due to device issue, this method could return False or raise an exception.

        payload = bytes(data)
        if report_id > 0:
            final_report = bytes([report_id]) + payload
        else: # report_id is 0 or not used (common for SteelSeries commands starting with 0x00)
            final_report = payload

        # It's important to determine if the first byte of `data` (e.g. app_config.HID_REPORT_FIXED_FIRST_BYTE)
        # is itself a report ID or part of the payload.
        # The original _write_hid_report logic:
        # - If report_id > 0, it prepends it.
        # - If report_id == 0, it sends data as-is.
        # This seems correct if commands in app_config that start with 0x00 are meant to be sent
        # with report_id=0, and that 0x00 is part of the payload.
        # For commands like HID_CMD_SAVE_SETTINGS = [0x06, 0x09], report_id=0x06 would be used.

        logger.debug(f"Writing HID report: ID={report_id}, Data={final_report.hex()} to device {self.device_product_str} ({self.device_path_str})")
        try:
            bytes_written = self.hid_device.write(final_report)
            logger.debug(f"Bytes written: {bytes_written}")
            if bytes_written <= 0:
                logger.warning(f"HID write returned {bytes_written}. This might indicate an issue with the device {self.device_product_str} ({self.device_path_str}).")
                # Consider if this class should handle device closure/reconnection or signal failure to a manager.
                # For now, just report failure. The caller (HeadsetService) might need to handle this.
                return False
            return True
        except Exception as e: # hid.HIDException can be more specific if available and appropriate
            logger.error(f"HID write error on device {self.device_product_str} ({self.device_path_str}): {e}")
            # Similar to bytes_written <= 0, signal failure.
            return False

    def read_report(self, report_length: int) -> Optional[bytes]: # Removed timeout_ms parameter
        # (Adapt logic from HeadsetService._get_parsed_status_hid for reading)
        # This method now assumes self.hid_device is valid and open.

        logger.debug(f"Reading HID report of length {report_length} from device {self.device_product_str} ({self.device_path_str})") # Updated log
        try:
            # Removed timeout logic

            # Call read without timeout_ms
            response_data = self.hid_device.read(report_length) # Removed timeout_ms and type: ignore

            if not response_data:
                logger.warning(f"No data received from HID read on {self.device_product_str} ({self.device_path_str}) (length {report_length}).") # Updated log
                return None
            if len(response_data) < report_length:
                logger.warning((f"Incomplete HID read on {self.device_product_str} ({self.device_path_str}). Expected {report_length} bytes, " # Log unchanged here but context is
                                f"got {len(response_data)}: {bytes(response_data).hex()}"))
                # Depending on requirements, could return None or the partial data.
                # For status reports, partial data is likely unusable.
                return None

            logger.debug(f"HID read successful from {self.device_product_str} ({self.device_path_str}): {bytes(response_data).hex()}")
            return bytes(response_data)
        except Exception as e: # hid.HIDException can be more specific
            logger.error(f"HID read error on device {self.device_product_str} ({self.device_path_str}): {e}")
            return None
