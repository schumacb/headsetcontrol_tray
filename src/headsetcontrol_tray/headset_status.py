"""
Parses status reports from the headset and encodes commands to be sent.

This module contains classes responsible for interpreting raw data from the
headset (like battery level, ChatMix status) and for constructing the raw
byte sequences for commands to be sent to the headset (like setting sidetone
or EQ).
"""

import logging
from typing import Any

from . import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Raw battery level mappings from headset
RAW_BATTERY_LEVEL_0 = 0x00
RAW_BATTERY_LEVEL_25 = 0x01
RAW_BATTERY_LEVEL_50 = 0x02
RAW_BATTERY_LEVEL_75 = 0x03
RAW_BATTERY_LEVEL_100 = 0x04

# Sidetone hardware values
SIDETONE_HW_VALUE_OFF = 0x00
SIDETONE_HW_VALUE_LOW = 0x01
SIDETONE_HW_VALUE_MEDIUM = 0x02
SIDETONE_HW_VALUE_HIGH = 0x03

# Sidetone UI level thresholds for mapping to hardware values
# These are exclusive upper bounds for the UI level (0-128)
SIDETONE_UI_THRESHOLD_MAP_TO_OFF = 26
SIDETONE_UI_THRESHOLD_MAP_TO_LOW = 51
SIDETONE_UI_THRESHOLD_MAP_TO_MEDIUM = 76

# Equalizer settings
NUM_EQ_BANDS = 10  # Number of equalizer bands
EQ_HW_VALUE_MIN = 0x0A  # Hardware value for -10dB
EQ_HW_VALUE_FLAT = 0x14  # Hardware value for 0dB
EQ_HW_VALUE_MAX = 0x1E  # Hardware value for +10dB
EQ_PAYLOAD_TERMINATOR_OR_SLOT_ID = 0x00  # Terminator or custom slot ID for EQ payload


class HeadsetStatusParser:
    """Parses status reports received from the headset device."""

    def __init__(self) -> None:
        """Initializes the HeadsetStatusParser."""
        # This class is stateless, so init might not be strictly needed
        # but can be kept for consistency or future stateful parsing logic.
        logger.debug("HeadsetStatusParser initialized.")

    def _determine_headset_online_status(self, response_data: bytes) -> bool:
        # (Copy from HeadsetService._determine_headset_online_status)
        if len(response_data) <= app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE:
            logger.warning(
                (
                    "_determine_headset_online_status: Response data too short. "
                    "Expected > %s bytes, got %s"
                ),
                app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE,
                len(response_data),
            )
            return False  # Or raise error
        raw_battery_status = response_data[
            app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE
        ]
        return raw_battery_status != 0x00

    def _parse_battery_info(
        self,
        response_data: bytes,
        *,
        is_online: bool,
    ) -> dict[str, Any]:
        # (Copy from HeadsetService._parse_battery_info)
        if not is_online:
            return {"battery_percent": None, "battery_charging": None}

        required_length = max(
            app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE,
            app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE,
        )
        if len(response_data) <= required_length:
            logger.warning(
                (
                    "_parse_battery_info: Response data too short for battery info. "
                    "Expected > %s bytes, got %s"
                ),
                required_length,
                len(response_data),
            )
            return {"battery_percent": None, "battery_charging": None}  # Or raise

        battery_percent: int | None = None
        raw_battery_level = response_data[app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE]
        if raw_battery_level == RAW_BATTERY_LEVEL_0:
            battery_percent = 0
        elif raw_battery_level == RAW_BATTERY_LEVEL_25:
            battery_percent = 25
        elif raw_battery_level == RAW_BATTERY_LEVEL_50:
            battery_percent = 50
        elif raw_battery_level == RAW_BATTERY_LEVEL_75:
            battery_percent = 75
        elif raw_battery_level == RAW_BATTERY_LEVEL_100:
            battery_percent = 100
        else:
            logger.warning(
                "_parse_battery_info: Unknown raw battery level: %#02x",
                raw_battery_level,
            )
            battery_percent = None

        raw_battery_status_byte = response_data[
            app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE
        ]
        battery_charging = (
            raw_battery_status_byte == 0x01
        )  # 0x01 = charging, 0x02 = online, 0x00 = offline

        return {
            "battery_percent": battery_percent,
            "battery_charging": battery_charging,
        }

    def _parse_chatmix_info(
        self,
        response_data: bytes,
        *,
        is_online: bool,
    ) -> int | None:
        # (Copy from HeadsetService._parse_chatmix_info)
        if not is_online:
            return None

        required_length = max(
            app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE,
            app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE,
        )
        if len(response_data) <= required_length:
            logger.warning(
                (
                    "_parse_chatmix_info: Response data too short for chatmix info. "
                    "Expected > %s bytes, got %s"
                ),
                required_length,
                len(response_data),
            )
            return None  # Or raise

        raw_game = response_data[app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE]
        raw_chat = response_data[app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE]

        # Values are 0-100 from headset, map to 0-64 for internal representation
        # Game: 0 (full chat) to 100 (full game) -> maps to 0 to 64
        # Chat: 0 (full game) to 100 (full chat) -> maps to 0 to -64 (effectively)
        # The logic from headsetcontrol seems to be:
        # Let's use the interpretation from the original HeadsetControl GUI
        # if possible or simplify.
        # The prompt's logic:
        raw_game_clamped = max(0, min(100, raw_game))
        raw_chat_clamped = max(0, min(100, raw_chat))

        # This mapping seems specific. If raw_game=100, mapped_game=64. If raw_chat=100,
        # mapped_chat=-64.
        # If game=100, chat=0 => chatmix_value = 64 - (0 + 64) = 0 (Full Game)
        # If game=0, chat=100 => chatmix_value = 64 - (-64 + 0) = 128 (Full Chat)
        # If game=50, chat=50 => chatmix_value = 64 - (-32 + 32) = 64 (Center)
        # This matches the 0-128 UI scale where 0=Game, 64=Center, 128=Chat.
        mapped_game = int((raw_game_clamped / 100.0) * 64.0)
        # Negative to pull "left"
        mapped_chat = int((raw_chat_clamped / 100.0) * -64.0)
        chatmix_value = 64 - (mapped_chat + mapped_game)  # Center point is 64.
        # If mapped_chat is negative, it adds to 64.
        # If mapped_game is positive, it subtracts from 64.

        return max(0, min(128, chatmix_value))

    def parse_status_report(self, response_data: bytes) -> dict[str, Any] | None:
        """Parses the raw HID status report data from the headset."""
        # (Adapt logic from HeadsetService._get_parsed_status_hid that handles parsing)
        if (
            not response_data
            or len(response_data) < app_config.HID_INPUT_REPORT_LENGTH_STATUS
        ):
            logger.warning(
                (
                    "parse_status_report: Insufficient data. Expected at least %s bytes, "
                    "got %s."
                ),
                app_config.HID_INPUT_REPORT_LENGTH_STATUS,
                len(response_data) if response_data else 0,
            )
            return None

        headset_online = self._determine_headset_online_status(response_data)
        battery_info = self._parse_battery_info(response_data, is_online=headset_online)
        chatmix_value = self._parse_chatmix_info(
            response_data,
            is_online=headset_online,
        )

        raw_battery_status_byte = response_data[
            app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE
        ]

        parsed_status = {
            "headset_online": headset_online,
            **battery_info,  # battery_percent, battery_charging
            "chatmix": chatmix_value,
            # For logging state changes in HeadsetService
            "raw_battery_status_byte": raw_battery_status_byte,
        }
        logger.debug("Parsed HID status report: %s", parsed_status)
        return parsed_status


class HeadsetCommandEncoder:
    """Encodes commands into byte sequences to be sent to the headset device."""

    def __init__(self) -> None:
        """Initializes the HeadsetCommandEncoder."""
        # This class is also stateless for now.
        logger.debug("HeadsetCommandEncoder initialized.")

    def encode_set_sidetone(self, level: int) -> list[int]:
        """Encodes the command to set the sidetone level."""
        # (Adapt from HeadsetService._set_sidetone_level_hid)
        # Level is 0-128 UI scale (representing Off, Low, Medium, High)
        # These typically map to 0x00, 0x01, 0x02, 0x03
        mapped_value = SIDETONE_HW_VALUE_HIGH  # Default to High
        if level < SIDETONE_UI_THRESHOLD_MAP_TO_OFF:
            mapped_value = SIDETONE_HW_VALUE_OFF
        elif level < SIDETONE_UI_THRESHOLD_MAP_TO_LOW:
            mapped_value = SIDETONE_HW_VALUE_LOW
        elif level < SIDETONE_UI_THRESHOLD_MAP_TO_MEDIUM:
            mapped_value = SIDETONE_HW_VALUE_MEDIUM
        # else: remains SIDETONE_HW_VALUE_HIGH

        command_payload = list(app_config.HID_CMD_SET_SIDETONE_PREFIX)
        command_payload.append(mapped_value)
        logger.debug(
            "Encoded set_sidetone: UI level %s -> HW value %#02x, payload %s",
            level,
            mapped_value,
            command_payload,
        )
        return command_payload

    def encode_set_inactive_timeout(self, minutes: int) -> list[int]:
        """Encodes the command to set the inactive timeout."""
        # (Adapt from HeadsetService._set_inactive_timeout_hid)
        # minutes is 0-90
        clamped_minutes = max(0, min(90, minutes))  # Hardware supports 0-90 minutes
        command_payload = list(app_config.HID_CMD_SET_INACTIVE_TIME_PREFIX)
        command_payload.append(clamped_minutes)
        logger.debug(
            "Encoded set_inactive_timeout: minutes %s (clamped: %s) -> payload %s",
            minutes,
            clamped_minutes,
            command_payload,
        )
        return command_payload

    def encode_set_eq_values(self, float_values: list[float]) -> list[int] | None:
        """Encodes the command to set custom equalizer values."""
        # (Adapt from HeadsetService._set_eq_values_hid)
        if len(float_values) != NUM_EQ_BANDS:
            logger.error(
                "encode_set_eq_values: Invalid number of EQ bands. Expected %s, got %s.",
                NUM_EQ_BANDS,
                len(float_values),
            )
            return None

        command_payload = list(app_config.HID_CMD_SET_EQ_BANDS_PREFIX)
        for val in float_values:
            clamped_val = max(-10.0, min(10.0, val))  # UI values are -10 to 10 dB
            # Hardware values are EQ_HW_VALUE_MIN (-10dB) to EQ_HW_VALUE_MAX (+10dB),
            # centered at EQ_HW_VALUE_FLAT (0dB).
            byte_value = int(EQ_HW_VALUE_FLAT + clamped_val)
            byte_value = max(EQ_HW_VALUE_MIN, min(EQ_HW_VALUE_MAX, byte_value))
            # Clamp to hardware limits
            command_payload.append(byte_value)

        # Original code appends a 0x00 if length is (prefix_len + num_bands).
        # This 0x00 is likely an identifier for "custom EQ slot" or similar.
        if len(command_payload) == (
            len(app_config.HID_CMD_SET_EQ_BANDS_PREFIX) + NUM_EQ_BANDS
        ):
            command_payload.append(EQ_PAYLOAD_TERMINATOR_OR_SLOT_ID)
        else:
            logger.error(
                (
                    "encode_set_eq_values: Error constructing EQ payload. Length before "
                    "terminator: %s. Expected %s."
                ),
                len(command_payload),
                len(app_config.HID_CMD_SET_EQ_BANDS_PREFIX) + NUM_EQ_BANDS,
            )
            return None

        logger.debug(
            "Encoded set_eq_values: values %s -> payload %s",
            float_values,
            [f"{x:#02x}" for x in command_payload],
        )
        return command_payload

    def encode_set_eq_preset_id(self, preset_id: int) -> list[int] | None:
        """Encodes the command to set a hardware equalizer preset by its ID."""
        # (Adapt from HeadsetService._set_eq_preset_hid)
        if preset_id not in app_config.ARCTIS_NOVA_7_HW_PRESETS:
            logger.error(
                (
                    "encode_set_eq_preset_id: Invalid preset ID: %s. "
                    "Not in ARCTIS_NOVA_7_HW_PRESETS."
                ),
                preset_id,
            )
            return None

        preset_data = app_config.ARCTIS_NOVA_7_HW_PRESETS[preset_id]
        float_values_obj = preset_data.get("values")

        if not isinstance(float_values_obj, list) or not all(
            isinstance(v, float | int) for v in float_values_obj
        ):
            logger.error(
                (
                    "encode_set_eq_preset_id: Preset data 'values' for ID %s "
                    "is not a list of numbers."
                ),
                preset_id,
            )
            return None

        float_values: list[float] = [float(v) for v in float_values_obj]

        if len(float_values) != NUM_EQ_BANDS:
            logger.error(
                (
                    "encode_set_eq_preset_id: Malformed preset data for ID %s. "
                    "Expected %s bands, got %s."
                ),
                preset_id,
                NUM_EQ_BANDS,  # Added missing argument
                len(float_values),
            )
            return None

        logger.info(
            (
                "encode_set_eq_preset_id: Encoding hardware preset '%s' (ID: %s) "
                "using its bands: %s"
            ),
            preset_data.get("name", "Unknown"),
            preset_id,
            float_values,
        )

        # As per prompt: selecting a preset effectively sends its values as a
        # "custom" EQ setting. This means it uses the same encode_set_eq_values
        # method, which appends 0x00. If hardware presets require a different
        # slot ID (e.g., 0x01-0x04), then encode_set_eq_values would need
        # modification to accept a slot_id parameter.
        # For now, maintaining consistency with the original described behavior.
        return self.encode_set_eq_values(float_values)
