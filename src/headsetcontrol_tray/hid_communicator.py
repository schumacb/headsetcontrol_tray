"""Handles low-level HID read and write operations for a connected headset device."""

import logging
from typing import Any  # Added Dict, Any

import hid

from . import app_config  # Assuming app_config is in the same directory

# Import HIDConnectionManager to type hint the constructor, but it's not strictly
# needed for runtime in this class if device is passed in

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class HIDCommunicator:
    """Facilitates direct HID communication with a headset device."""

    def __init__(self, hid_device: hid.Device, device_info: dict[str, Any]) -> None:
        """
        Initializes the HIDCommunicator.

        Args:
            hid_device: An open hid.Device object.
            device_info: A dictionary containing device information like path
                         and product string.
        """
        if hid_device is None:
            # This case should ideally be prevented by the caller
            # (e.g. HeadsetService ensuring connection first)
            logger.error(
                "HIDCommunicator initialized with a None hid_device. "
                "This is unexpected.",
            )
            raise ValueError("HIDCommunicator requires a valid hid.Device object.")
        self.hid_device: hid.Device = hid_device

        # Extract and store info for logging
        # Path is bytes in device_info, product_string is str
        _path_bytes = device_info.get("path")
        self.device_path_str: str = (
            _path_bytes.decode("utf-8", "replace")
            if isinstance(_path_bytes, bytes)
            else "Unknown Path"
        )
        # Ensure product_string is treated as potentially None and provide a default
        _product_str_temp = device_info.get("product_string")
        self.device_product_str: str = (
            _product_str_temp
            if isinstance(_product_str_temp, str)
            else "Unknown Product"
        )

        logger.debug(
            "HIDCommunicator initialized for device: %s (%s)",
            self.device_product_str,
            self.device_path_str,
        )

    def write_report(self, report_id: int, data: list[int]) -> bool:
        """Writes an HID report to the headset device."""
        # (Adapt logic from HeadsetService._write_hid_report)
        # This method now assumes self.hid_device is valid and open.
        # The responsibility of ensuring the device is connected and stays connected
        # could lie with HeadsetService or HIDConnectionManager.
        # If write fails due to device issue, this method could return False or raise an exception.

        payload = bytes(data)
        final_report = bytes([report_id]) + payload if report_id > 0 else payload

        # It's important to determine if the first byte of `data`
        # (e.g. app_config.HID_REPORT_FIXED_FIRST_BYTE) is itself a report ID or
        # part of the payload.
        # The original _write_hid_report logic:
        # - If report_id > 0, it prepends it.
        # - If report_id == 0, it sends data as-is.
        # This seems correct if commands in app_config that start with 0x00 are
        # meant to be sent with report_id=0, and that 0x00 is part of the
        # payload.
        # For commands like HID_CMD_SAVE_SETTINGS = [0x06, 0x09],
        # report_id=0x06 would be used.

        logger.debug(
            ("Writing HID report: ID=%s, Data=%s to device %s (%s)"), # Already wrapped, but the line itself is long
            report_id,
            final_report.hex(),
            self.device_product_str,
            self.device_path_str,
        )
        try:
            bytes_written = self.hid_device.write(final_report)
            logger.debug("Bytes written: %s", bytes_written)
            if bytes_written <= 0:
                logger.warning(
                    ("HID write returned %s. This might indicate an issue with the "
                     "device %s (%s)."),
                    bytes_written,
                    self.device_product_str,
                    self.device_path_str,
                )
                # Consider if this class should handle device closure/reconnection
                # or signal failure to a manager.
                # For now, just report failure. The caller (HeadsetService) might need to handle this.
                return False
            else:
                return True
        except hid.HIDException as e:
            logger.exception(
                "HID write error on device %s (%s)",
                self.device_product_str,
                self.device_path_str,
            )
            # Similar to bytes_written <= 0, signal failure.
            return False

    def read_report(
        self,
        report_length: int,
    ) -> bytes | None:  # Removed timeout_ms parameter
        """Reads an HID report from the headset device."""
        # (Adapt logic from HeadsetService._get_parsed_status_hid for reading)
        # This method now assumes self.hid_device is valid and open.

        logger.debug(
            ("Reading HID report of length %s from device %s (%s)"),
            report_length,
            self.device_product_str,
            self.device_path_str,
        )  # Updated log
        try:
            # Removed timeout logic

            # Call read without timeout_ms
            response_data = self.hid_device.read(
                report_length,
            )  # Removed timeout_ms and type: ignore

            if not response_data:
                logger.warning(
                    ("No data received from HID read on %s (%s) (length %s)."),
                    self.device_product_str,
                    self.device_path_str,
                    report_length,
                )  # Updated log
                return None
            if len(response_data) < report_length:
                logger.warning(
                    "Incomplete HID read on %s (%s). Expected %s bytes, got %s: %s",
                    self.device_product_str,
                    self.device_path_str,
                    report_length,
                    len(response_data),
                    bytes(response_data).hex(),
                )
                # Depending on requirements, could return None or the partial data.
                # For status reports, partial data is likely unusable.
                return None

            logger.debug(
                "HID read successful from %s (%s): %s",
                self.device_product_str,
                self.device_path_str,
                bytes(response_data).hex(),
            )
            return bytes(response_data)
        except hid.HIDException as e:
            logger.exception(
                "HID read error on device %s (%s)",
                self.device_product_str,
                self.device_path_str,
            )
            return None
