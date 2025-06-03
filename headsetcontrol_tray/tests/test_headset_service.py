import unittest
from unittest import mock
from unittest.mock import Mock, patch
import os
import tempfile

# Attempt to import from the correct location
try:
    from headsetcontrol_tray.headset_service import HeadsetService, UDEV_RULE_CONTENT, UDEV_RULE_FILENAME, STEELSERIES_VID, TARGET_PIDS
    from headsetcontrol_tray import app_config
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from headset_service import HeadsetService, UDEV_RULE_CONTENT, UDEV_RULE_FILENAME, STEELSERIES_VID, TARGET_PIDS
    import app_config

# Original TestHeadsetServiceUdevRules is removed as _check_udev_rules no longer exists.
# Tests for _create_udev_rules are still relevant as the method itself was not removed,
# only how it's called. We can integrate these into a new test class or keep them separate.
# For now, let's keep them focused on _create_udev_rules functionality itself,
# and add new tests for _connect_hid_device calling it.

class TestHeadsetServiceCreateUdevRules(unittest.TestCase):
    def setUp(self):
        # We need a HeadsetService instance, but its __init__ calls _connect_hid_device,
        # which we might not want for these specific tests if they focus *only* on _create_udev_rules.
        # However, _create_udev_rules sets an instance variable `self.udev_setup_details`.
        # Patching __init__ to do nothing simplifies this.
        with patch.object(HeadsetService, '_connect_hid_device', return_value=None) as mock_connect:
            self.service = HeadsetService()
            # If __init__ was more complex, we might need more elaborate __init__ mocking.
            # For now, this ensures _connect_hid_device within __init__ doesn't run its full course.
            # Reset udev_setup_details as it's set by _create_udev_rules
            self.service.udev_setup_details = None


    @patch('headsetcontrol_tray.headset_service.logger')
    @patch('tempfile.NamedTemporaryFile')
    def test_create_rules_success_populates_details(self, mock_named_temp_file, mock_logger):
        mock_temp_fd_context_manager = mock_named_temp_file.return_value.__enter__.return_value
        mock_temp_fd_context_manager.name = "/tmp/fake_temp_rule_file.rules"
        mock_temp_fd_context_manager.write = Mock()

        self.assertTrue(self.service._create_udev_rules())
        self.assertIsNotNone(self.service.udev_setup_details)
        self.assertEqual(self.service.udev_setup_details["temp_file_path"], "/tmp/fake_temp_rule_file.rules")
        self.assertEqual(self.service.udev_setup_details["rule_filename"], UDEV_RULE_FILENAME)
        mock_temp_fd_context_manager.write.assert_called_once_with(UDEV_RULE_CONTENT + "\n")
        self.assertGreaterEqual(mock_logger.info.call_count, 4)

    @patch('headsetcontrol_tray.headset_service.logger')
    @patch('tempfile.NamedTemporaryFile')
    def test_create_rules_io_error_on_write_details_none(self, mock_named_temp_file, mock_logger):
        mock_temp_fd_context_manager = mock_named_temp_file.return_value.__enter__.return_value
        mock_temp_fd_context_manager.name = "/tmp/fake_temp_rule_file_ioerror.rules"
        mock_temp_fd_context_manager.write.side_effect = IOError("Failed to write temp file")

        self.assertFalse(self.service._create_udev_rules())
        self.assertIsNone(self.service.udev_setup_details)
        mock_logger.error.assert_called_with(mock.ANY)


class TestHeadsetServiceConnectionFailure(unittest.TestCase):

    @patch('headsetcontrol_tray.headset_service.hid.Device')
    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    @patch.object(HeadsetService, '_create_udev_rules', return_value=True) # Mock _create_udev_rules
    def test_connect_device_fails_all_attempts_calls_create_rules(self, mock_create_rules, mock_hid_enumerate, mock_hid_device_class):
        # Simulate hid.enumerate finding one or more potential devices
        mock_hid_enumerate.return_value = [
            {'vendor_id': STEELSERIES_VID, 'product_id': TARGET_PIDS[0], 'path': b'path1', 'interface_number': 0},
            {'vendor_id': STEELSERIES_VID, 'product_id': TARGET_PIDS[0], 'path': b'path2', 'interface_number': 3}
        ]
        # Simulate hid.Device constructor failing (raising an exception) for any path
        mock_hid_device_class.side_effect = Exception("Failed to open HID device")

        service = HeadsetService() # __init__ calls _connect_hid_device

        self.assertIsNone(service.hid_device) # Should not have connected
        mock_create_rules.assert_called_once() # Key assertion: _create_udev_rules was called

    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    @patch.object(HeadsetService, '_create_udev_rules', return_value=True) # Mock _create_udev_rules
    def test_connect_device_enumerate_empty_calls_create_rules(self, mock_create_rules, mock_hid_enumerate):
        # Simulate hid.enumerate finding no devices
        mock_hid_enumerate.return_value = []

        service = HeadsetService() # __init__ calls _connect_hid_device

        self.assertIsNone(service.hid_device) # Should not have connected
        mock_create_rules.assert_called_once() # Key assertion: _create_udev_rules was called

    @patch('headsetcontrol_tray.headset_service.hid.Device')
    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    @patch.object(HeadsetService, '_create_udev_rules', return_value=True)
    def test_connect_device_success_does_not_call_create_rules(self, mock_create_rules, mock_hid_enumerate, mock_hid_device_class):
        # Simulate hid.enumerate finding a device
        mock_hid_enumerate.return_value = [
             {'vendor_id': STEELSERIES_VID, 'product_id': TARGET_PIDS[0], 'path': b'path1', 'interface_number': 0}
        ]
        # Simulate hid.Device succeeding
        mock_hid_device_instance = Mock()
        mock_hid_device_class.return_value = mock_hid_device_instance

        service = HeadsetService()

        self.assertIsNotNone(service.hid_device) # Should have connected
        mock_create_rules.assert_not_called() # Key: _create_udev_rules NOT called


if __name__ == '__main__':
    unittest.main()
