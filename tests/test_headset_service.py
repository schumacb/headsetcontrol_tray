"""Tests for the HeadsetService class."""

import os
from pathlib import Path  # Added
import sys
import unittest
from unittest.mock import MagicMock, patch

import hid  # Keep for type hinting if hid.Device is used

# Ensure src is in path for imports
sys.path.insert(
    0,
    str((Path(__file__).parent / ".." / "src").resolve()), # Replaced with pathlib
)

from headsetcontrol_tray import app_config
from headsetcontrol_tray.headset_service import HeadsetService

# Constants for magic numbers used in test comparisons
EXPECTED_BATTERY_LEVEL_HIGH = 75
EXPECTED_CHATMIX_VALUE_MID = 32


# Common mock setup for HeadsetService dependencies
# No class decorators here now
class BaseHeadsetServiceTestCase(unittest.TestCase):
    """Base class for HeadsetService tests with common mock setup."""

    def setUp(self) -> None:  # Signature changed, no # type: ignore[override] needed
        """Set up common mocks for HeadsetService tests."""
        # Patch 'pathlib.Path' in the context of the headset_service module
        self.mock_path_patcher = patch("headsetcontrol_tray.headset_service.Path")
        mock_path_class = self.mock_path_patcher.start()

        # When Path(...) is called, it returns an instance (mock_path_instance)
        self.mock_path_instance = MagicMock(spec=Path)
        mock_path_class.return_value = self.mock_path_instance

        # When mock_path_instance / STEELSERIES_UDEV_FILENAME is called,
        # it should return another mock (mock_final_path) whose exists() can be controlled.
        self.mock_final_path = MagicMock(spec=Path)
        self.mock_path_instance.__truediv__.return_value = self.mock_final_path

        # Control the .exists() on this mock_final_path
        self.mock_final_path.exists = MagicMock(return_value=True)  # Default to True

        self.addCleanup(self.mock_path_patcher.stop)

        # Patch HIDConnectionManager class
        self.hid_connection_manager_patcher = patch(
            "headsetcontrol_tray.headset_service.HIDConnectionManager",
        )
        mock_hid_connection_manager_class = self.hid_connection_manager_patcher.start()
        self.mock_hid_connection_manager_instance = mock_hid_connection_manager_class.return_value
        self.addCleanup(self.hid_connection_manager_patcher.stop)

        # Patch HIDCommunicator class
        self.hid_communicator_patcher = patch(
            "headsetcontrol_tray.headset_service.HIDCommunicator",
        )
        self.MockHIDCommunicatorClass = self.hid_communicator_patcher.start()  # Keep ref to mock class
        self.mock_hid_communicator_instance = self.MockHIDCommunicatorClass.return_value
        self.addCleanup(self.hid_communicator_patcher.stop)

        # Patch UDEVManager class
        self.udev_manager_patcher = patch(
            "headsetcontrol_tray.headset_service.UDEVManager",
        )
        mock_udev_manager_class = self.udev_manager_patcher.start()
        self.mock_udev_manager_instance = mock_udev_manager_class.return_value
        self.addCleanup(self.udev_manager_patcher.stop)

        # Patch HeadsetStatusParser class
        self.status_parser_patcher = patch(
            "headsetcontrol_tray.headset_service.HeadsetStatusParser",
        )
        mock_status_parser_class = self.status_parser_patcher.start()
        self.mock_status_parser_instance = mock_status_parser_class.return_value
        self.addCleanup(self.status_parser_patcher.stop)

        # Patch HeadsetCommandEncoder class
        self.command_encoder_patcher = patch(
            "headsetcontrol_tray.headset_service.HeadsetCommandEncoder",
        )
        mock_command_encoder_class = self.command_encoder_patcher.start()
        self.mock_command_encoder_instance = mock_command_encoder_class.return_value
        self.addCleanup(self.command_encoder_patcher.stop)

        # Patch logger
        self.logger_patcher = patch("headsetcontrol_tray.headset_service.logger")
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        # --- Original default mock behaviors from user's provided code ---
        self.mock_hid_device_instance = MagicMock(
            spec=hid.Device,
        )  # Mock the hid.Device object
        self.mock_hid_device_instance.path = b"/dev/hidraw_mock"  # Example path

        self.mock_hid_connection_manager_instance.ensure_connection.return_value = True
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance

        # When HeadsetService initializes, it calls _ensure_hid_communicator.
        # This might try to create an HIDCommunicator instance.
        # We ensure that this creation uses the mocked instance.
        self.MockHIDCommunicatorClass.return_value = self.mock_hid_communicator_instance

        self.service = HeadsetService()

        # Reset call counts for mocks that might be called during HeadsetService initialization
        self.reset_common_mocks()

    def reset_common_mocks(self) -> None:
        """Reset common mocks to a default state for a new test scenario."""
        # Reset the .exists() mock on the final path object
        if hasattr(self, "mock_final_path") and hasattr(self.mock_final_path, "exists"):
            self.mock_final_path.exists.reset_mock()
            self.mock_final_path.exists.return_value = True  # Reset to default True

        self.mock_hid_connection_manager_instance.reset_mock()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = True  # Reset to default success
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance

        self.MockHIDCommunicatorClass.reset_mock()
        self.MockHIDCommunicatorClass.return_value = self.mock_hid_communicator_instance  # Re-assign
        self.mock_hid_communicator_instance.reset_mock()

        self.mock_udev_manager_instance.reset_mock()
        self.mock_status_parser_instance.reset_mock()
        self.mock_command_encoder_instance.reset_mock()
        self.mock_logger.reset_mock()


class TestHeadsetServiceUdevInteraction(BaseHeadsetServiceTestCase):
    """Tests UDEV interaction functionalities of HeadsetService."""

    def test_init_connection_fail_udev_rules_missing_triggers_creation(self) -> None:
        """Test __init__ triggers udev creation if connection fails and rules are missing."""
        # Reset mocks called during setUp's HeadsetService() instantiation
        self.reset_common_mocks()

        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None  # No device if connection fails
        self.mock_final_path.exists.return_value = False  # UDEV rules do NOT exist
        self.mock_udev_manager_instance.create_rules_interactive.return_value = (
            True  # Mock successful rule creation guidance
        )

        # Re-initialize service to test __init__ behavior with these conditions
        # Need to ensure the HIDCommunicator isn't re-created with old mocks by default __init__
        with patch(
            "headsetcontrol_tray.headset_service.HIDCommunicator",
        ) as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService()

        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        # Path(...).exists() is called, so check that mock
        self.mock_final_path.exists.assert_called_once()
        # We can also check that Path was constructed with the correct base dir if needed
        # e.g., self.mock_path_instance.parent_of_final_path_mock \
        # .__truediv__.assert_called_with(STEELSERIES_UDEV_FILENAME)
        # For now, just checking .exists() is enough to confirm the flow.

        self.mock_udev_manager_instance.create_rules_interactive.assert_called_once()
        assert service.udev_setup_details is not None

    def test_init_connection_fail_udev_rules_exist_no_creation(self) -> None:
        """Test __init__ does not trigger udev creation if rules exist, even if connection fails."""
        self.reset_common_mocks()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None
        self.mock_final_path.exists.return_value = True  # UDEV rules EXIST

        with patch(
            "headsetcontrol_tray.headset_service.HIDCommunicator",
        ) as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService()

        self.mock_final_path.exists.assert_called_once()
        self.mock_udev_manager_instance.create_rules_interactive.assert_not_called()
        assert service.udev_setup_details is None  # Should be None as interactive creation wasn't called

    def test_get_udev_setup_details_returns_data(self) -> None:
        """Test that udev_setup_details contains expected data after rule creation guidance."""
        self.reset_common_mocks()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None
        self.mock_final_path.exists.return_value = False

        dummy_details = {
            "temp_file_path": "./dummy_temp_file.txt",
            "final_file_path": "/etc/rules",
            "rule_content": "RULE",
        }
        self.mock_udev_manager_instance.create_rules_interactive.return_value = True
        self.mock_udev_manager_instance.get_last_udev_setup_details.return_value = dummy_details

        with patch(
            "headsetcontrol_tray.headset_service.HIDCommunicator",
        ) as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService()  # Trigger the call path

        assert service.udev_setup_details == dummy_details


class TestHeadsetServiceConnectionAndStatus(BaseHeadsetServiceTestCase):
    """Tests connection and status retrieval of HeadsetService."""

    def test_is_device_connected_success(self) -> None:
        """Test is_device_connected returns True when HID communication and parsing succeed."""
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = True
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance
        self.mock_hid_communicator_instance.write_report.return_value = True
        # Make read_report return valid status bytes
        status_report_bytes = b"\x00" * app_config.HID_INPUT_REPORT_LENGTH_STATUS
        self.mock_hid_communicator_instance.read_report.return_value = status_report_bytes
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": 50,
        }

        assert self.service.is_device_connected()
        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        self.mock_status_parser_instance.parse_status_report.assert_called_with(
            status_report_bytes,
        )

    def test_is_device_connected_manager_fails_connection(self) -> None:
        """Test is_device_connected returns False if HID manager fails connection."""
        self.reset_common_mocks()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None
        self.mock_final_path.exists.return_value = (  # Ensure this is also set for the path in _ensure_hid_communicator
            True  # Assume udev rules exist for this test
        )
        # If the service was already initialized in setUp, its _ensure_hid_communicator might have run.
        # We need to re-evaluate its state or re-initialize if we want to test this path cleanly.
        # For simplicity, let's assume the initial _ensure_hid_communicator in setUp() didn't trigger udev logic
        # because ensure_connection() was True by default there.

        # Re-initialize service for a clean test of this specific scenario
        with patch(
            "headsetcontrol_tray.headset_service.HIDCommunicator",
        ) as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService()
            assert not service.is_device_connected()  # Now test with this new instance

        # The assertions below should target the mocks as they were called by 'service.is_device_connected()'

        # ensure_connection is called by _ensure_hid_communicator, which is called by is_device_connected
        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        self.mock_hid_communicator_instance.write_report.assert_not_called()
        # ensure_connection is called by _ensure_hid_communicator, which is called by is_device_connected
        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        self.mock_hid_communicator_instance.write_report.assert_not_called()

    def test_is_device_connected_parser_returns_offline(self) -> None:
        """Test is_device_connected returns False if status parser indicates headset is offline."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": False,
        }
        assert not self.service.is_device_connected()

    def test_get_battery_level_success(self) -> None:
        """Test successful retrieval of battery level."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": EXPECTED_BATTERY_LEVEL_HIGH,
            "battery_charging": False,
            "chatmix": 64, # Not directly asserted, part of mock setup
            "raw_battery_status_byte": 0x02,
        }
        assert self.service.get_battery_level() == EXPECTED_BATTERY_LEVEL_HIGH

    def test_get_battery_level_offline(self) -> None:
        """Test get_battery_level returns None when headset is offline."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": False,
        }
        assert self.service.get_battery_level() is None

    def test_get_battery_level_parse_fail(self) -> None:
        """Test get_battery_level returns None when status parsing fails."""
        self.mock_status_parser_instance.parse_status_report.return_value = None
        assert self.service.get_battery_level() is None

    def test_get_chatmix_value_success(self) -> None:
        """Test successful retrieval of chatmix value."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": EXPECTED_BATTERY_LEVEL_HIGH, # Not directly asserted here, part of mock setup
            "battery_charging": False,
            "chatmix": EXPECTED_CHATMIX_VALUE_MID,
            "raw_battery_status_byte": 0x02,
        }
        assert self.service.get_chatmix_value() == EXPECTED_CHATMIX_VALUE_MID

    def test_is_charging_success(self) -> None:
        """Test successful retrieval of charging status."""
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True,
            "battery_percent": 75,
            "battery_charging": True,
            "chatmix": 64,
            "raw_battery_status_byte": 0x01,
        }
        assert self.service.is_charging()

    def test_write_failure_in_get_status_closes_connection(self) -> None:
        """Test that a HID write failure during status update closes the connection."""
        self.reset_common_mocks()
        self.mock_hid_communicator_instance.write_report.return_value = False  # Simulate write failure

        self.service._get_parsed_status_hid()  # noqa: SLF001 # Call the method that experiences the failure

        self.mock_hid_connection_manager_instance.close.assert_called_once()
        assert self.service.hid_communicator is None  # Communicator should be cleared

    def test_read_failure_in_get_status(self) -> None:
        """Test handling of HID read failure during status update."""
        self.reset_common_mocks()
        self.mock_hid_communicator_instance.write_report.return_value = True  # Write succeeds
        self.mock_hid_communicator_instance.read_report.return_value = None  # Read fails

        result = self.service._get_parsed_status_hid()  # noqa: SLF001

        assert result is None
        assert self.service._last_hid_raw_read_data is None  # noqa: SLF001 # Should be cleared
        assert self.service._last_hid_parsed_status is None  # noqa: SLF001


class TestHeadsetServiceCommands(BaseHeadsetServiceTestCase):
    """Tests command sending functionalities of HeadsetService."""

    def test_set_sidetone_level_success(self) -> None:
        """Test successfully setting the sidetone level."""
        encoded_payload = [0x01, 0x02]
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = encoded_payload
        self.mock_hid_communicator_instance.write_report.return_value = True

        result = self.service.set_sidetone_level(50)

        assert result
        self.mock_command_encoder_instance.encode_set_sidetone.assert_called_once_with(
            50,
        )
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(
            report_id=0,
            data=encoded_payload,
        )

    def test_set_sidetone_level_encoder_returns_none(self) -> None:
        """Test set_sidetone_level handles None from command encoder."""
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = None  # Simulate encoding error

        result = self.service.set_sidetone_level(50)
        assert not result
        self.mock_hid_communicator_instance.write_report.assert_not_called()

    def test_set_sidetone_level_write_fail(self) -> None:
        """Test set_sidetone_level handles HID write failure."""
        encoded_payload = [0x01, 0x02]
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = encoded_payload
        self.mock_hid_communicator_instance.write_report.return_value = False  # Write fails

        result = self.service.set_sidetone_level(50)

        assert not result
        self.mock_hid_connection_manager_instance.close.assert_called_once()  # Ensure connection is closed on failure
        assert self.service.hid_communicator is None

    def test_set_inactive_timeout_success(self) -> None:
        """Test successfully setting the inactive timeout."""
        payload = [0x0A, 30]
        self.mock_command_encoder_instance.encode_set_inactive_timeout.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        assert self.service.set_inactive_timeout(30)
        self.mock_command_encoder_instance.encode_set_inactive_timeout.assert_called_once_with(
            30,
        )
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(
            report_id=0,
            data=payload,
        )

    def test_set_eq_values_success(self) -> None:
        """Test successfully setting EQ values."""
        values = [1.0] * 10
        payload = [0x0B] + ([0x15] * 10) + [0x00]  # Example payload
        self.mock_command_encoder_instance.encode_set_eq_values.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        assert self.service.set_eq_values(values)
        self.mock_command_encoder_instance.encode_set_eq_values.assert_called_once_with(
            values,
        )
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(
            report_id=0,
            data=payload,
        )

    def test_set_eq_preset_id_success(self) -> None:
        """Test successfully setting an EQ preset by ID."""
        preset_id = 1
        payload = [0x0C] + ([0x10] * 10) + [0x00]  # Example payload
        self.mock_command_encoder_instance.encode_set_eq_preset_id.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        assert self.service.set_eq_preset_id(preset_id)
        self.mock_command_encoder_instance.encode_set_eq_preset_id.assert_called_once_with(
            preset_id,
        )
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(
            report_id=0,
            data=payload,
        )

    def test_close_method(self) -> None:
        """Test the close method of HeadsetService."""
        self.service.close()
        self.mock_hid_connection_manager_instance.close.assert_called_once()
        assert self.service.hid_communicator is None


if __name__ == "__main__":
    unittest.main()
