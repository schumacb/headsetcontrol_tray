"""Manages the discovery, connection, and sorting of HID devices."""
import logging
from typing import Any

import hid

from . import app_config  # Assuming app_config is in the same directory

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

class HIDConnectionManager:
    """Handles the connection lifecycle for SteelSeries HID devices."""
    def __init__(self) -> None:
        """Initializes the HIDConnectionManager."""
        self.hid_device: hid.Device | None = None
        self.selected_device_info: dict[str, Any] | None = None
        logger.debug("HIDConnectionManager initialized.")

    def _find_potential_hid_devices(self) -> list[dict[str, Any]]:
        # (Copy and adapt logic from HeadsetService._find_potential_hid_devices)
        # Ensure STEELSERIES_VID and TARGET_PIDS are accessed via app_config
        logger.debug("Enumerating HID devices for VID 0x%04x, Target PIDs: %s", app_config.STEELSERIES_VID, app_config.TARGET_PIDS)
        try:
            devices_enum = hid.enumerate(app_config.STEELSERIES_VID, 0)
            logger.debug("Found %s SteelSeries VID devices during enumeration.", len(devices_enum))
        except Exception as e_enum:
            logger.error("Error enumerating HID devices: %s", str(e_enum))
            return []

        potential_devices = []
        for dev_info in devices_enum:
            logger.debug("  Enumerated device: PID=0x%04x, Release=0x%04x, Interface=%s, UsagePage=0x%04x, Usage=0x%04x, Path=%s, Product='%s'",
                         dev_info["product_id"], dev_info.get("release_number", 0),
                         dev_info.get("interface_number", "N/A"), dev_info.get("usage_page", 0),
                         dev_info.get("usage", 0), dev_info["path"].decode("utf-8", errors="replace"),
                         dev_info.get("product_string", "N/A"))
            if dev_info["product_id"] in app_config.TARGET_PIDS:
                logger.debug("    Device matches target PID 0x%04x. Adding to potential list.", dev_info["product_id"])
                potential_devices.append(dev_info)
        return potential_devices

    def _sort_hid_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # (Copy and adapt logic from HeadsetService._sort_hid_devices)
        # Ensure constants like HID_REPORT_INTERFACE are accessed via app_config
        def sort_key(d_info: dict[str, Any]) -> int:
            if d_info["vendor_id"] == app_config.STEELSERIES_VID and \
               d_info["product_id"] in app_config.TARGET_PIDS and \
               d_info.get("interface_number") == app_config.HID_REPORT_INTERFACE and \
               d_info.get("usage_page") == app_config.HID_REPORT_USAGE_PAGE and \
               d_info.get("usage") == app_config.HID_REPORT_USAGE_ID:
                logger.debug("  SortKey: Prioritizing exact Arctis Nova 7 interface (0) for PID 0x%04x", d_info.get("product_id"))
                return -2 # Highest priority
            # This condition for PID 0x2202 seems very specific and might be less generic.
            # Consider if it's universally applicable or needs to be part of a more flexible configuration.
            if d_info.get("product_id") == 0x2202 and d_info.get("interface_number") == 0:
                logger.debug("  SortKey: Prioritizing interface 0 for PID 0x%04x (-1)", d_info.get("product_id"))
                return -1
            if d_info.get("interface_number") == 3: # Common interface for some SteelSeries headsets
                logger.debug("  SortKey: Prioritizing interface 3 (generic) for PID 0x%04x (0)", d_info.get("product_id"))
                return 0
            if d_info.get("usage_page") == 0xFFC0: # Common SteelSeries usage page
                logger.debug("  SortKey: Prioritizing usage page 0xFFC0 (generic) for PID 0x%04x (1)", d_info.get("product_id"))
                return 1
            logger.debug("  SortKey: Default priority 2 for PID 0x%04x, Interface %s, UsagePage 0x%04x",
                         d_info.get("product_id"), d_info.get("interface_number", "N/A"), d_info.get("usage_page",0))
            return 2 # Lowest priority

        devices.sort(key=sort_key)
        logger.debug("Found %s potential devices to try, sorted by priority.", len(devices))
        for i, d in enumerate(devices):
            logger.debug("  Device %s: Path=%s, Interface=%s, UsagePage=0x%04x, PID=0x%04x",
                         i+1, d["path"].decode("utf-8", errors="replace"),
                         d.get("interface_number","N/A"), d.get("usage_page",0), d["product_id"])
        return devices

    def _connect_device(self) -> bool:
        # (Adapt HeadsetService._connect_hid_device)
        if self.hid_device:
            logger.debug("_connect_device: Already connected.")
            return True

        logger.debug("_connect_device: Trying to connect.")
        potential_devices = self._find_potential_hid_devices()

        if not potential_devices:
            logger.debug("_connect_device: No devices found matching target PIDs after enumeration.")
            self.hid_device = None
            self.selected_device_info = None
            # Do not call udev rule creation here; that's a separate concern.
            return False

        sorted_devices = self._sort_hid_devices(potential_devices)

        for dev_info_to_try in sorted_devices:
            h_temp = None
            path_str = dev_info_to_try["path"].decode("utf-8", errors="replace")
            logger.debug("  Attempting to open path: %s (Interface: %s, UsagePage: 0x%04x, PID: 0x%04x)",
                         path_str, dev_info_to_try.get("interface_number", "N/A"),
                         dev_info_to_try.get("usage_page", 0), dev_info_to_try["product_id"])
            try:
                # Ensure path is bytes as expected by hid.Device constructor
                h_temp = hid.Device(path=dev_info_to_try["path"])
                self.hid_device = h_temp
                self.selected_device_info = dev_info_to_try
                logger.info("Successfully opened HID device: %s on interface %s path %s",
                             dev_info_to_try.get("product_string", "N/A"),
                             dev_info_to_try.get("interface_number", -1), path_str)
                return True
            except Exception as e_open:
                logger.warning("    Failed to open HID device path %s: %s", path_str, str(e_open))
                if h_temp:
                    try:
                        h_temp.close()
                    except Exception: # pylint: disable=broad-except
                        pass # Ignore errors on close during error handling
                continue

        self.hid_device = None
        self.selected_device_info = None
        logger.warning("Failed to connect to any suitable HID interface.")
        return False

    def ensure_connection(self) -> bool:
        """Ensures that a connection to a suitable HID device is active."""
        # (Adapt HeadsetService._ensure_hid_connection)
        if not self.hid_device:
            logger.debug("ensure_connection: No HID device, attempting to connect.")
            return self._connect_device()
        # Could add a check here to see if the device is still responsive, if necessary.
        # For now, assume if hid_device object exists, it's connected.
        return True

    def get_hid_device(self) -> hid.Device | None:
        """Returns the active hid.Device object if connected, otherwise None."""
        if self.ensure_connection():
            return self.hid_device
        return None

    def get_selected_device_info(self) -> dict[str, Any] | None:
        """Returns the device info dictionary of the selected HID device."""
        return self.selected_device_info

    def close(self) -> None:
        """Closes the connection to the HID device."""
        # (Adapt HeadsetService.close)
        if self.hid_device:
            device_path = "unknown path"
            if self.selected_device_info and isinstance(self.selected_device_info.get("path"), bytes):
                device_path = self.selected_device_info["path"].decode("utf-8", errors="replace")
            logger.debug("Closing HID device: %s", device_path)
            try:
                self.hid_device.close()
            except Exception as e: # pylint: disable=broad-except
                logger.warning("Exception while closing HID device %s: %s", device_path, str(e))
            finally:
                self.hid_device = None
                self.selected_device_info = None
        else:
            logger.debug("Close called, but no HID device was open.")
