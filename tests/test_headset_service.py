import unittest
from unittest.mock import MagicMock, patch, call, ANY
import hid # Keep for type hinting if hid.Device is used
import os
import sys

# Ensure src is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from headsetcontrol_tray import app_config
from headsetcontrol_tray.headset_service import HeadsetService
# Removed direct import of constants like STEELSERIES_VID from headset_service, will use app_config
from headsetcontrol_tray.udev_manager import UDEV_RULE_FILENAME as STEELSERIES_UDEV_FILENAME # Correctly import this

# New imports for mocked classes (though patches target their path in headset_service.py)
# from headsetcontrol_tray.hid_manager import HIDConnectionManager
# from headsetcontrol_tray.hid_communicator import HIDCommunicator
# from headsetcontrol_tray.udev_manager import UDEVManager
# from headsetcontrol_tray.headset_status import HeadsetStatusParser, HeadsetCommandEncoder


# Common mock setup for HeadsetService dependencies
# Order of decorators matters: last one is first arg to setUp
@patch('headsetcontrol_tray.headset_service.logger')
@patch('headsetcontrol_tray.headset_service.HeadsetCommandEncoder')
@patch('headsetcontrol_tray.headset_service.HeadsetStatusParser')
@patch('headsetcontrol_tray.headset_service.UDEVManager')
@patch('headsetcontrol_tray.headset_service.HIDCommunicator')
@patch('headsetcontrol_tray.headset_service.HIDConnectionManager')
@patch('headsetcontrol_tray.headset_service.os.path.exists') # Innermost decorator, last argument to setUp
class BaseHeadsetServiceTestCase(unittest.TestCase):
    def setUp(self, mock_logger, mock_command_encoder_class, mock_status_parser_class, # type: ignore[override]
                  mock_udev_manager_class, mock_hid_communicator_class,
                  mock_hid_connection_manager_class, mock_os_path_exists):

        # Assignments must match the new parameter order
        self.mock_logger = mock_logger
        self.mock_command_encoder_instance = mock_command_encoder_class.return_value
        self.mock_status_parser_instance = mock_status_parser_class.return_value
        self.mock_udev_manager_instance = mock_udev_manager_class.return_value
        self.MockHIDCommunicatorClass = mock_hid_communicator_class  # Store the class itself
        self.mock_hid_communicator_instance = mock_hid_communicator_class.return_value
        self.mock_hid_connection_manager_instance = mock_hid_connection_manager_class.return_value
        self.mock_os_path_exists = mock_os_path_exists


        # Default mock behaviors
        self.mock_hid_device_instance = MagicMock(spec=hid.Device) # Mock the hid.Device object
        self.mock_hid_device_instance.path = b'/dev/hidraw_mock' # Example path

        self.mock_hid_connection_manager_instance.ensure_connection.return_value = True
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance

        # When HeadsetService initializes, it calls _ensure_hid_communicator.
        # This might try to create an HIDCommunicator instance.
        # We ensure that this creation uses the mocked instance.
        self.MockHIDCommunicatorClass.return_value = self.mock_hid_communicator_instance

        self.service = HeadsetService()

        # Reset call counts for mocks that might be called during HeadsetService initialization
        self.reset_common_mocks()

    def reset_common_mocks(self):
        self.mock_os_path_exists.reset_mock()
        self.mock_hid_connection_manager_instance.reset_mock()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = True # Reset to default success
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance

        self.MockHIDCommunicatorClass.reset_mock()
        self.MockHIDCommunicatorClass.return_value = self.mock_hid_communicator_instance # Re-assign
        self.mock_hid_communicator_instance.reset_mock()

        self.mock_udev_manager_instance.reset_mock()
        self.mock_status_parser_instance.reset_mock()
        self.mock_command_encoder_instance.reset_mock()
        self.mock_logger.reset_mock()


class TestHeadsetServiceUdevInteraction(BaseHeadsetServiceTestCase):

    def test_init_connection_fail_udev_rules_missing_triggers_creation(self):
        # Reset mocks called during setUp's HeadsetService() instantiation
        self.reset_common_mocks()

        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None # No device if connection fails
        self.mock_os_path_exists.return_value = False # UDEV rules do NOT exist
        self.mock_udev_manager_instance.create_rules_interactive.return_value = True # Mock successful rule creation guidance

        # Re-initialize service to test __init__ behavior with these conditions
        # Need to ensure the HIDCommunicator isn't re-created with old mocks by default __init__
        with patch('headsetcontrol_tray.headset_service.HIDCommunicator') as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService()

        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        self.mock_os_path_exists.assert_called_with(f"/etc/udev/rules.d/{STEELSERIES_UDEV_FILENAME}")
        self.mock_udev_manager_instance.create_rules_interactive.assert_called_once()
        self.assertIsNotNone(service.udev_setup_details)

    def test_init_connection_fail_udev_rules_exist_no_creation(self):
        self.reset_common_mocks()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None
        self.mock_os_path_exists.return_value = True # UDEV rules EXIST

        with patch('headsetcontrol_tray.headset_service.HIDCommunicator') as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService()

        self.mock_os_path_exists.assert_called_with(f"/etc/udev/rules.d/{STEELSERIES_UDEV_FILENAME}")
        self.mock_udev_manager_instance.create_rules_interactive.assert_not_called()
        self.assertIsNone(service.udev_setup_details) # Should be None as interactive creation wasn't called

    def test_get_udev_setup_details_returns_data(self):
        self.reset_common_mocks()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None
        self.mock_os_path_exists.return_value = False

        dummy_details = {"temp_file_path": "/tmp/temp", "final_file_path": "/etc/rules", "rule_content": "RULE"}
        self.mock_udev_manager_instance.create_rules_interactive.return_value = True
        self.mock_udev_manager_instance.get_last_udev_setup_details.return_value = dummy_details

        with patch('headsetcontrol_tray.headset_service.HIDCommunicator') as local_mock_comm_class:
            local_mock_comm_class.return_value = self.mock_hid_communicator_instance
            service = HeadsetService() # Trigger the call path

        self.assertEqual(service.get_udev_setup_details(), dummy_details)


class TestHeadsetServiceConnectionAndStatus(BaseHeadsetServiceTestCase):

    def test_is_device_connected_success(self):
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = True
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = self.mock_hid_device_instance
        self.mock_hid_communicator_instance.write_report.return_value = True
        # Make read_report return valid status bytes
        status_report_bytes = b'\x00' * app_config.HID_INPUT_REPORT_LENGTH_STATUS
        self.mock_hid_communicator_instance.read_report.return_value = status_report_bytes
        self.mock_status_parser_instance.parse_status_report.return_value = {"headset_online": True, "battery_percent": 50}

        self.assertTrue(self.service.is_device_connected())
        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        self.mock_status_parser_instance.parse_status_report.assert_called_with(status_report_bytes)

    def test_is_device_connected_manager_fails_connection(self):
        self.reset_common_mocks()
        self.mock_hid_connection_manager_instance.ensure_connection.return_value = False
        self.mock_hid_connection_manager_instance.get_hid_device.return_value = None
        self.mock_os_path_exists.return_value = True # Assume udev rules exist for this test

        self.assertFalse(self.service.is_device_connected())
        # ensure_connection is called by _ensure_hid_communicator, which is called by is_device_connected
        self.mock_hid_connection_manager_instance.ensure_connection.assert_called()
        self.mock_hid_communicator_instance.write_report.assert_not_called()

    def test_is_device_connected_parser_returns_offline(self):
        self.mock_status_parser_instance.parse_status_report.return_value = {"headset_online": False}
        self.assertFalse(self.service.is_device_connected())

    def test_get_battery_level_success(self):
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True, "battery_percent": 75, "battery_charging": False, "chatmix": 64, "raw_battery_status_byte": 0x02
        }
        self.assertEqual(self.service.get_battery_level(), 75)

    def test_get_battery_level_offline(self):
        self.mock_status_parser_instance.parse_status_report.return_value = {"headset_online": False}
        self.assertIsNone(self.service.get_battery_level())

    def test_get_battery_level_parse_fail(self):
        self.mock_status_parser_instance.parse_status_report.return_value = None
        self.assertIsNone(self.service.get_battery_level())

    def test_get_chatmix_value_success(self):
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True, "battery_percent": 75, "battery_charging": False, "chatmix": 32, "raw_battery_status_byte": 0x02
        }
        self.assertEqual(self.service.get_chatmix_value(), 32)

    def test_is_charging_success(self):
        self.mock_status_parser_instance.parse_status_report.return_value = {
            "headset_online": True, "battery_percent": 75, "battery_charging": True, "chatmix": 64, "raw_battery_status_byte": 0x01
        }
        self.assertTrue(self.service.is_charging())

    def test_write_failure_in_get_status_closes_connection(self):
        self.reset_common_mocks()
        self.mock_hid_communicator_instance.write_report.return_value = False # Simulate write failure

        self.service._get_parsed_status_hid() # Call the method that experiences the failure

        self.mock_hid_connection_manager_instance.close.assert_called_once()
        self.assertIsNone(self.service.hid_communicator) # Communicator should be cleared

    def test_read_failure_in_get_status(self):
        self.reset_common_mocks()
        self.mock_hid_communicator_instance.write_report.return_value = True # Write succeeds
        self.mock_hid_communicator_instance.read_report.return_value = None # Read fails

        result = self.service._get_parsed_status_hid()

        self.assertIsNone(result)
        self.assertIsNone(self.service._last_hid_raw_read_data) # Should be cleared
        self.assertIsNone(self.service._last_hid_parsed_status)


class TestHeadsetServiceCommands(BaseHeadsetServiceTestCase):

    def test_set_sidetone_level_success(self):
        encoded_payload = [0x01, 0x02]
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = encoded_payload
        self.mock_hid_communicator_instance.write_report.return_value = True

        result = self.service.set_sidetone_level(50)

        self.assertTrue(result)
        self.mock_command_encoder_instance.encode_set_sidetone.assert_called_once_with(50)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=encoded_payload)

    def test_set_sidetone_level_encoder_returns_none(self):
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = None # Simulate encoding error

        result = self.service.set_sidetone_level(50)
        self.assertFalse(result)
        self.mock_hid_communicator_instance.write_report.assert_not_called()


    def test_set_sidetone_level_write_fail(self):
        encoded_payload = [0x01, 0x02]
        self.mock_command_encoder_instance.encode_set_sidetone.return_value = encoded_payload
        self.mock_hid_communicator_instance.write_report.return_value = False # Write fails

        result = self.service.set_sidetone_level(50)

        self.assertFalse(result)
        self.mock_hid_connection_manager_instance.close.assert_called_once() # Ensure connection is closed on failure
        self.assertIsNone(self.service.hid_communicator)

    def test_set_inactive_timeout_success(self):
        payload = [0x0A, 30]
        self.mock_command_encoder_instance.encode_set_inactive_timeout.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        self.assertTrue(self.service.set_inactive_timeout(30))
        self.mock_command_encoder_instance.encode_set_inactive_timeout.assert_called_once_with(30)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=payload)

    def test_set_eq_values_success(self):
        values = [1.0] * 10
        payload = [0x0B] + ([0x15] * 10) + [0x00] # Example payload
        self.mock_command_encoder_instance.encode_set_eq_values.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        self.assertTrue(self.service.set_eq_values(values))
        self.mock_command_encoder_instance.encode_set_eq_values.assert_called_once_with(values)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=payload)

    def test_set_eq_preset_id_success(self):
        preset_id = 1
        payload = [0x0C] + ([0x10] * 10) + [0x00] # Example payload
        self.mock_command_encoder_instance.encode_set_eq_preset_id.return_value = payload
        self.mock_hid_communicator_instance.write_report.return_value = True
        self.assertTrue(self.service.set_eq_preset_id(preset_id))
        self.mock_command_encoder_instance.encode_set_eq_preset_id.assert_called_once_with(preset_id)
        self.mock_hid_communicator_instance.write_report.assert_called_once_with(report_id=0, data=payload)

    def test_close_method(self):
        self.service.close()
        self.mock_hid_connection_manager_instance.close.assert_called_once()
        self.assertIsNone(self.service.hid_communicator)


if __name__ == "__main__":
    unittest.main()