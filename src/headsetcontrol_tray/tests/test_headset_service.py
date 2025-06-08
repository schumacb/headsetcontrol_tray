import os
import unittest
from unittest import mock
from unittest.mock import Mock, patch

# Attempt to import from the correct location
try:
    from headsetcontrol_tray.headset_service import (
        STEELSERIES_VID,  # Keep relevant imports
        TARGET_PIDS,
        UDEV_RULE_CONTENT,
        UDEV_RULE_FILENAME,
        HeadsetService,
    )
    # from headsetcontrol_tray import app_config # Unused direct import
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from headset_service import (
        STEELSERIES_VID,  # Keep relevant imports
        TARGET_PIDS,
        UDEV_RULE_CONTENT,
        UDEV_RULE_FILENAME,
        HeadsetService,
    )

class TestHeadsetServiceCreateUdevRules(unittest.TestCase):
    def setUp(self):
        # We need a HeadsetService instance, but its __init__ calls _connect_hid_device,
        # which we might not want for these specific tests if they focus *only* on _create_udev_rules.
        # However, _create_udev_rules sets an instance variable `self.udev_setup_details`.
        # Patching __init__ to do nothing simplifies this.
        with patch.object(HeadsetService, "_connect_hid_device", return_value=None): # mock_connect was unused
            self.service = HeadsetService()
            # If __init__ was more complex, we might need more elaborate __init__ mocking.
            # For now, this ensures _connect_hid_device within __init__ doesn't run its full course.
            # Reset udev_setup_details as it's set by _create_udev_rules
            self.service.udev_setup_details = None


    @patch("headsetcontrol_tray.headset_service.logger")
    @patch("tempfile.NamedTemporaryFile")
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

    @patch("headsetcontrol_tray.headset_service.logger")
    @patch("tempfile.NamedTemporaryFile")
    def test_create_rules_io_error_on_write_details_none(self, mock_named_temp_file, mock_logger):
        mock_temp_fd_context_manager = mock_named_temp_file.return_value.__enter__.return_value
        mock_temp_fd_context_manager.name = "/tmp/fake_temp_rule_file_ioerror.rules"
        mock_temp_fd_context_manager.write.side_effect = OSError("Failed to write temp file")

        self.assertFalse(self.service._create_udev_rules())
        self.assertIsNone(self.service.udev_setup_details)
        mock_logger.error.assert_called_with(mock.ANY)


class TestHeadsetServiceConnectionFailure(unittest.TestCase):

    @patch("headsetcontrol_tray.headset_service.hid.Device")
    @patch("headsetcontrol_tray.headset_service.hid.enumerate")
    @patch.object(HeadsetService, "_create_udev_rules", return_value=True) # Mock _create_udev_rules
    def test_connect_device_fails_all_attempts_calls_create_rules(self, mock_create_rules, mock_hid_enumerate, mock_hid_device_class):
        # Simulate hid.enumerate finding one or more potential devices
        mock_hid_enumerate.return_value = [
            {"vendor_id": STEELSERIES_VID, "product_id": TARGET_PIDS[0], "path": b"path1", "interface_number": 0},
            {"vendor_id": STEELSERIES_VID, "product_id": TARGET_PIDS[0], "path": b"path2", "interface_number": 3},
        ]
        # Simulate hid.Device constructor failing (raising an exception) for any path
        mock_hid_device_class.side_effect = Exception("Failed to open HID device")

        # Patch out the __init__ subprocess call for headsetcontrol availability for this specific test context
        with patch("subprocess.run") as mock_sub_run_init:
            service = HeadsetService() # __init__ calls _connect_hid_device

        self.assertIsNone(service.hid_device) # Should not have connected
        mock_create_rules.assert_called_once() # Key assertion: _create_udev_rules was called

    @patch("headsetcontrol_tray.headset_service.hid.enumerate")
    @patch.object(HeadsetService, "_create_udev_rules", return_value=True) # Mock _create_udev_rules
    def test_connect_device_enumerate_empty_calls_create_rules(self, mock_create_rules, mock_hid_enumerate):
        # Simulate hid.enumerate finding no devices
        mock_hid_enumerate.return_value = []

        with patch("subprocess.run") as mock_sub_run_init:
            service = HeadsetService() # __init__ calls _connect_hid_device

        self.assertIsNone(service.hid_device) # Should not have connected
        mock_create_rules.assert_called_once() # Key assertion: _create_udev_rules was called

    @patch("headsetcontrol_tray.headset_service.hid.Device")
    @patch("headsetcontrol_tray.headset_service.hid.enumerate")
    @patch.object(HeadsetService, "_create_udev_rules", return_value=True)
    def test_connect_device_success_does_not_call_create_rules(self, mock_create_rules, mock_hid_enumerate, mock_hid_device_class):
        # Simulate hid.enumerate finding a device
        mock_hid_enumerate.return_value = [
             {"vendor_id": STEELSERIES_VID, "product_id": TARGET_PIDS[0], "path": b"path1", "interface_number": 0, "usage_page": 0xffc0, "usage": 0x0001},
        ]
        # Simulate hid.Device succeeding
        mock_hid_device_instance = Mock()
        mock_hid_device_class.return_value = mock_hid_device_instance

        with patch("subprocess.run") as mock_sub_run_init:
            service = HeadsetService()

        self.assertIsNotNone(service.hid_device) # Should have connected
        mock_create_rules.assert_not_called() # Key: _create_udev_rules NOT called


class TestHeadsetServiceNoCliFallback(unittest.TestCase):
    def setUp(self):
        self.connect_patcher = patch.object(HeadsetService, "_connect_hid_device", return_value=None)
        self.mock_connect_hid = self.connect_patcher.start()
        # We instantiate service here, __init__ will call the patched _connect_hid_device
        self.service = HeadsetService()
        self.service.hid_device = None # Explicitly set to None after __init__

    def tearDown(self):
        self.connect_patcher.stop()

    @patch("subprocess.run")
    def test_init_no_headsetcontrol_check(self, mock_subprocess_run_ext):
        # This test needs to check __init__ specifically.
        # The class-level _connect_hid_device patch is active.
        # We need to ensure that the subprocess.run within __init__ (for headsetcontrol check) is not called.

        # Stop the class setUp patcher to allow __init__ to run with a fresh subprocess.run mock
        self.connect_patcher.stop()

        # Specific patch for _connect_hid_device during this __init__ call
        with patch.object(HeadsetService, "_connect_hid_device", return_value=None) as mock_connect_in_init:
            # This is the subprocess.run we want to inspect for the headsetcontrol check
            with patch("subprocess.run") as mock_subprocess_for_init_check:
                 service_init_test = HeadsetService()

        # Assert that subprocess.run was NOT called with 'headsetcontrol --version'
        # This was removed, so it should not be called at all for that purpose.
        # The only subprocess call might be from _create_udev_rules if connection fails.
        # Since _connect_hid_device is mocked to None, _create_udev_rules might be called.
        # We are interested if 'headsetcontrol' was directly called by __init__ for version check.

        found_headsetcontrol_call = False
        for call_obj in mock_subprocess_for_init_check.call_args_list:
            args, _ = call_obj
            if len(args) > 0 and isinstance(args[0], list) and "headsetcontrol" in args[0][0]:
                if "--version" in args[0]: # Check if it was the version call
                    found_headsetcontrol_call = True
                    break
        self.assertFalse(found_headsetcontrol_call, "subprocess.run was called for 'headsetcontrol --version'")

        self.assertFalse(hasattr(service_init_test, "headsetcontrol_available"))

        # Restart the class setUp patcher
        self.mock_connect_hid = self.connect_patcher.start()


    @patch("headsetcontrol_tray.headset_service.logger")
    def test_get_sidetone_level_returns_none_and_logs_warning(self, mock_logger):
        self.service.hid_device = None
        result = self.service.get_sidetone_level()
        self.assertIsNone(result)
        mock_logger.warning.assert_any_call("get_sidetone_level: Cannot retrieve via HID (not implemented) and CLI fallback removed.")

    @patch("headsetcontrol_tray.headset_service.logger")
    def test_get_inactive_timeout_returns_none_and_logs_warning(self, mock_logger):
        self.service.hid_device = None
        result = self.service.get_inactive_timeout()
        self.assertIsNone(result)
        mock_logger.warning.assert_any_call("get_inactive_timeout: Cannot retrieve via HID (not implemented) and CLI fallback removed.")

    @patch.object(HeadsetService, "_set_sidetone_level_hid", return_value=True)
    @patch("subprocess.run") # To ensure CLI is not called
    def test_set_sidetone_level_uses_hid_only_success(self, mock_subprocess_run, mock_set_sidetone_hid):
        # Ensure hid_device is mocked as connected for this path
        self.service.hid_device = Mock()
        self.mock_connect_hid.return_value = True # _ensure_hid_connection returns True

        result = self.service.set_sidetone_level(50)
        self.assertTrue(result)
        mock_set_sidetone_hid.assert_called_once_with(50)
        for call_args in mock_subprocess_run.call_args_list:
            args, _ = call_args
            if len(args) > 0 and isinstance(args[0], list) and "headsetcontrol" in args[0][0]:
                 self.fail("subprocess.run called with headsetcontrol")

    @patch.object(HeadsetService, "_set_sidetone_level_hid", return_value=False)
    @patch("subprocess.run")
    def test_set_sidetone_level_hid_failure_no_cli_fallback(self, mock_subprocess_run, mock_set_sidetone_hid_failure):
        self.service.hid_device = Mock()
        self.mock_connect_hid.return_value = True

        result = self.service.set_sidetone_level(50)
        self.assertFalse(result)
        mock_set_sidetone_hid_failure.assert_called_once_with(50)
        for call_args in mock_subprocess_run.call_args_list:
            args, _ = call_args
            if len(args) > 0 and isinstance(args[0], list) and "headsetcontrol" in args[0][0]:
                 self.fail("subprocess.run called with headsetcontrol")

    @patch.object(HeadsetService, "_get_parsed_status_hid")
    @patch("subprocess.run")
    def test_get_battery_level_uses_hid_only_success(self, mock_subprocess_run, mock_get_status_hid):
        mock_get_status_hid.return_value = {"headset_online": True, "battery_percent": 75, "battery_charging": False, "chatmix": 64}
        self.service.hid_device = Mock()
        self.mock_connect_hid.return_value = True

        level = self.service.get_battery_level()
        self.assertEqual(level, 75)
        mock_get_status_hid.assert_called()
        for call_args in mock_subprocess_run.call_args_list:
            args, _ = call_args
            if len(args) > 0 and isinstance(args[0], list) and "headsetcontrol" in args[0][0]:
                self.fail("subprocess.run called with headsetcontrol")

    @patch.object(HeadsetService, "_get_parsed_status_hid", return_value=None)
    @patch("subprocess.run")
    def test_get_battery_level_hid_failure_no_cli_fallback(self, mock_subprocess_run, mock_get_status_hid_failure):
        self.service.hid_device = Mock()
        self.mock_connect_hid.return_value = True

        level = self.service.get_battery_level()
        self.assertIsNone(level)
        mock_get_status_hid_failure.assert_called()
        for call_args in mock_subprocess_run.call_args_list:
            args, _ = call_args
            if len(args) > 0 and isinstance(args[0], list) and "headsetcontrol" in args[0][0]:
                 self.fail("subprocess.run called with headsetcontrol")

if __name__ == "__main__":
    unittest.main()
