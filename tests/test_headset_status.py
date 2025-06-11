"""Tests for HeadsetStatusParser and HeadsetCommandEncoder."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is in path for imports
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")),
)

from headsetcontrol_tray import app_config
from headsetcontrol_tray.headset_status import (
    NUM_EQ_BANDS,  # Added import
    HeadsetCommandEncoder,
    HeadsetStatusParser,
)


# Helper to create mock response data for HeadsetStatusParser
def create_status_response_data(
    status_byte_val: int,
    level_byte_val: int = 0x00,
    game_byte_val: int = 0,  # Raw value 0-100
    chat_byte_val: int = 0,  # Raw value 0-100
) -> bytes:
    """Helper function to create mock status response data for tests."""
    data = bytearray(
        [0] * app_config.HID_INPUT_REPORT_LENGTH_STATUS,
    )  # Use bytearray for mutability

    # Ensure indices are within bounds before assignment
    if len(data) > app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE:
        data[app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE] = status_byte_val
    else:
        raise IndexError(
            f"HID_RES_STATUS_BATTERY_STATUS_BYTE index {app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE} out of bounds for data length {len(data)}",
        )

    if len(data) > app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE:
        data[app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE] = level_byte_val
    else:
        raise IndexError(
            f"HID_RES_STATUS_BATTERY_LEVEL_BYTE index {app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE} out of bounds for data length {len(data)}",
        )

    if len(data) > app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE:
        data[app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE] = game_byte_val
    else:
        raise IndexError(
            f"HID_RES_STATUS_CHATMIX_GAME_BYTE index {app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE} out of bounds for data length {len(data)}",
        )

    if len(data) > app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE:
        data[app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE] = chat_byte_val
    else:
        raise IndexError(
            f"HID_RES_STATUS_CHATMIX_CHAT_BYTE index {app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE} out of bounds for data length {len(data)}",
        )

    return bytes(data)


class TestHeadsetStatusParser(unittest.TestCase):  # Removed class decorator
    """Tests for the HeadsetStatusParser class."""
    def setUp(self) -> None:  # Signature changed
        """Set up test environment for HeadsetStatusParser tests."""
        self.logger_patcher = patch(
            f"{HeadsetStatusParser.__module__}.logger",
            new_callable=MagicMock,
        )
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        self.parser = HeadsetStatusParser()
        # self.mock_logger is now available

    def test_parse_status_report_online_charging_full_battery_mid_chatmix(
        self,
    ) -> None:  # Removed mock_logger arg
        """Test parsing a status report for online, charging, full battery, and mid chatmix."""
        # Status: 0x01 (Charging), Level: 0x04 (100%), Game: 50, Chat: 50 (Balanced -> UI 64)
        response_data = create_status_response_data(
            status_byte_val=0x01,
            level_byte_val=0x04,
            game_byte_val=50,
            chat_byte_val=50,
        )

        expected_status = {
            "headset_online": True,
            "battery_percent": 100,
            "battery_charging": True,
            "chatmix": 64,  # (50,50) maps to 64
            "raw_battery_status_byte": 0x01,
        }
        parsed = self.parser.parse_status_report(response_data)
        self.assertEqual(parsed, expected_status)

    def test_parse_status_report_offline(self) -> None:  # Removed mock_logger arg
        """Test parsing a status report when the headset is offline."""
        # Status: 0x00 (Offline)
        response_data = create_status_response_data(
            status_byte_val=0x00,
            level_byte_val=0x02,
            game_byte_val=50,
            chat_byte_val=50,
        )

        expected_status = {
            "headset_online": False,
            "battery_percent": None,  # Offline, so no battery info
            "battery_charging": None,  # Offline, so no charging info
            "chatmix": None,  # Offline, so no chatmix info
            "raw_battery_status_byte": 0x00,
        }
        parsed = self.parser.parse_status_report(response_data)
        self.assertEqual(parsed, expected_status)

    def test_parse_status_report_various_battery_levels(
        self,
    ) -> None:  # Removed mock_logger arg
        """Test parsing status reports with various battery levels."""
        # status_byte_val=0x02 (Online, not charging)
        levels_map = {0x00: 0, 0x01: 25, 0x02: 50, 0x03: 75, 0x04: 100}
        for level_byte, expected_percent in levels_map.items():
            with self.subTest(level_byte=level_byte):
                response_data = create_status_response_data(
                    status_byte_val=0x02,
                    level_byte_val=level_byte,
                )
                parsed = self.parser.parse_status_report(response_data)
                self.assertIsNotNone(parsed)
                if parsed:  # For Mypy, though assertIsNotNone should guarantee
                    self.assertEqual(parsed["battery_percent"], expected_percent)
                    self.assertFalse(parsed["battery_charging"])  # Status 0x02
                    self.assertTrue(parsed["headset_online"])

    def test_parse_status_report_unknown_battery_level(self) -> None:  # Removed mock_logger arg
        """Test parsing a status report with an unknown battery level byte."""
        response_data = create_status_response_data(
            status_byte_val=0x02,
            level_byte_val=0x05,
        )  # Unknown level
        parsed = self.parser.parse_status_report(response_data)
        self.assertIsNotNone(parsed)
        if parsed:  # For Mypy
            self.assertIsNone(parsed["battery_percent"])
        self.mock_logger.warning.assert_any_call(
            "_parse_battery_info: Unknown raw battery level: %#02x",
            5,
        )

    def test_parse_status_report_various_chatmix_values(
        self,
    ) -> None:  # Removed mock_logger arg
        """Test parsing status reports with various chatmix values."""
        # status_byte_val=0x02 (Online, not charging), level_byte_val=0x02 (50%)
        chatmix_tests = [
            # (game_raw, chat_raw, expected_ui_value)
            (100, 0, 0),
            (0, 100, 128),
            (50, 50, 64),
            (0, 0, 64),
            (75, 25, 32),
            (25, 75, 96),
        ]
        for game, chat, expected_mix in chatmix_tests:
            with self.subTest(game=game, chat=chat):
                response_data = create_status_response_data(
                    status_byte_val=0x02,
                    level_byte_val=0x02,
                    game_byte_val=game,
                    chat_byte_val=chat,
                )
                parsed = self.parser.parse_status_report(response_data)
                self.assertIsNotNone(parsed)
                if parsed:  # For Mypy
                    self.assertEqual(parsed["chatmix"], expected_mix)

    def test_parse_status_report_insufficient_data(self) -> None:  # Removed mock_logger arg
        """Test parsing a status report with insufficient data."""
        short_data = b"\x00\x01"  # Too short for full parsing
        parsed = self.parser.parse_status_report(short_data)
        self.assertIsNone(parsed)
        self.mock_logger.warning.assert_called_with(
            "parse_status_report: Insufficient data. Expected at least %s bytes, got %s.",
            app_config.HID_INPUT_REPORT_LENGTH_STATUS,
            len(short_data),
        )

    def test_determine_headset_online_status_short_data(
        self,
    ) -> None:  # Removed mock_logger arg
        """Test _determine_headset_online_status with short data."""
        # Test the specific helper if data is too short for HID_RES_STATUS_BATTERY_STATUS_BYTE
        short_data = bytes(
            [0] * (app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE),
        )  # Length exactly up to, but not including, the byte
        self.assertFalse(self.parser._determine_headset_online_status(short_data))
        self.mock_logger.warning.assert_called_with(
            "_determine_headset_online_status: Response data too short. Expected > %s bytes, got %s",
            app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE,
            len(short_data),
        )


class TestHeadsetCommandEncoder(unittest.TestCase):  # Removed class decorator
    """Tests for the HeadsetCommandEncoder class."""
    def setUp(self) -> None:  # Signature changed
        """Set up test environment for HeadsetCommandEncoder tests."""
        self.logger_patcher = patch(
            f"{HeadsetCommandEncoder.__module__}.logger",
            new_callable=MagicMock,
        )
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        self.encoder = HeadsetCommandEncoder()
        # self.mock_logger is now available

    def test_encode_set_sidetone(self) -> None:  # Removed mock_logger arg
        """Test encoding of set sidetone command for various UI levels."""
        # (level_ui, expected_hw_byte)
        sidetone_map = {
            0: 0x00,
            25: 0x00,
            26: 0x01,
            50: 0x01,
            51: 0x02,
            75: 0x02,
            76: 0x03,
            128: 0x03,
        }
        for ui_level, hw_byte in sidetone_map.items():
            with self.subTest(ui_level=ui_level):
                expected_payload = list(app_config.HID_CMD_SET_SIDETONE_PREFIX) + [
                    hw_byte,
                ]
                encoded = self.encoder.encode_set_sidetone(ui_level)
                self.assertEqual(encoded, expected_payload)

    def test_encode_set_inactive_timeout(self) -> None:  # Removed mock_logger arg
        """Test encoding of set inactive timeout command for various minute values."""
        # (minutes_in, expected_minutes_byte)
        timeout_map = {0: 0, 30: 30, 90: 90, 100: 90, -10: 0}  # Also test clamping
        for minutes_in, minutes_byte in timeout_map.items():
            with self.subTest(minutes_in=minutes_in):
                expected_payload = list(app_config.HID_CMD_SET_INACTIVE_TIME_PREFIX) + [
                    minutes_byte,
                ]
                encoded = self.encoder.encode_set_inactive_timeout(minutes_in)
                self.assertEqual(encoded, expected_payload)

    def test_encode_set_eq_values_valid(self) -> None:  # Removed mock_logger arg
        """Test encoding of set EQ values command with valid float inputs."""
        # 10 float values from -10.0 to 10.0
        # Hardware: 0x14 (0dB), 0x0A (-10dB), 0x1E (10dB)
        # byte_value = int(0x14 + clamped_val)
        eq_floats = [-10.0, -5.0, 0.0, 5.0, 10.0, -10.0, -5.0, 0.0, 5.0, 10.0]
        expected_hw_bytes = [0x0A, 0x0F, 0x14, 0x19, 0x1E, 0x0A, 0x0F, 0x14, 0x19, 0x1E]
        expected_payload = (
            list(app_config.HID_CMD_SET_EQ_BANDS_PREFIX) + expected_hw_bytes + [0x00]
        )  # Terminator

        encoded = self.encoder.encode_set_eq_values(eq_floats)
        self.assertEqual(encoded, expected_payload)

    def test_encode_set_eq_values_invalid_band_count(self) -> None:  # Removed mock_logger arg
        """Test encode_set_eq_values returns None for invalid band count."""
        eq_floats_short = [0.0] * 9
        encoded = self.encoder.encode_set_eq_values(eq_floats_short)
        self.assertIsNone(encoded)
        self.mock_logger.error.assert_called_with(
            "encode_set_eq_values: Invalid number of EQ bands. Expected %s, got %s.",
            NUM_EQ_BANDS,
            9,
        )

    # For ARCTIS_NOVA_7_HW_PRESETS, we need to ensure it's structured as expected
    # or mock it if its content is complex or external.
    # Assuming app_config.ARCTIS_NOVA_7_HW_PRESETS is available and has a known structure.
    def test_encode_set_eq_preset_id_valid(self) -> None:  # Removed mock_logger arg
        """Test encoding of set EQ preset command with a valid preset ID."""
        # Assume preset ID 0 exists and has 10 float values.
        preset_id_to_test = 0
        if preset_id_to_test not in app_config.ARCTIS_NOVA_7_HW_PRESETS:
            self.skipTest(
                f"Preset ID {preset_id_to_test} not in app_config.ARCTIS_NOVA_7_HW_PRESETS for testing.",
            )

        preset_values = app_config.ARCTIS_NOVA_7_HW_PRESETS[preset_id_to_test]["values"]
        # This test relies on encode_set_eq_values, which is tested separately.
        # So, we just need to ensure encode_set_eq_values is called with the correct preset values.

        # Mock encode_set_eq_values to verify it's called correctly
        with patch.object(
            self.encoder,
            "encode_set_eq_values",
            wraps=self.encoder.encode_set_eq_values,
        ) as mock_encode_eq:
            self.encoder.encode_set_eq_preset_id(preset_id_to_test)
            # preset_values might be seen as List[Any] by mypy depending on app_config typing
            mock_encode_eq.assert_called_once_with([float(v) for v in preset_values])  # type: ignore[arg-type]

    def test_encode_set_eq_preset_id_invalid_id(self) -> None:  # Removed mock_logger arg
        """Test encode_set_eq_preset_id returns None for an invalid preset ID."""
        invalid_id = 99
        encoded = self.encoder.encode_set_eq_preset_id(invalid_id)
        self.assertIsNone(encoded)
        self.mock_logger.error.assert_called_with(
            "encode_set_eq_preset_id: Invalid preset ID: %s. Not in ARCTIS_NOVA_7_HW_PRESETS.",
            invalid_id,
        )

    @patch.dict(
        app_config.ARCTIS_NOVA_7_HW_PRESETS,
        {
            0: {
                "name": "TestPreset",
                "values": [1.0] * 5,
            },  # Malformed: 5 bands instead of 10
        },
    )
    def test_encode_set_eq_preset_id_malformed_preset_data_band_count(
        self,
    ) -> None:  # Removed mock_logger arg
        """Test encode_set_eq_preset_id with malformed preset data (band count)."""
        encoded = self.encoder.encode_set_eq_preset_id(0)
        self.assertIsNone(encoded)
        self.mock_logger.error.assert_any_call(
            "encode_set_eq_preset_id: Malformed preset data for ID %s. Expected %s bands, got %s.",
            0,
            NUM_EQ_BANDS,
            5,
        )

    @patch.dict(
        app_config.ARCTIS_NOVA_7_HW_PRESETS,
        {
            0: {
                "name": "TestPreset",
                "values": "not_a_list",
            },  # Malformed: values not a list
        },
    )
    def test_encode_set_eq_preset_id_malformed_preset_data_values_type(
        self,
    ) -> None:  # Removed mock_logger arg
        """Test encode_set_eq_preset_id with malformed preset data (values type)."""
        encoded = self.encoder.encode_set_eq_preset_id(0)
        self.assertIsNone(encoded)
        self.mock_logger.error.assert_any_call(
            "encode_set_eq_preset_id: Preset data 'values' for ID %s is not a list of numbers.",
            0,
        )


if __name__ == "__main__":
    unittest.main()
