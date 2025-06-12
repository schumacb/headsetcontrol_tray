import logging
from typing import Any, Optional, Tuple # Ensure Tuple is imported

import hid

from . import app_config
from .os_layer.base import HIDManagerInterface # Added import

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Specific interface numbers for sorting preference (already defined in app_config)
# STEELSERIES_INTERFACE_0 = 0 # app_config.ARCTIS_NOVA_7_USER_INTERFACE
# STEELSERIES_INTERFACE_3 = 3 # app_config.HID_REPORT_INTERFACE

# Define HidDevice type alias for clarity, using hid.Device
HidDevice = hid.Device # Correctly use hid.Device (from hidapi library)

class HIDConnectionManager(HIDManagerInterface): # Inherit from HIDManagerInterface
    """Handles the discovery, connection, sorting, and lifecycle for SteelSeries HID devices."""

    def __init__(self) -> None:
        """Initializes the HIDConnectionManager."""
        self.hid_device: Optional[HidDevice] = None # Use Optional[HidDevice]
        self.selected_device_info: Optional[dict[str, Any]] = None
        logger.debug("HIDConnectionManager initialized.")

    def find_potential_hid_devices(self) -> list[dict[str, Any]]: # Renamed and matches plan
        logger.debug(
            "Enumerating HID devices for VID 0x%04x, Target PIDs: %s",
            app_config.STEELSERIES_VID,
            [f"0x{pid:04x}" for pid in app_config.TARGET_PIDS], # Log PIDs in hex
        )
        try:
            # hid.enumerate can take optional vid and pid.
            # Passing 0 for pid means any product ID for that vendor.
            devices_enum = hid.enumerate(app_config.STEELSERIES_VID, 0)
            logger.debug(
                "Found %s devices with VID 0x%04x during initial enumeration.",
                len(devices_enum),
                app_config.STEELSERIES_VID,
            )
        except hid.HIDException as e:
            logger.exception("Error enumerating HID devices: %s", e)
            return []

        potential_devices = []
        for dev_info in devices_enum:
            # Log device details using .get for optional fields
            logger.debug(
                (
                    "  Enumerated device: PID=0x%04x, Release=0x%04x, Interface=%s, "
                    "UsagePage=0x%04x, Usage=0x%04x, Path=%s, Product='%s', Manufacturer='%s'"
                ),
                dev_info["product_id"],
                dev_info.get("release_number", 0),
                dev_info.get("interface_number", "N/A"),
                dev_info.get("usage_page", 0),
                dev_info.get("usage", 0),
                dev_info.get("path", b"N/A").decode("utf-8", errors="replace"), # Ensure path is decoded
                dev_info.get("product_string", "N/A"),
                dev_info.get("manufacturer_string", "N/A"),
            )
            if dev_info["product_id"] in app_config.TARGET_PIDS:
                logger.debug(
                    "    Device PID 0x%04x matches target PIDs. Adding to potential list.",
                    dev_info["product_id"],
                )
                potential_devices.append(dev_info)
            else:
                logger.debug(
                    "    Device PID 0x%04x does not match target PIDs.",
                    dev_info["product_id"],
                )
        logger.info(
            "Found %d potential devices matching VID and Target PIDs.",
            len(potential_devices)
        )
        return potential_devices

    def sort_hid_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]: # Renamed and matches plan
        # Sort key based on interface number, usage page, and specific PIDs.
        # Higher preference (lower sort key value) for more specific matches.
        def sort_key(d_info: dict[str, Any]) -> int:
            pid = d_info["product_id"]
            interface = d_info.get("interface_number", -1) # Default to -1 if not present
            usage_page = d_info.get("usage_page", 0)
            usage = d_info.get("usage", 0) # Added usage for more specificity

            # Highest priority: Exact match for primary HID interface defined in app_config
            if (
                interface == app_config.HID_REPORT_INTERFACE
                and usage_page == app_config.HID_REPORT_USAGE_PAGE
                and usage == app_config.HID_REPORT_USAGE_ID # Check usage ID as well
            ):
                logger.debug(
                    "  SortKey: Prioritizing exact match (interface %s, usage page 0x%04x, usage 0x%04x) for PID 0x%04x -> -3",
                    interface, usage_page, usage, pid,
                )
                return -3 # Highest priority

            # Next priority: Specific known PIDs with their common primary interface (e.g., Arctis Nova 7 specific interface if different)
            # Example: if ARCTIS_NOVA_7_USER_PID has a preferred interface that's not the generic one above
            if (
                pid == app_config.ARCTIS_NOVA_7_USER_PID and
                interface == app_config.ARCTIS_NOVA_7_USER_INTERFACE # Assuming this constant exists or is 0
            ):
                logger.debug(
                    "  SortKey: Prioritizing specific PID 0x%04x with interface %s -> -2",
                    pid, interface
                )
                return -2

            # General SteelSeries interface (e.g., interface 3)
            if interface == app_config.HID_REPORT_INTERFACE:
                logger.debug(
                    "  SortKey: Prioritizing general SteelSeries interface %s for PID 0x%04x -> -1",
                    interface, pid,
                )
                return -1

            # General SteelSeries usage page if interface didn't match specifically
            if usage_page == app_config.HID_REPORT_USAGE_PAGE:
                logger.debug(
                    "  SortKey: Prioritizing usage page 0x%04x for PID 0x%04x -> 0",
                    usage_page, pid,
                )
                return 0

            logger.debug(
                "  SortKey: Default priority 1 for PID 0x%04x, Interface %s, UsagePage 0x%04x",
                pid, interface, usage_page,
            )
            return 1 # Lowest priority for other matches

        # Sort devices using the defined key
        # The list should be mutable for sort()
        mutable_devices = list(devices)
        mutable_devices.sort(key=sort_key)

        logger.debug("Sorted %d potential devices:", len(mutable_devices))
        for i, d in enumerate(mutable_devices):
            path_str = d.get("path", b"N/A").decode("utf-8", errors="replace")
            logger.debug(
                "  Device %s: PID=0x%04x, Interface=%s, UsagePage=0x%04x, Path=%s",
                i + 1,
                d["product_id"],
                d.get("interface_number", "N/A"),
                d.get("usage_page", 0),
                path_str,
            )
        return mutable_devices

    # This method signature now matches HIDManagerInterface
    def connect_device(self) -> Tuple[Optional[HidDevice], Optional[dict[str, Any]]]:
        if self.hid_device:
            logger.debug("connect_device: Already connected. Returning existing device.")
            return self.hid_device, self.selected_device_info

        logger.debug("connect_device: Attempting to find and connect to a new device.")
        potential_devices = self.find_potential_hid_devices() # Use renamed public method

        if not potential_devices:
            logger.warning("connect_device: No potential HID devices found after enumeration.")
            self.hid_device = None
            self.selected_device_info = None
            return None, None

        sorted_devices = self.sort_hid_devices(potential_devices) # Use renamed public method

        for dev_info_to_try in sorted_devices:
            path_bytes = dev_info_to_try.get("path")
            if not path_bytes:
                logger.warning("  Skipping device due to missing path: %s", dev_info_to_try)
                continue

            path_str = path_bytes.decode("utf-8", errors="replace")
            logger.info(
                ("  Attempting to open path: %s (PID: 0x%04x, Interface: %s, UsagePage: 0x%04x)"),
                path_str,
                dev_info_to_try["product_id"],
                dev_info_to_try.get("interface_number", "N/A"),
                dev_info_to_try.get("usage_page", 0),
            )
            try:
                # hid.Device constructor expects path to be bytes or str.
                # hidapi library usually handles bytes path correctly.
                h_temp = hid.Device(path=path_bytes) # type: ignore # hid.Device is hid.device which is Any
                # If hid.Device is correctly typed as hid.device, type: ignore might not be needed.
            except hid.HIDException as e:
                logger.warning("    Failed to open HID device path %s: %s", path_str, e)
                continue
            except Exception as e: # Catch other potential errors like OSError
                logger.exception("    An unexpected error occurred opening HID device path %s: %s", path_str, e)
                continue
            else:
                self.hid_device = h_temp
                self.selected_device_info = dev_info_to_try
                product_string = dev_info_to_try.get("product_string", "Unknown Product")
                logger.info(
                    ("Successfully opened HID device: %s on interface %s (Path: %s)"),
                    product_string,
                    dev_info_to_try.get("interface_number", "N/A"),
                    path_str,
                )
                return self.hid_device, self.selected_device_info

        self.hid_device = None
        self.selected_device_info = None
        logger.warning("Failed to connect to any suitable HID interface after trying all potential devices.")
        return None, None


    def ensure_connection(self) -> bool: # Name matches plan
        if self.hid_device:
            # Could add a check here to see if the device is still responsive,
            # e.g., by trying a benign read or checking if path is still valid.
            # For now, if hid_device object exists, assume it's connected.
            return True

        logger.debug("ensure_connection: No HID device currently connected. Attempting to connect.")
        hid_dev, _ = self.connect_device() # connect_device now returns the tuple
        return hid_dev is not None

    def get_hid_device(self) -> Optional[HidDevice]: # Name matches plan
        # ensure_connection will try to connect if not already.
        # if self.ensure_connection():
        #    return self.hid_device
        # return None
        # Simpler: just return current state, connect_device or ensure_connection should be called explicitly if needed by service layer
        return self.hid_device


    def get_selected_device_info(self) -> Optional[dict[str, Any]]: # Name matches plan
        return self.selected_device_info

    def close(self) -> None: # Name matches plan
        if self.hid_device:
            device_path_str = "unknown path"
            if self.selected_device_info and isinstance(self.selected_device_info.get("path"), bytes):
                device_path_str = self.selected_device_info["path"].decode("utf-8", errors="replace")

            logger.info("Closing HID device: %s", device_path_str)
            try:
                self.hid_device.close()
            except hid.HIDException as e: # Catch hid.HIDException specifically
                logger.exception("HIDException while closing HID device %s: %s", device_path_str, e)
            except Exception as e: # Catch any other error during close
                logger.exception("Unexpected error while closing HID device %s: %s", device_path_str, e)
            finally:
                self.hid_device = None
                self.selected_device_info = None
        else:
            logger.debug("Close called, but no HID device was open.")
