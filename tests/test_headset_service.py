"""Unit tests for the HeadsetService class.

This module contains tests for various functionalities of HeadsetService,
including device connection, status retrieval (battery, chatmix, charging),
and sending commands (sidetone, EQ, timeout). It uses unittest.mock
extensively to isolate HeadsetService from actual HID hardware and dependencies.
"""
# Ensure src is in path for imports
# This path manipulation might not be ideal for all test runners.
# Consider pytest path features or project structure if issues arise.
from pathlib import Path  # Path is used here for sys.path modification
import sys
import unittest
from unittest.mock import MagicMock, patch

import hid  # Keep for type hinting if hid.Device is used

sys.path.insert(0, str((Path(__file__).parent / ".." / "src").resolve()))

from headsetcontrol_tray import app_config
from headsetcontrol_tray.headset_service import HeadsetService
from headsetcontrol_tray.os_layer.base import HIDManagerInterface  # Added

EXPECTED_BATTERY_LEVEL_HIGH = 75
EXPECTED_CHATMIX_VALUE_MID = 32


class BaseHeadsetServiceTestCase(unittest.TestCase):
    """Base test case for HeadsetService, setting up common mocks."""

    def setUp(self) -> None:
        """Set up common mocks and the HeadsetService instance for each test."""
        # Create a mock for HIDManagerInterface
        self.mock_hid_manager_instance = MagicMock(spec=HIDManagerInterface)

        # Patch HIDCommunicator class
        self.hid_communicator_patcher = patch("headsetcontrol_tray.headset_service.HIDCommunicator")
        self.MockHIDCommunicatorClass = self.hid_communicator_patcher.start()
        self.mock_hid_communicator_instance = self.MockHIDCommunicatorClass.return_value
        self.addCleanup(self.hid_communicator_patcher.stop)

        # Patch HeadsetStatusParser class
        self.status_parser_patcher = patch("headsetcontrol_tray.headset_service.HeadsetStatusParser")
        mock_status_parser_class = self.status_parser_patcher.start()
        self.mock_status_parser_instance = mock_status_parser_class.return_value
        self.addCleanup(self.status_parser_patcher.stop)

        # Patch HeadsetCommandEncoder class
        self.command_encoder_patcher = patch("headsetcontrol_tray.headset_service.HeadsetCommandEncoder")
        mock_command_encoder_class = self.command_encoder_patcher.start()
        self.mock_command_encoder_instance = mock_command_encoder_class.return_value
        self.addCleanup(self.command_encoder_patcher.stop)

        # Patch logger
        self.logger_patcher = patch("headsetcontrol_tray.headset_service.logger")
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        # Default mock behaviors
        self.mock_hid_device_instance = MagicMock(spec=hid.Device)
        self.mock_hid_device_instance.path = b"/dev/hidraw_mock"  # hid.Device path is bytes

        self.mock_hid_manager_instance.ensure_connection.return_value = True
        self.mock_hid_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance
        # Ensure selected_device_info is also mocked if HIDCommunicator relies on it
        self.mock_hid_manager_instance.get_selected_device_info.return_value = {
            "path": b"/dev/hidraw_mock",
            "product_string": "Mocked Headset",
        }

        self.MockHIDCommunicatorClass.return_value = self.mock_hid_communicator_instance

        # Instantiate HeadsetService with the mocked HIDManagerInterface
        self.service = HeadsetService(hid_manager=self.mock_hid_manager_instance)

        self.reset_common_mocks()

    def reset_common_mocks(self) -> None:
        """Reset common mocks to their default states for a clean test setup."""
        self.mock_hid_manager_instance.reset_mock()
        self.mock_hid_manager_instance.ensure_connection.return_value = True
        self.mock_hid_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance
        self.mock_hid_manager_instance.get_selected_device_info.return_value = {
            "path": b"/dev/hidraw_mock",
            "product_string": "Mocked Headset",
        }

        self.MockHIDCommunicatorClass.reset_mock()
        self.MockHIDCommunicatorClass.return_value = self.mock_hid_communicator_instance
        self.mock_hid_communicator_instance.reset_mock()

        self.mock_status_parser_instance.reset_mock()
        self.mock_command_encoder_instance.reset_mock()
        self.mock_logger.reset_mock()


# TestHeadsetServiceUdevInteraction class is REMOVED


class TestHeadsetServiceConnectionAndStatus(BaseHeadsetServiceTestCase):
    """Tests for HeadsetService connection logic and status retrieval methods."""

    def test_is_device_connected_success(self) -> None:
        """Test is_device_connected() when connection and status parsing are successful."""
        self.mock_hid_manager_instance.ensure_connection.return_value = True
        self.mock_hid_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance
        self.mock_hid_communicator_instance.write_report.return_value = True
        status_report_bytes = b"\x00" * app_config.HID_INPUT_REPORT_LENGTH_STATUS
        self.mock_hid_communicator_instance.read_report.return_value = status_report_bytes
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": 50,
        }

        assert self.service.is_device_connected()
        self.mock_hid_manager_instance.ensure_connection.assert_called()
        self.mock_status_parser_instance.parse_status_report.assert_called_with(status_report_bytes)

    def test_is_device_connected_manager_fails_connection(self) -> None:
        """Test is_device_connected() when the HID manager fails to ensure a connection."""
        self.reset_common_mocks()
        self.mock_hid_manager_instance.ensure_connection.return_value = False
        self.mock_hid_manager_instance.get_hid_device.return_value = None

        # Re-initialize service for a clean test of this specific scenario
        # No need to patch HIDCommunicator here as it's already patched at class level by Base
        service = HeadsetService(hid_manager=self.mock_hid_manager_instance)
        assert not service.is_device_connected()

        self.mock_hid_manager_instance.ensure_connection.assert_called()
        self.mock_hid_communicator_instance.write_report.assert_not_called()

    def test_is_device_connected_parser_returns_offline(self) -> None:
        """Test is_device_connected() when the status parser indicates the headset is offline."""
        self.mock_status_parser_instance.parse_status_report.return_value = {"headset_online": False}
        assert not self.service.is_device_connected()

    def test_get_battery_level_success(self) -> None:
        """Test get_battery_level() when status is available and headset is online."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": EXPECTED_BATTERY_LEVEL_HIGH,
            "battery_charging": False,
            "chatmix": 64,
            "raw_battery_status_byte": 0x02,
        }
        assert self.service.get_battery_level() == EXPECTED_BATTERY_LEVEL_HIGH

    def test_get_battery_level_offline(self) -> None:
        """Test get_battery_level() when the headset reports as offline."""
        self.mock_status_parser_instance.parse_status_report.return_value = {"headset_online": False}
        assert self.service.get_battery_level() is None

    def test_get_battery_level_parse_fail(self) -> None:
        """Test get_battery_level() when status parsing fails."""
        self.mock_status_parser_instance.parse_status_report.return_value = None
        assert self.service.get_battery_level() is None

    def test_get_chatmix_value_success(self) -> None:
        """Test get_chatmix_value() when status is available and headset is online."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": EXPECTED_BATTERY_LEVEL_HIGH,
            "battery_charging": False,
            "chatmix": EXPECTED_CHATMIX_VALUE_MID,
            "raw_battery_status_byte": 0x02,
        }
        assert self.service.get_chatmix_value() == EXPECTED_CHATMIX_VALUE_MID

    def test_is_charging_success(self) -> None:
        """Test is_charging() when status is available and headset reports charging."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": 75,
            "battery_charging": True,
            "chatmix": 64,
            "raw_battery_status_byte": 0x01,
        }
        assert self.service.is_charging()

    def test_write_failure_in_get_status_closes_connection(self) -> None:
        """Test that a HID write failure during status retrieval closes the connection."""
        self.reset_common_mocks()
        self.mock_hid_communicator_instance.write_report.return_value = False

        self.service._get_parsed_status_hid()  # noqa: SLF001 # Testing internal method behavior

        self.mock_hid_manager_instance.close.assert_called_once()
        assert self.service.hid_communicator is None

    def test_read_failure_in_get_status(self) -> None:
        """Test handling of a HID read failure during status retrieval."""
        self.reset_common_mocks()
        self.mock_hid_communicator_instance.write_report.return_value = True
        self.mock_hid_communicator_instance.read_report.return_value = None

        result = self.service._get_parsed_status_hid()  # noqa: SLF001 # Testing internal method behavior

        assert result is None
        assert self.service._last_hid_raw_read_data is None  # noqa: SLF001 # Verifying internal state
        assert self.service._last_hid_parsed_status is None  # noqa: SLF001 # Verifying internal state


class TestHeadsetServiceCommands(BaseHeadsetServiceTestCase):
    """Tests for HeadsetService methods that send commands to the headset."""

    def test_set_sidetone_level_success(self) -> None:
        """Test successful setting of the sidetone level."""
        encoded_payload = [0x01, 0x02]
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = encoded_payload
        self.mock_hid_communicator_instance.write_report.return_value = True

        result = self.service.set_sidetone_level(50)

        assert result
        self.mock_command_encoder_instance.encode_set_sidetone.assert_called_once_with(50)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=encoded_payload)

    def test_set_sidetone_level_encoder_returns_none(self) -> None:
        """Test set_sidetone_level() when the command encoder returns None."""
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = None
        result = self.service.set_sidetone_level(50)
        assert not result
        self.mock_hid_communicator_instance.write_report.assert_not_called()

    def test_set_sidetone_level_write_fail(self) -> None:
        """Test set_sidetone_level() when HID write_report fails."""
        encoded_payload = [0x01, 0x02]
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = encoded_payload
        self.mock_hid_communicator_instance.write_report.return_value = False

        result = self.service.set_sidetone_level(50)

        assert not result
        self.mock_hid_manager_instance.close.assert_called_once()
        assert self.service.hid_communicator is None

    def test_set_inactive_timeout_success(self) -> None:
        """Test successful setting of the inactive timeout."""
        payload = [0x0A, 30]
        self.mock_command_encoder_instance.encode_set_inactive_timeout.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        assert self.service.set_inactive_timeout(30)
        self.mock_command_encoder_instance.encode_set_inactive_timeout.assert_called_once_with(30)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=payload)

    def test_set_eq_values_success(self) -> None:
        """Test successful setting of EQ values."""
        values = [1.0] * 10
        payload = [0x0B] + ([0x15] * 10) + [0x00]
        self.mock_command_encoder_instance.encode_set_eq_values.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        assert self.service.set_eq_values(values)
        self.mock_command_encoder_instance.encode_set_eq_values.assert_called_once_with(values)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=payload)

    def test_set_eq_preset_id_success(self) -> None:
        """Test successful setting of an EQ preset ID."""
        preset_id = 1
        payload = [0x0C] + ([0x10] * 10) + [0x00]  # Example payload
        self.mock_command_encoder_instance.encode_set_eq_preset_id.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        assert self.service.set_eq_preset_id(preset_id)
        self.mock_command_encoder_instance.encode_set_eq_preset_id.assert_called_once_with(preset_id)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=payload)

    def test_close_method(self) -> None:
        """Test that the close method calls the HID manager's close method."""
        self.service.close()
        self.mock_hid_manager_instance.close.assert_called_once()
        assert self.service.hid_communicator is None


if __name__ == "__main__":
    unittest.main()
