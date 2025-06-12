import logging
from pathlib import Path # Keep for now, though STEELSERIES_UDEV_FILENAME is removed
from typing import Any

from . import app_config
from .headset_status import HeadsetCommandEncoder, HeadsetStatusParser
from .hid_communicator import HIDCommunicator
from .os_layer.base import HIDManagerInterface # Added
# UDEVManager and STEELSERIES_UDEV_FILENAME removed

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class HeadsetService:
    """Provides an interface to interact with the headset."""

    def __init__(self, hid_manager: HIDManagerInterface) -> None: # Modified signature
        """Initializes the HeadsetService."""
        self.hid_manager = hid_manager # Use passed-in hid_manager
        self.hid_communicator: HIDCommunicator | None = None
        # self.udev_manager removed
        self.status_parser = HeadsetStatusParser()
        self.command_encoder = HeadsetCommandEncoder()

        # self.udev_setup_details removed
        self._last_hid_only_connection_logged_status: bool | None = None
        self._last_hid_raw_read_data: list[int] | None = None
        self._last_hid_parsed_status: dict[str, Any] | None = None
        self._last_reported_battery_level: int | None = None
        self._last_reported_chatmix: int | None = None
        self._last_reported_charging_status: bool | None = None
        self._last_raw_battery_status_for_logging: int | None = None

        logger.debug("HeadsetService initialized with injected HIDManager.")
        self._ensure_hid_communicator()

    def _ensure_hid_communicator(self) -> bool:
        if (
            self.hid_communicator
            and self.hid_manager.get_hid_device() # Use getter method
            and self.hid_communicator.hid_device == self.hid_manager.get_hid_device()
        ):
            return True

        logger.debug(
            "_ensure_hid_communicator: Attempting to establish/refresh HID communicator.",
        )
        # Use self.hid_manager instead of self.hid_connection_manager
        if self.hid_manager.ensure_connection():
            active_hid_device = self.hid_manager.get_hid_device()
            if active_hid_device:
                device_info = self.hid_manager.get_selected_device_info()
                if device_info is None:
                    logger.warning(
                        "_ensure_hid_communicator: Got active HID device but no "
                        "selected_device_info. Using placeholders for HIDCommunicator.",
                    )
                    device_info_for_comm = {
                        "path": b"unknown_path_service",
                        "product_string": "unknown_product_service",
                    }
                else:
                    device_info_for_comm = device_info

                if (
                    self.hid_communicator is None or self.hid_communicator.hid_device != active_hid_device
                ):
                    self.hid_communicator = HIDCommunicator(
                        hid_device=active_hid_device,
                        device_info=device_info_for_comm,
                    )
                return True
            logger.error(
                (
                    "_ensure_hid_communicator: Connection manager reported success "
                    "but no device found by get_hid_device()."
                ),
            )
            self.hid_communicator = None
            return False

        logger.warning(
            "_ensure_hid_communicator: Failed to ensure HID connection via manager.",
        )
        self.hid_communicator = None

        # Removed udev check block
        return False

    def close(self) -> None:
        """Closes the HID connection and clears the communicator."""
        self.hid_manager.close() # Use self.hid_manager
        self.hid_communicator = None
        logger.debug(
            "HeadsetService: HID connection closed via manager, local communicator cleared.",
        )

    def _clear_last_hid_status(self, reason: str) -> None:
        if self._last_hid_parsed_status is not None or self._last_hid_raw_read_data is not None:
            logger.info(
                "_get_parsed_status_hid: %s, clearing last known status.", # Corrected method name in log
                reason,
            )
        self._last_hid_raw_read_data = None
        self._last_hid_parsed_status = None

    def _read_raw_hid_status(self) -> bytes | None:
        if not self._ensure_hid_communicator() or not self.hid_communicator:
            self._clear_last_hid_status("HID communicator not available")
            return None

        command_payload = app_config.HID_CMD_GET_STATUS
        if not self.hid_communicator.write_report(report_id=0, data=command_payload):
            logger.warning(
                "_read_raw_hid_status: Failed to write HID status request. Closing connection.",
            )
            self.hid_manager.close() # Use self.hid_manager
            self.hid_communicator = None
            self._clear_last_hid_status("Write failed")
            return None

        response_data_bytes = self.hid_communicator.read_report(
            app_config.HID_INPUT_REPORT_LENGTH_STATUS,
        )
        if not response_data_bytes:
            self._clear_last_hid_status("Read failed or no data")
            return None

        current_raw_data_list = list(response_data_bytes)
        if current_raw_data_list != self._last_hid_raw_read_data:
            logger.debug(
                "HID read data (raw bytes via communicator): %s",
                response_data_bytes.hex(),
            )
            self._last_hid_raw_read_data = current_raw_data_list
        return response_data_bytes

    def _log_headset_state_changes(self, parsed_status: dict[str, Any]) -> None:
        raw_battery_status_byte = parsed_status.get("raw_battery_status_byte")
        if raw_battery_status_byte is None:
            return

        is_online = parsed_status.get("headset_online", False)
        prev_log_status_byte = self._last_raw_battery_status_for_logging

        if is_online:
            is_charging = parsed_status.get("battery_charging", False)
            current_log_status_byte = 0x01 if is_charging else 0x02

            if prev_log_status_byte is None or prev_log_status_byte == 0x00:
                logger.info(
                    "Headset status change: Now %s (status byte %#02x), was previously offline or unknown.",
                    "charging" if is_charging else "online",
                    raw_battery_status_byte,
                )
            elif is_charging and prev_log_status_byte != 0x01:
                logger.info(
                    "Headset status change: Now charging (status byte %#02x), was previously online and not charging.",
                    raw_battery_status_byte,
                )
            elif not is_charging and prev_log_status_byte == 0x01:
                logger.info(
                    "Headset status change: Now online and not charging (status byte %#02x), was previously charging.",
                    raw_battery_status_byte,
                )
            self._last_raw_battery_status_for_logging = current_log_status_byte
        else:
            if prev_log_status_byte is not None and prev_log_status_byte != 0x00:
                logger.info(
                    "Headset status change: Now offline (status byte %#02x), was previously online/charging.",
                    raw_battery_status_byte,
                )
            self._last_raw_battery_status_for_logging = 0x00

    def _get_parsed_status_hid(self) -> dict[str, Any] | None:
        response_data_bytes = self._read_raw_hid_status()
        if not response_data_bytes:
            return None

        parsed_status = self.status_parser.parse_status_report(response_data_bytes)
        if not parsed_status:
            self._clear_last_hid_status("Parsing failed")
            return None

        self._log_headset_state_changes(parsed_status)

        if parsed_status != self._last_hid_parsed_status:
            logger.debug("Parsed HID status (via parser): %s", parsed_status)
            self._last_hid_parsed_status = parsed_status.copy()
        return parsed_status

    def is_device_connected(self) -> bool:
        self._ensure_hid_communicator()
        if not self.hid_communicator:
            if self._last_hid_only_connection_logged_status is not False:
                logger.warning(
                    "is_device_connected: HID communicator not available. Reporting as NOT connected.",
                )
                self._last_hid_only_connection_logged_status = False
            return False

        status = self._get_parsed_status_hid()
        is_functionally_online = status is not None and status.get("headset_online", False)

        if is_functionally_online != self._last_hid_only_connection_logged_status:
            if is_functionally_online:
                logger.info("is_device_connected: HID connection is active and headset reports as online.")
            else:
                logger.info(
                    "is_device_connected: HID path may be active, but headset reported as offline or status query failed. Reporting as NOT connected.",
                )
            self._last_hid_only_connection_logged_status = is_functionally_online
        return is_functionally_online

    def get_battery_level(self) -> int | None:
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("battery_percent") is not None:
            current_value = status["battery_percent"]
            if current_value != self._last_reported_battery_level:
                logger.debug("Battery level from parsed status: %s%%", current_value)
                self._last_reported_battery_level = current_value
            return current_value
        if self._last_reported_battery_level is not None:
            logger.info("get_battery_level: Could not retrieve valid battery level, clearing last known value.")
        self._last_reported_battery_level = None
        return None

    def get_chatmix_value(self) -> int | None:
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("chatmix") is not None:
            current_value = status["chatmix"]
            if current_value != self._last_reported_chatmix:
                logger.debug("ChatMix value from parsed status: %s", current_value)
                self._last_reported_chatmix = current_value
            return current_value
        if self._last_reported_chatmix is not None:
            logger.info("get_chatmix_value: Could not retrieve valid chatmix value, clearing last known value.")
        self._last_reported_chatmix = None
        return None

    def is_charging(self) -> bool | None:
        status = self._get_parsed_status_hid()
        if status and status.get("headset_online") and status.get("battery_charging") is not None:
            current_value = status["battery_charging"]
            if current_value != self._last_reported_charging_status:
                logger.debug("Charging status from parsed status: %s", current_value)
                self._last_reported_charging_status = current_value
            return current_value
        if self._last_reported_charging_status is not None:
            logger.info("is_charging: Could not retrieve valid charging status, clearing last known value.")
        self._last_reported_charging_status = None
        return None

    def _generic_set_command(
        self,
        command_name_log: str,
        encoded_payload: list[int] | None,
        report_id: int = 0,
    ) -> bool:
        if not self._ensure_hid_communicator() or not self.hid_communicator:
            logger.warning("%s: HID communicator not available. Cannot send command.", command_name_log)
            return False

        if encoded_payload is None:
            logger.error("%s: Encoded payload is None. Command not sent.", command_name_log)
            return False

        success = self.hid_communicator.write_report(report_id=report_id, data=encoded_payload)
        if success:
            logger.info("%s: Successfully sent command.", command_name_log)
        else:
            logger.warning("%s: Failed to send command. Closing HID connection.", command_name_log)
            self.hid_manager.close() # Use self.hid_manager
            self.hid_communicator = None
        return success

    def set_sidetone_level(self, level: int) -> bool:
        clamped_level = max(0, min(128, level))
        payload = self.command_encoder.encode_set_sidetone(clamped_level)
        return self._generic_set_command(f"Set Sidetone (UI level {clamped_level})", payload, report_id=0)

    def set_inactive_timeout(self, minutes: int) -> bool:
        clamped_minutes = max(0, min(90, minutes))
        payload = self.command_encoder.encode_set_inactive_timeout(clamped_minutes)
        return self._generic_set_command(f"Set Inactive Timeout ({clamped_minutes}min)", payload, report_id=0)

    def set_eq_values(self, values: list[float]) -> bool:
        payload = self.command_encoder.encode_set_eq_values(values)
        return self._generic_set_command(f"Set EQ Values ({values})", payload, report_id=0)

    def set_eq_preset_id(self, preset_id: int) -> bool:
        payload = self.command_encoder.encode_set_eq_preset_id(preset_id)
        return self._generic_set_command(f"Set EQ Preset ID ({preset_id})", payload, report_id=0)
