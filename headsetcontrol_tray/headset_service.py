import logging
import os

# import re # No longer needed
# import subprocess # No longer needed
import tempfile
from typing import Any, TypedDict

# import json # No longer needed if _get_headset_device_json is removed and not used elsewhere
import hid

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
    level: int | None
    status_text: str | None

class HeadsetService:
    """
    Service class to interact with the SteelSeries headset via CLI and HID.
    """
    def __init__(self):
        self.hid_device: hid.Device | None = None
        self.device_path: bytes | None = None
        self.udev_setup_details = None # Initialize details for udev rule setup
        self._last_hid_only_connection_logged_status: bool | None = None
        self._last_hid_raw_read_data: list[int] | None = None
        self._last_hid_parsed_status: dict[str, Any] | None = None
        self._last_reported_battery_level: int | None = None
        self._last_reported_chatmix: int | None = None
        self._last_reported_charging_status: bool | None = None
        self._last_raw_battery_status_for_logging: int | None = None

        logger.debug("HeadsetService initialized. Attempting initial HID connection.")
        self._connect_hid_device()

    def _create_udev_rules(self) -> bool:
        """
        Creates the udev rule file in a temporary location and instructs the user.
        Stores information about the created temporary file if successful.
        """
        final_rules_path_str = os.path.join("/etc/udev/rules.d/", UDEV_RULE_FILENAME)
        logger.info(f"Attempting to guide user for udev rule creation for {final_rules_path_str}")
        self.udev_setup_details = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="headsetcontrol_") as tmp_file:
                temp_file_name = tmp_file.name
                tmp_file.write(UDEV_RULE_CONTENT + "\n")
            self.udev_setup_details = {
                "temp_file_path": temp_file_name,
                "final_file_path": final_rules_path_str,
                "rule_filename": UDEV_RULE_FILENAME,
            }
            logger.info(f"Successfully wrote udev rule content to temporary file: {temp_file_name}")
            logger.info("--------------------------------------------------------------------------------")
            logger.info("ACTION REQUIRED: To complete headset setup, please run the following commands:")
            logger.info(f'1. Copy the rule file: sudo cp "{temp_file_name}" "{final_rules_path_str}"')
            logger.info("2. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger")
            logger.info("3. Replug your SteelSeries headset.")
            logger.info(f"(The temporary file {temp_file_name} can be deleted after copying.)")
            logger.info("--------------------------------------------------------------------------------")
            return True
        except OSError as e:
            logger.error(f"Could not write temporary udev rule file: {e}")
            self.udev_setup_details = None
            return False
        except Exception as e_global:
            logger.error(f"An unexpected error occurred during temporary udev rule file creation: {e_global}")
            self.udev_setup_details = None
            return False

    def _connect_hid_device(self) -> bool:
        """Attempts to connect to the headset via HID by trying suitable interfaces."""
        if self.hid_device:
            logger.debug("_connect_hid_device: Already connected.")
            return True

        logger.debug(f"_connect_hid_device: Trying to connect. Target PIDs: {app_config.TARGET_PIDS}")
        try:
            devices_enum = hid.enumerate(STEELSERIES_VID, 0)
            logger.debug(f"Found {len(devices_enum)} SteelSeries VID devices during enumeration.")
        except Exception as e_enum:
            logger.error(f"Error enumerating HID devices: {e_enum}")
            devices_enum = []

        potential_devices_to_try = []
        for dev_info in devices_enum:
            logger.debug(f"  Enumerated device: PID=0x{dev_info['product_id']:04x}, Release=0x{dev_info.get('release_number', 0):04x}, "
                         f"Interface={dev_info.get('interface_number', 'N/A')}, UsagePage=0x{dev_info.get('usage_page', 0):04x}, "
                         f"Usage=0x{dev_info.get('usage', 0):04x}, Path={dev_info['path'].decode('utf-8', errors='replace')}, "
                         f"Product='{dev_info.get('product_string', 'N/A')}'")
            if dev_info["product_id"] in TARGET_PIDS:
                logger.debug(f"    Device matches target PID 0x{dev_info['product_id']:04x}. Adding to potential list.")
                potential_devices_to_try.append(dev_info)

        if potential_devices_to_try:
            def sort_key(d_info):
                if d_info["vendor_id"] == app_config.STEELSERIES_VID and \
                   d_info["product_id"] in app_config.TARGET_PIDS and \
                   d_info.get("interface_number") == app_config.HID_REPORT_INTERFACE and \
                   d_info.get("usage_page") == app_config.HID_REPORT_USAGE_PAGE and \
                   d_info.get("usage") == app_config.HID_REPORT_USAGE_ID:
                    logger.debug(f"  SortKey: Prioritizing exact Arctis Nova 7 interface (0) for PID 0x{d_info.get('product_id'):04x}")
                    return -2
                if d_info.get("product_id") == 0x2202 and d_info.get("interface_number") == 0:
                    logger.debug(f"  SortKey: Prioritizing interface 0 for PID 0x{d_info.get('product_id'):04x} (-1)")
                    return -1
                if d_info.get("interface_number") == 3:
                    logger.debug(f"  SortKey: Prioritizing interface 3 (generic) for PID 0x{d_info.get('product_id'):04x} (0)")
                    return 0
                if d_info.get("usage_page") == 0xFFC0:
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
                    h_temp = hid.Device(path=dev_info_to_try["path"])
                    self.hid_device = h_temp
                    self.device_path = dev_info_to_try["path"]
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
        else: # potential_devices_to_try was empty
            logger.debug("_connect_hid_device: No devices found matching target PIDs after enumeration.")

        self.hid_device = None
        self.device_path = None
        logger.warning("Failed to connect to any suitable HID interface. Udev rules might be missing or incorrect, or the device is off.")
        self._create_udev_rules()
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

    def _write_hid_report(self, report_id: int, data: list[int], report_length: int = 64) -> bool:
        """
        Writes a report to the HID device.
        Prepends report_id if it's > 0.
        Pads data to report_length.

        The `report_id` is prefixed to `data` if `report_id > 0`.
        The combined message is then passed to `self.hid_device.write()`.
        This method is intended for sending command/control data to the headset
        once the correct report IDs and data structures are known.
        """
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_write_hid_report: No HID device connected (low-level).")
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
            if bytes_written <= 0:
                logger.warning(f"HID write returned {bytes_written}, closing potentially stale HID handle.")
                self.close()
                return False
            return True
        except Exception as e:
            logger.error(f"HID write error: {e}. Closing potentially stale HID handle.")
            self.close()
            return False

    def _read_hid_report(self, report_id_to_request: int | None = None, report_length: int = 64, timeout_ms: int = 1000) -> list[int] | None:
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
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_read_hid_report: No HID device connected (low-level).")
            return None

        logger.debug(f"Reading HID report: ReportIDToRequest={report_id_to_request}, Length={report_length}, Timeout={timeout_ms}ms")
        try:
            data: list[int] | None = None
            if report_id_to_request is not None:
                logger.debug(f"Attempting to read Input report, expecting report ID {report_id_to_request} if numbered.")
                raw_data = self.hid_device.read(report_length)
                if raw_data and report_id_to_request is not None and raw_data[0] == report_id_to_request:
                    data = raw_data[1:]
                    logger.debug(f"Stripped report ID {report_id_to_request} from received data.")
                elif raw_data and report_id_to_request is None:
                    data = raw_data
                else:
                    data = raw_data
            else:
                data = self.hid_device.read(report_length)

            if data:
                logger.debug(f"HID read data: {bytes(data).hex()}")
                return list(data)
            logger.debug("HID read no data (timeout or empty report).")
            return None
        except Exception as e:
            logger.error(f"HID read error: {e}. Closing potentially stale HID handle.")
            self.close()
            return None

    def is_device_connected(self) -> bool:
        if self.hid_device is None:
            self._ensure_hid_connection()

        if self.hid_device is None:
            if self._last_hid_only_connection_logged_status is not False:
                logger.warning("is_device_connected (HID mode): HID device path NOT active (dongle likely disconnected or permissions issue).")
                self._last_hid_only_connection_logged_status = False
            return False

        status = self._get_parsed_status_hid()
        is_functionally_online = status is not None and status.get("headset_online", False)
        current_overall_connected_status = is_functionally_online

        if current_overall_connected_status != self._last_hid_only_connection_logged_status:
            if current_overall_connected_status:
                logger.info("is_device_connected (HID mode): Direct HID connection is active and headset is online.")
            elif self.hid_device is not None and not is_functionally_online :
                logger.info("is_device_connected (HID mode): HID device path active, but headset reported as offline.")
            else:
                logger.warning("is_device_connected (HID mode): Direct HID connection is NOT active or failed.")
            self._last_hid_only_connection_logged_status = current_overall_connected_status
        else:
            logger.debug(f"is_device_connected (HID mode): Connection status remains {'active and online' if current_overall_connected_status else 'inactive or offline'} (logged at DEBUG to reduce noise).")
        return current_overall_connected_status

    def get_battery_level(self) -> int | None:
        logger.debug("get_battery_level: Attempting via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("battery_percent") is not None:
            current_value = status["battery_percent"]
            if current_value != self._last_reported_battery_level:
                logger.debug(f"Battery level from HID: {current_value}%")
                self._last_reported_battery_level = current_value
            else:
                logger.debug(f"Battery level from HID: {current_value}% (unchanged, VERBOSE suppressed).")
            return current_value
        self._last_reported_battery_level = None
        if status is not None and not status.get("headset_online"):
            logger.info("get_battery_level: Headset reported itself as offline via HID. No value retrieved from HID.")
        else:
            logger.warning("get_battery_level: HID communication failed (or status was unexpected). No value retrieved.")
        return None

    def _get_parsed_status_hid(self) -> dict[str, Any] | None:
        logger.debug("Attempting _get_parsed_status_hid.")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_get_parsed_status_hid: No HID device connected or connection failed.")
            self._last_hid_raw_read_data = None
            self._last_hid_parsed_status = None
            return None
        command_payload = app_config.HID_CMD_GET_STATUS
        success_write = self._write_hid_report(
            report_id=0,
            data=command_payload,
            report_length=len(command_payload),
        )
        if not success_write:
            logger.warning("_get_parsed_status_hid: Failed to write HID status request command.")
            return None
        response_data = self.hid_device.read(app_config.HID_INPUT_REPORT_LENGTH_STATUS)
        if not response_data:
            logger.warning("_get_parsed_status_hid: No response data from HID device.")
            if self._last_hid_raw_read_data is not None:
                logger.debug("HID read data changed: No data received (previously had data).")
            self._last_hid_raw_read_data = None
            self._last_hid_parsed_status = None
            return None
        if len(response_data) < app_config.HID_INPUT_REPORT_LENGTH_STATUS:
            logger.warning(
                f"_get_parsed_status_hid: Incomplete response. Expected {app_config.HID_INPUT_REPORT_LENGTH_STATUS} bytes, got {len(response_data)}: {response_data}",
            )
            self._last_hid_raw_read_data = None
            self._last_hid_parsed_status = None
            return None
        current_raw_data_list = list(response_data)
        if current_raw_data_list != self._last_hid_raw_read_data:
            logger.debug(f"HID read data: {bytes(response_data).hex()}")
            self._last_hid_raw_read_data = current_raw_data_list
        else:
            logger.debug("HID read data: No change since last report.")
        parsed_status = {"headset_online": True}
        raw_battery_level = response_data[app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE]
        if raw_battery_level == 0x00:
            parsed_status["battery_percent"] = 0
        elif raw_battery_level == 0x01:
            parsed_status["battery_percent"] = 25
        elif raw_battery_level == 0x02:
            parsed_status["battery_percent"] = 50
        elif raw_battery_level == 0x03:
            parsed_status["battery_percent"] = 75
        elif raw_battery_level == 0x04:
            parsed_status["battery_percent"] = 100
        else:
            logger.warning(f"_get_parsed_status_hid: Unknown raw battery level: {raw_battery_level}")
            parsed_status["battery_percent"] = None
        raw_battery_status = response_data[app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE]
        if raw_battery_status == 0x00:
            if self._last_raw_battery_status_for_logging != 0x00:
                logger.info("_get_parsed_status_hid: Headset reported offline by status byte (0x00).")
            parsed_status["battery_charging"] = None
            parsed_status["headset_online"] = False
            parsed_status["battery_percent"] = None
            parsed_status["chatmix"] = None
        elif raw_battery_status == 0x01:
            if self._last_raw_battery_status_for_logging == 0x00:
                logger.info(f"_get_parsed_status_hid: Headset now reported as charging (status byte {raw_battery_status:#02x}), was previously offline by status byte.")
            parsed_status["battery_charging"] = True
        else:
            if self._last_raw_battery_status_for_logging == 0x00:
                logger.info(f"_get_parsed_status_hid: Headset now reported as online (status byte {raw_battery_status:#02x}), was previously offline by status byte.")
            parsed_status["battery_charging"] = False
        self._last_raw_battery_status_for_logging = raw_battery_status
        if parsed_status["headset_online"]:
            raw_game = response_data[app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE]
            raw_chat = response_data[app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE]
            raw_game_clamped = max(0, min(100, raw_game))
            raw_chat_clamped = max(0, min(100, raw_chat))
            mapped_game = int((raw_game_clamped / 100.0) * 64.0)
            mapped_chat = int((raw_chat_clamped / 100.0) * -64.0)
            chatmix_value = 64 - (mapped_chat + mapped_game)
            parsed_status["chatmix"] = max(0, min(128, chatmix_value))
        else:
            pass
        if parsed_status != self._last_hid_parsed_status:
            logger.debug(f"_get_parsed_status_hid: Parsed status: {parsed_status}")
            self._last_hid_parsed_status = parsed_status.copy()
        else:
            logger.debug("_get_parsed_status_hid: Parsed status: No change since last report.")
        return parsed_status

    def get_battery_level_hid(self) -> int | None:
        logger.debug("get_battery_level_hid: Attempting to get battery via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("battery_percent") is not None:
            return status["battery_percent"]
        logger.warning("get_battery_level_hid: Could not retrieve battery level via HID.")
        return None

    def get_chatmix_hid(self) -> int | None:
        logger.debug("get_chatmix_hid: Attempting to get chatmix via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("chatmix") is not None:
            return status["chatmix"]
        logger.warning("get_chatmix_hid: Could not retrieve chatmix via HID.")
        return None

    def is_charging_hid(self) -> bool | None:
        """Checks if the headset is currently charging using HID."""
        logger.debug("is_charging_hid: Attempting to get charging status via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("battery_charging") is not None:
            return status["battery_charging"]
        logger.warning("is_charging_hid: Could not retrieve charging status via HID.")
        return None

    def get_chatmix_value(self) -> int | None:
        logger.debug("get_chatmix_value: Attempting via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("chatmix") is not None:
            current_value = status["chatmix"]
            if current_value != self._last_reported_chatmix:
                logger.debug(f"ChatMix value from HID: {current_value}")
                self._last_reported_chatmix = current_value
            else:
                logger.debug(f"ChatMix value from HID: {current_value} (unchanged, VERBOSE suppressed).")
            return current_value
        self._last_reported_chatmix = None
        if status is not None and not status.get("headset_online"):
            logger.info("get_chatmix_value: Headset reported itself as offline via HID. No value retrieved from HID.")
        else:
            logger.warning("get_chatmix_value: HID communication failed (or status was unexpected). No value retrieved.")
        return None

    def is_charging(self) -> bool | None:
        logger.debug("is_charging: Attempting via direct HID.")
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("battery_charging") is not None:
            current_value = status["battery_charging"]
            if current_value != self._last_reported_charging_status:
                logger.debug(f"Charging status from HID: {current_value}")
                self._last_reported_charging_status = current_value
            else:
                logger.debug(f"Charging status from HID: {current_value} (unchanged, VERBOSE suppressed).")
            return current_value
        self._last_reported_charging_status = None
        if status is not None and not status.get("headset_online"):
            logger.info("is_charging: Headset reported itself as offline via HID. No value retrieved from HID.")
        else:
            logger.warning("is_charging: HID communication failed (or status was unexpected). No value retrieved.")
        return None

    def get_sidetone_level(self) -> int | None:
        logger.warning("get_sidetone_level: Cannot retrieve via HID (not implemented) and CLI fallback removed.")
        return None

    def set_sidetone_level(self, level: int) -> bool:
        logger.debug(f"set_sidetone_level: Attempting to set level to {level} via direct HID.")
        level = max(0, min(128, level))
        if self._set_sidetone_level_hid(level):
            return True
        logger.warning(f"set_sidetone_level: Direct HID failed for level {level}.")
        return False

    def _set_sidetone_level_hid(self, level: int) -> bool:
        logger.debug(f"Attempting _set_sidetone_level_hid to {level}.")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_set_sidetone_level_hid: No HID device connected or connection failed.")
            return False
        mapped_value = 0
        if level < 26:
            mapped_value = 0x00
        elif level < 51:
            mapped_value = 0x01
        elif level < 76:
            mapped_value = 0x02
        else:
            mapped_value = 0x03
        logger.debug(f"_set_sidetone_level_hid: Input level {level} mapped to hardware value {mapped_value}.")
        command_payload = list(app_config.HID_CMD_SET_SIDETONE_PREFIX)
        command_payload.append(mapped_value)
        success = self._write_hid_report(
            report_id=0,
            data=command_payload,
            report_length=len(command_payload),
        )
        if success:
            logger.info(f"_set_sidetone_level_hid: Successfully sent command for level {level} (mapped: {mapped_value}).")
        else:
            logger.warning(f"_set_sidetone_level_hid: Failed to send command for level {level}.")
        return success

    def _set_inactive_timeout_hid(self, minutes: int) -> bool:
        logger.debug(f"Attempting _set_inactive_timeout_hid to {minutes} minutes.")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_set_inactive_timeout_hid: No HID device connected or connection failed.")
            return False
        if not (0 <= minutes <= 90):
            logger.warning(f"_set_inactive_timeout_hid: Invalid value for minutes ({minutes}). Must be 0-90.")
        command_payload = list(app_config.HID_CMD_SET_INACTIVE_TIME_PREFIX)
        command_payload.append(minutes)
        success = self._write_hid_report(
            report_id=0,
            data=command_payload,
            report_length=len(command_payload),
        )
        if success:
            logger.info(f"_set_inactive_timeout_hid: Successfully sent command for {minutes} minutes.")
        else:
            logger.warning(f"_set_inactive_timeout_hid: Failed to send command for {minutes} minutes.")
        return success

    def get_inactive_timeout(self) -> int | None:
        logger.warning("get_inactive_timeout: Cannot retrieve via HID (not implemented) and CLI fallback removed.")
        return None

    def set_inactive_timeout(self, minutes: int) -> bool:
        logger.debug(f"set_inactive_timeout: Attempting to set to {minutes} minutes via direct HID.")
        clamped_minutes = max(0, min(90, minutes))
        if clamped_minutes != minutes:
            logger.info(f"set_inactive_timeout: Requested minutes {minutes} clamped to {clamped_minutes}.")
        if self._set_inactive_timeout_hid(clamped_minutes):
            return True
        logger.warning(f"set_inactive_timeout: Direct HID failed for {clamped_minutes} minutes.")
        return False

    def _set_eq_values_hid(self, float_values: list[float]) -> bool:
        logger.debug(f"Attempting _set_eq_values_hid with bands: {float_values}")
        if not self._ensure_hid_connection() or not self.hid_device:
            logger.warning("_set_eq_values_hid: No HID device connected or connection failed.")
            return False
        if len(float_values) != 10:
            logger.error(f"_set_eq_values_hid: Invalid number of EQ bands. Expected 10, got {len(float_values)}.")
            return False
        command_payload = list(app_config.HID_CMD_SET_EQ_BANDS_PREFIX)
        for val in float_values:
            clamped_val = max(-10.0, min(10.0, val))
            byte_value = int(0x14 + clamped_val)
            byte_value = max(0, min(255, byte_value))
            command_payload.append(byte_value)
        if len(command_payload) == 12:
            command_payload.append(0x00)
        else:
            logger.error(f"_set_eq_values_hid: Error constructing EQ payload. Length before terminator: {len(command_payload)}")
            return False
        logger.debug(f"_set_eq_values_hid: Constructed payload: {command_payload}")
        success = self._write_hid_report(
            report_id=0,
            data=command_payload,
            report_length=len(command_payload),
        )
        if success:
            logger.info(f"_set_eq_values_hid: Successfully sent custom EQ bands: {float_values}")
        else:
            logger.warning("_set_eq_values_hid: Failed to send custom EQ bands.")
        return success

    def get_current_eq_values(self) -> list[float] | None:
        logger.warning("get_current_eq_values: Cannot retrieve via HID (not implemented) and CLI fallback removed.")
        return None

    def set_eq_values(self, values: list[float]) -> bool:
        logger.debug(f"set_eq_values: Attempting to set EQ bands to {values} via direct HID.")
        if self._set_eq_values_hid(values):
            return True
        logger.warning(f"set_eq_values: Direct HID failed for EQ bands {values}.")
        return False

    def _set_eq_preset_hid(self, preset_id: int) -> bool:
        logger.debug(f"Attempting _set_eq_preset_hid for preset ID: {preset_id}")
        if preset_id not in app_config.ARCTIS_NOVA_7_HW_PRESETS:
            logger.error(f"_set_eq_preset_hid: Invalid preset ID: {preset_id}. Not found in ARCTIS_NOVA_7_HW_PRESETS.")
            return False
        preset_data = app_config.ARCTIS_NOVA_7_HW_PRESETS[preset_id]
        float_values = preset_data.get("values")
        if not float_values or len(float_values) != 10:
            logger.error(f"_set_eq_preset_hid: Malformed preset data for ID {preset_id} in app_config.ARCTIS_NOVA_7_HW_PRESETS.")
            return False
        logger.info(f"_set_eq_preset_hid: Setting hardware preset '{preset_data.get('name', 'Unknown')}' (ID: {preset_id}) using its defined bands.")
        return self._set_eq_values_hid(float_values)

    def get_current_eq_preset_id(self) -> int | None:
        logger.warning("get_current_eq_preset_id: Cannot retrieve via HID (not implemented) and CLI fallback removed.")
        return None

    def set_eq_preset_id(self, preset_id: int) -> bool:
        logger.debug(f"set_eq_preset_id: Attempting to set HW EQ preset to ID {preset_id} via direct HID.")
        if not (0 <= preset_id <= 3):
            logger.error(f"set_eq_preset_id: Invalid HW EQ preset ID: {preset_id}. Typically 0-3.")
        if self._set_eq_preset_hid(preset_id):
            return True
        logger.warning(f"set_eq_preset_id: Direct HID failed for HW EQ preset ID {preset_id}.")
        return False
