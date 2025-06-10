"""
Service layer for interacting with the headset.

This module abstracts the HID communication and status parsing, providing a
cleaner interface for the rest of the application to get headset status and
send commands.
"""

import logging
import os
from typing import Any

from . import app_config
from .headset_status import HeadsetCommandEncoder, HeadsetStatusParser
from .hid_communicator import HIDCommunicator
from .hid_manager import HIDConnectionManager
from .udev_manager import (
    UDEV_RULE_FILENAME as STEELSERIES_UDEV_FILENAME,  # Import for udev check
)
from .udev_manager import UDEVManager

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class HeadsetService:
    """Provides an interface to interact with the headset."""

    def __init__(self) -> None:
        """Initializes the HeadsetService."""
        self.hid_connection_manager = HIDConnectionManager()
        self.hid_communicator: HIDCommunicator | None = None
        self.udev_manager = UDEVManager()
        self.status_parser = HeadsetStatusParser()
        self.command_encoder = HeadsetCommandEncoder()

        self.udev_setup_details: dict[str, Any] | None = None
        self._last_hid_only_connection_logged_status: bool | None = None
        self._last_hid_raw_read_data: list[int] | None = (
            None  # Store as list of ints for direct comparison
        )
        self._last_hid_parsed_status: dict[str, Any] | None = None
        self._last_reported_battery_level: int | None = None
        self._last_reported_chatmix: int | None = None
        self._last_reported_charging_status: bool | None = None
        self._last_raw_battery_status_for_logging: int | None = None

        logger.debug("HeadsetService initialized with new component managers.")
        self._ensure_hid_communicator()

    def _ensure_hid_communicator(self) -> bool:
        # Check if current communicator is valid and points to the same device as connection manager
        if (
            self.hid_communicator
            and self.hid_connection_manager.hid_device
            and self.hid_communicator.hid_device
            == self.hid_connection_manager.hid_device
        ):
            return True

        logger.debug(
            "_ensure_hid_communicator: Attempting to establish/refresh HID communicator.",
        )
        if self.hid_connection_manager.ensure_connection():
            active_hid_device = self.hid_connection_manager.get_hid_device()
            if active_hid_device:
                device_info = self.hid_connection_manager.get_selected_device_info()
                if device_info is None:
                    logger.warning(
                        "_ensure_hid_communicator: Got active HID device but no selected_device_info. Using placeholders for HIDCommunicator.",
                    )
                    # Provide a default dictionary that HIDCommunicator's __init__ can handle gracefully
                    device_info_for_comm = {
                        "path": b"unknown_path_service",
                        "product_string": "unknown_product_service",
                    }
                else:
                    device_info_for_comm = device_info

                # Recreate communicator if it's None or if the device object identity has changed.
                # HIDConnectionManager is the source of truth for the current device and its info.
                if (
                    self.hid_communicator is None
                    or self.hid_communicator.hid_device != active_hid_device
                ):
                    self.hid_communicator = HIDCommunicator(
                        hid_device=active_hid_device, device_info=device_info_for_comm,
                    )
                    # The HIDCommunicator's own __init__ log is now sufficient.
                return True
            # Should not happen if ensure_connection() was true and returned a device
            logger.error(
                "_ensure_hid_communicator: Connection manager reported success but no device found by get_hid_device().",
            )
            self.hid_communicator = None  # Ensure communicator is cleared
            return False
        # Connection manager failed to ensure connection
        logger.warning(
            "_ensure_hid_communicator: Failed to ensure HID connection via manager.",
        )
        self.hid_communicator = None  # Ensure communicator is cleared

        # If connection fails, check for udev rules and guide user if missing
        final_rules_path = os.path.join("/etc/udev/rules.d/", STEELSERIES_UDEV_FILENAME)
        if not os.path.exists(final_rules_path):
            logger.info(
                "Udev rules file not found at %s. Triggering interactive udev rule creation guide.",
                final_rules_path,
            )
            if (
                self.udev_manager.create_rules_interactive()
            ):  # This method logs its own success/failure
                self.udev_setup_details = (
                    self.udev_manager.get_last_udev_setup_details()
                )
        else:
            logger.debug(
                "Udev rules file %s exists. Skipping interactive udev guide related to connection failure.",
                final_rules_path,
            )
        return False

    def close(self) -> None:
        """Closes the HID connection and clears the communicator."""
        self.hid_connection_manager.close()  # This will set its hid_device to None
        self.hid_communicator = None  # Clear our communicator instance
        logger.debug(
            "HeadsetService: HID connection closed via manager, local communicator cleared.",
        )

    def _get_parsed_status_hid(self) -> dict[str, Any] | None:
        if not self._ensure_hid_communicator() or not self.hid_communicator:
            if self._last_hid_parsed_status is not None:
                logger.info(
                    "_get_parsed_status_hid: HID communicator not available, clearing last known status.",
                )
            self._last_hid_raw_read_data = None
            self._last_hid_parsed_status = None
            return None

        command_payload = app_config.HID_CMD_GET_STATUS  # This is List[int]
        success_write = self.hid_communicator.write_report(
            report_id=0, data=command_payload,
        )

        if not success_write:
            logger.warning(
                "_get_parsed_status_hid: Failed to write HID status request. Closing connection.",
            )
            # Failure to write often means device is disconnected or in a bad state.
            self.hid_connection_manager.close()  # Close via manager
            self.hid_communicator = None  # Clear local communicator
            if self._last_hid_parsed_status is not None:
                logger.info(
                    "_get_parsed_status_hid: Write failed, clearing last known status.",
                )
            self._last_hid_raw_read_data = None
            self._last_hid_parsed_status = None
            return None

        response_data_bytes = self.hid_communicator.read_report(
            app_config.HID_INPUT_REPORT_LENGTH_STATUS,
        )
        if not response_data_bytes:  # None if read failed or timed out
            if (
                self._last_hid_raw_read_data is not None
            ):  # Log if we previously had data
                logger.debug(
                    "HID read data changed: No data received this time (previously had data).",
                )
            if (
                self._last_hid_parsed_status is not None
            ):  # Log if we are clearing a known status
                logger.info(
                    "_get_parsed_status_hid: Read failed or no data, clearing last known status.",
                )
            self._last_hid_raw_read_data = None
            self._last_hid_parsed_status = None
            return None

        current_raw_data_list = list(
            response_data_bytes,
        )  # Convert bytes to List[int] for comparison
        if current_raw_data_list != self._last_hid_raw_read_data:
            logger.debug(
                "HID read data (raw bytes via communicator): %s",
                response_data_bytes.hex(),
            )
            self._last_hid_raw_read_data = current_raw_data_list

        parsed_status = self.status_parser.parse_status_report(response_data_bytes)
        if not parsed_status:
            logger.warning(
                "_get_parsed_status_hid: Failed to parse status report from received data.",
            )
            if (
                self._last_hid_parsed_status is not None
            ):  # Log if we are clearing a known status
                logger.info(
                    "_get_parsed_status_hid: Parsing failed, clearing last known status.",
                )
            self._last_hid_parsed_status = None  # Still store None if parsing failed
            return None

        # Logging for headset state changes (online, charging, offline)
        raw_battery_status_byte_from_parser = parsed_status.get(
            "raw_battery_status_byte",
        )
        if raw_battery_status_byte_from_parser is not None:
            is_online_from_parser = parsed_status.get("headset_online", False)
            prev_log_status = (
                self._last_raw_battery_status_for_logging
            )  # Previous status byte used for this logging

            if is_online_from_parser:  # Headset is currently online
                is_charging_from_parser = parsed_status.get("battery_charging", False)
                current_effective_status_for_log = (
                    0x01 if is_charging_from_parser else 0x02
                )  # Simple: 0x01 charging, 0x02 online (not charging)

                if (
                    prev_log_status is None or prev_log_status == 0x00
                ):  # Was unknown or offline
                    logger.info(
                        "Headset status change: Now %s (status byte %#02x), was previously offline or unknown.",
                        "charging" if is_charging_from_parser else "online",
                        raw_battery_status_byte_from_parser,
                    )
                elif (
                    is_charging_from_parser and prev_log_status != 0x01
                ):  # Was online but not charging, now charging
                    logger.info(
                        "Headset status change: Now charging (status byte %#02x), was previously online and not charging.",
                        raw_battery_status_byte_from_parser,
                    )
                elif (
                    not is_charging_from_parser and prev_log_status == 0x01
                ):  # Was charging, now online but not charging
                    logger.info(
                        "Headset status change: Now online and not charging (status byte %#02x), was previously charging.",
                        raw_battery_status_byte_from_parser,
                    )
                self._last_raw_battery_status_for_logging = (
                    current_effective_status_for_log
                )
            else:  # Headset is currently offline (raw_battery_status_byte_from_parser was 0x00)
                if (
                    prev_log_status is not None and prev_log_status != 0x00
                ):  # Was previously online or charging
                    logger.info(
                        "Headset status change: Now offline (status byte %#02x), was previously online/charging.",
                        raw_battery_status_byte_from_parser,
                    )
                self._last_raw_battery_status_for_logging = 0x00

        if parsed_status != self._last_hid_parsed_status:
            logger.debug("Parsed HID status (via parser): %s", parsed_status)
            self._last_hid_parsed_status = parsed_status.copy()  # Store a copy
        return parsed_status

    def is_device_connected(self) -> bool:
        """Checks if the headset is connected and functionally online."""
        # This method should quickly check connectivity.
        # It first ensures the communicator is attempted.
        # Then, it relies on _get_parsed_status_hid to determine functional online status.
        self._ensure_hid_communicator()

        if not self.hid_communicator:  # Check after attempting to ensure it
            if (
                self._last_hid_only_connection_logged_status is not False
            ):  # Log only on change to False
                logger.warning(
                    "is_device_connected: HID communicator not available (device path likely NOT active or permissions issue). Reporting as NOT connected.",
                )
                self._last_hid_only_connection_logged_status = False
            return False

        # If communicator exists, try to get status.
        # _get_parsed_status_hid handles its own logging for success/failure.
        status = self._get_parsed_status_hid()
        is_functionally_online = status is not None and status.get(
            "headset_online", False,
        )

        # Log changes in the "functionally online" status for this specific check
        if is_functionally_online != self._last_hid_only_connection_logged_status:
            if is_functionally_online:
                logger.info(
                    "is_device_connected: HID connection is active and headset reports as online.",
                )
            else:
                # This covers cases where communicator exists, but headset is offline or status fails
                logger.info(
                    "is_device_connected: HID path may be active, but headset reported as offline or status query failed. Reporting as NOT connected.",
                )
            self._last_hid_only_connection_logged_status = is_functionally_online

        return is_functionally_online

    def get_battery_level(self) -> int | None:
        """Retrieves the current battery level percentage from the headset."""
        status = self._get_parsed_status_hid()
        if (
            status
            and status.get("headset_online")
            and status.get("battery_percent") is not None
        ):
            current_value = status["battery_percent"]
            if current_value != self._last_reported_battery_level:
                logger.debug("Battery level from parsed status: %s%%", current_value)
                self._last_reported_battery_level = current_value
            return current_value
        # If status is None, or headset_online is False, or battery_percent is None
        if (
            self._last_reported_battery_level is not None
        ):  # Log if we are clearing a known value
            logger.info(
                "get_battery_level: Could not retrieve valid battery level, clearing last known value.",
            )
        self._last_reported_battery_level = None
        return None

    def get_chatmix_value(self) -> int | None:
        """Retrieves the current ChatMix value (0-128) from the headset."""
        status = self._get_parsed_status_hid()
        if (
            status
            and status.get("headset_online")
            and status.get("chatmix") is not None
        ):
            current_value = status["chatmix"]
            if current_value != self._last_reported_chatmix:
                logger.debug("ChatMix value from parsed status: %s", current_value)
                self._last_reported_chatmix = current_value
            return current_value
        if (
            self._last_reported_chatmix is not None
        ):  # Log if we are clearing a known value
            logger.info(
                "get_chatmix_value: Could not retrieve valid chatmix value, clearing last known value.",
            )
        self._last_reported_chatmix = None
        return None

    def is_charging(self) -> bool | None:
        """Checks if the headset is currently charging."""
        status = self._get_parsed_status_hid()
        if (
            status
            and status.get("headset_online")
            and status.get("battery_charging") is not None
        ):
            current_value = status["battery_charging"]
            if current_value != self._last_reported_charging_status:
                logger.debug("Charging status from parsed status: %s", current_value)
                self._last_reported_charging_status = current_value
            return current_value
        if (
            self._last_reported_charging_status is not None
        ):  # Log if we are clearing a known value
            logger.info(
                "is_charging: Could not retrieve valid charging status, clearing last known value.",
            )
        self._last_reported_charging_status = None
        return None

    def _generic_set_command(
        self,
        command_name_log: str,
        encoded_payload: list[int] | None,
        report_id: int = 0,
    ) -> bool:
        if not self._ensure_hid_communicator() or not self.hid_communicator:
            logger.warning(
                "%s: HID communicator not available. Cannot send command.",
                command_name_log,
            )
            return False

        if encoded_payload is None:  # Encoder might return None if input is invalid
            logger.error(
                "%s: Encoded payload is None (likely due to invalid input to encoder). Command not sent.",
                command_name_log,
            )
            return False

        success = self.hid_communicator.write_report(
            report_id=report_id, data=encoded_payload,
        )
        if success:
            logger.info("%s: Successfully sent command.", command_name_log)
        else:
            logger.warning(
                "%s: Failed to send command via communicator. Closing HID connection as it might be stale.",
                command_name_log,
            )
            self.hid_connection_manager.close()  # Close via manager
            self.hid_communicator = None  # Clear local communicator
        return success

    def set_sidetone_level(self, level: int) -> bool:
        """Sets the sidetone level on the headset."""
        # UI scale 0-128, encoder handles mapping to HW values
        clamped_level = max(0, min(128, level))
        payload = self.command_encoder.encode_set_sidetone(clamped_level)
        return self._generic_set_command(
            f"Set Sidetone (UI level {clamped_level})", payload, report_id=0,
        )

    def set_inactive_timeout(self, minutes: int) -> bool:
        """Sets the inactive timeout (in minutes) on the headset."""
        clamped_minutes = max(
            0, min(90, minutes),
        )  # Encoder also clamps, but good practice here too
        payload = self.command_encoder.encode_set_inactive_timeout(clamped_minutes)
        return self._generic_set_command(
            f"Set Inactive Timeout ({clamped_minutes}min)", payload, report_id=0,
        )

    def set_eq_values(self, values: list[float]) -> bool:
        """Sets custom equalizer values on the headset."""
        # values are typically -10.0 to 10.0 dB for 10 bands
        payload = self.command_encoder.encode_set_eq_values(values)
        # report_id=0 is used as HID_CMD_SET_EQ_BANDS_PREFIX likely starts with 0x00 or similar,
        # or it's an unnumbered report where the first byte of prefix is data.
        # The HIDCommunicator handles prepending a report ID only if report_id > 0.
        return self._generic_set_command(
            f"Set EQ Values ({values})", payload, report_id=0,
        )

    def set_eq_preset_id(self, preset_id: int) -> bool:
        """Sets a hardware equalizer preset on the headset by its ID."""
        # preset_id is an integer key from app_config.ARCTIS_NOVA_7_HW_PRESETS
        payload = self.command_encoder.encode_set_eq_preset_id(preset_id)
        return self._generic_set_command(
            f"Set EQ Preset ID ({preset_id})", payload, report_id=0,
        )

    def get_udev_setup_details(self) -> dict[str, Any] | None:
        """Returns details about udev setup if guided during the current session."""
        # This returns details if udev setup was guided *during this session*
        return self.udev_setup_details
