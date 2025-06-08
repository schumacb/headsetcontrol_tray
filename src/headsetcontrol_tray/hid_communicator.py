import logging
import hid # type: ignore[import-not-found]
from typing import List, Optional

from . import app_config # Assuming app_config is in the same directory
# Import HIDConnectionManager to type hint the constructor, but it's not strictly needed for runtime in this class if device is passed in
# from .hid_manager import HIDConnectionManager # Or forward reference if that causes issues

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

class HIDCommunicator:
    def __init__(self, hid_device: hid.Device):
        if hid_device is None:
            # This case should ideally be prevented by the caller (e.g. HeadsetService ensuring connection first)
            # Or, HIDCommunicator could be more resilient, but for now, assume valid device.
            logger.error("HIDCommunicator initialized with a None hid_device. This is unexpected.")
            raise ValueError("HIDCommunicator requires a valid hid.Device object.")
        self.hid_device: hid.Device = hid_device
        # self._connection_manager = connection_manager # If we need to re-acquire device or signal connection loss
        logger.debug("HIDCommunicator initialized with an active HID device.")

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

        device_path_str = "N/A"
        if self.hid_device and self.hid_device.path:
            try:
                device_path_str = self.hid_device.path.decode('utf-8', 'replace')
            except AttributeError: # path might already be a string in some hidapi versions/implementations
                 if isinstance(self.hid_device.path, str):
                    device_path_str = self.hid_device.path

        logger.debug(f"Writing HID report: ID={report_id}, Data={final_report.hex()} to device {device_path_str}")
        try:
            bytes_written = self.hid_device.write(final_report)
            logger.debug(f"Bytes written: {bytes_written}")
            if bytes_written <= 0:
                logger.warning(f"HID write returned {bytes_written}. This might indicate an issue with the device.")
                # Consider if this class should handle device closure/reconnection or signal failure to a manager.
                # For now, just report failure. The caller (HeadsetService) might need to handle this.
                return False
            return True
        except Exception as e: # hid.HIDException can be more specific if available and appropriate
            logger.error(f"HID write error on device {device_path_str}: {e}")
            # Similar to bytes_written <= 0, signal failure.
            return False

    def read_report(self, report_length: int, timeout_ms: Optional[int] = 1000) -> Optional[bytes]:
        # (Adapt logic from HeadsetService._get_parsed_status_hid for reading)
        # This method now assumes self.hid_device is valid and open.
        device_path_str = "N/A"
        if self.hid_device and self.hid_device.path:
            try:
                device_path_str = self.hid_device.path.decode('utf-8', 'replace')
            except AttributeError: # path might already be a string
                if isinstance(self.hid_device.path, str):
                    device_path_str = self.hid_device.path

        logger.debug(f"Reading HID report of length {report_length} with timeout {timeout_ms}ms from device {device_path_str}")
        try:
            # The timeout_ms parameter in hid.Device.read might not be universally supported across all python-hid backends/versions.
            # If it's not, or if a non-blocking read is preferred, this might need adjustment.
            # For now, assume it works as intended.
            # If timeout_ms is None, it might block indefinitely, which could be an issue.
            # Defaulting to a reasonable timeout (e.g., 1000ms) is safer.
            if timeout_ms is None: # Ensure there's always a timeout
                logger.warning("read_report called with timeout_ms=None, defaulting to 1000ms to prevent potential indefinite block.")
                effective_timeout_ms = 1000
            else:
                effective_timeout_ms = timeout_ms

            # hid.Device.read expects path as bytes.
            # The type ignore for timeout_ms is because some stubs might not declare it.
            response_data = self.hid_device.read(report_length, timeout_ms=effective_timeout_ms) # type: ignore

            if not response_data:
                logger.warning(f"No data received from HID read (length {report_length}, timeout {effective_timeout_ms}ms).")
                return None
            if len(response_data) < report_length:
                logger.warning((f"Incomplete HID read. Expected {report_length} bytes, "
                                f"got {len(response_data)}: {bytes(response_data).hex()}"))
                # Depending on requirements, could return None or the partial data.
                # For status reports, partial data is likely unusable.
                return None

            logger.debug(f"HID read successful: {bytes(response_data).hex()}")
            return bytes(response_data)
        except Exception as e: # hid.HIDException can be more specific
            logger.error(f"HID read error on device {device_path_str}: {e}")
            return None
