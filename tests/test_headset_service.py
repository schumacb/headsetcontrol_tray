import os
import unittest
import sys # Moved sys import
from unittest import mock
from unittest.mock import Mock, patch, MagicMock

# Ensure the package root (src directory) is in path for mypy and runtime
# This assumes 'tests' is one level down from repo root, and 'src' is at repo root.
# Adjust if structure is tests/headsetcontrol_tray and src/headsetcontrol_tray
# Based on other files, it seems headsetcontrol_tray is directly in src/
# So, tests/ is sibling to src/
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
# Correcting path based on typical project structure where tests/ is sibling to src/
# If tests/ is inside src/, then ".." would be src/, and "../.." would be repo root.
# Assuming tests/ is at repo_root/tests/ and package is repo_root/src/headsetcontrol_tray/
# Then path should be repo_root/src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))


from headsetcontrol_tray.headset_service import (
    STEELSERIES_VID,
    TARGET_PIDS,
    UDEV_RULE_CONTENT,
    UDEV_RULE_FILENAME,
    HeadsetService,
)
from headsetcontrol_tray import app_config # Import app_config for HID constants


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
        assert self.service.udev_setup_details is not None # For mypy
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

    @patch("headsetcontrol_tray.headset_service.hid") # Patch the hid module as imported in headset_service
    @patch.object(HeadsetService, "_create_udev_rules", return_value=True)
    def test_connect_device_fails_all_attempts_calls_create_rules(self, mock_create_rules, mock_hid_module):
        # Simulate hid.enumerate (called as mock_hid_module.enumerate) finding devices
        mock_hid_module.enumerate.return_value = [
            {"vendor_id": STEELSERIES_VID, "product_id": TARGET_PIDS[0], "path": b"path1", "interface_number": 0},
            {"vendor_id": STEELSERIES_VID, "product_id": TARGET_PIDS[0], "path": b"path2", "interface_number": 3},
        ]
        # Simulate hid.Device (called as mock_hid_module.Device) constructor failing
        mock_hid_module.Device = MagicMock(side_effect=Exception("Failed to open HID device"))

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

    @patch("headsetcontrol_tray.headset_service.hid") # Patch the hid module as imported in headset_service
    @patch.object(HeadsetService, "_create_udev_rules", return_value=True)
    def test_connect_device_success_does_not_call_create_rules(self, mock_create_rules, mock_hid_module):
        # Simulate hid.enumerate (mock_hid_module.enumerate) finding a device
        # Ensure this device matches the highest priority criteria in _sort_hid_devices
        pid_for_test = TARGET_PIDS[0] if TARGET_PIDS else 0x1234 # Ensure TARGET_PIDS is not empty
        mock_hid_module.enumerate.return_value = [
             {"vendor_id": STEELSERIES_VID, "product_id": pid_for_test, "path": b"path1",
              "interface_number": app_config.HID_REPORT_INTERFACE,
              "usage_page": app_config.HID_REPORT_USAGE_PAGE,
              "usage": app_config.HID_REPORT_USAGE_ID},
        ]
        # Simulate hid.Device (mock_hid_module.Device) succeeding
        # Note: if hid module itself is a C extension and hid.Device is a type,
        #       spec=hid.Device might be useful if 'hid' can be imported in test context.
        #       For now, a simple MagicMock is often sufficient.
        mock_hid_device_instance = MagicMock()
        mock_hid_module.Device.return_value = mock_hid_device_instance

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
        self.service.hid_device = None # Ensure service thinks device is not connected for this test path
        self.mock_connect_hid.return_value = False # _ensure_hid_connection returns False
        result = self.service.get_sidetone_level()
        self.assertIsNone(result)
        mock_logger.warning.assert_any_call("get_sidetone_level: Cannot retrieve via HID (not implemented) and CLI fallback removed.")

    @patch("headsetcontrol_tray.headset_service.logger")
    def test_get_inactive_timeout_returns_none_and_logs_warning(self, mock_logger):
        self.service.hid_device = None
        self.mock_connect_hid.return_value = False
        result = self.service.get_inactive_timeout()
        self.assertIsNone(result)
        mock_logger.warning.assert_any_call("get_inactive_timeout: Cannot retrieve via HID (not implemented) and CLI fallback removed.")

    @patch.object(HeadsetService, "_set_sidetone_level_hid", return_value=True)
    @patch("subprocess.run") # To ensure CLI is not called
    def test_set_sidetone_level_uses_hid_only_success(self, mock_subprocess_run, mock_set_sidetone_hid):
        self.service.hid_device = Mock() # Simulate connected device object
        self.mock_connect_hid.return_value = True # _ensure_hid_connection returns True

        result = self.service.set_sidetone_level(50)
        self.assertTrue(result)
        mock_set_sidetone_hid.assert_called_once_with(50)
        for call_args in mock_subprocess_run.call_args_list: # Check no CLI calls
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


class TestHeadsetServiceFindPotentialDevices(unittest.TestCase):
    def setUp(self):
        # Patch _connect_hid_device in HeadsetService's __init__ path to prevent it from running,
        # as we want to test _find_potential_hid_devices in isolation.
        self.connect_patcher = patch.object(HeadsetService, '_connect_hid_device', return_value=None)
        self.mock_connect_hid_in_init = self.connect_patcher.start()
        self.service = HeadsetService()

    def tearDown(self):
        self.connect_patcher.stop()

    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    def test_find_potential_devices_enumerate_empty(self, mock_hid_enumerate):
        mock_hid_enumerate.return_value = []
        result = self.service._find_potential_hid_devices()
        self.assertEqual(result, [])
        mock_hid_enumerate.assert_called_once_with(STEELSERIES_VID, 0)

    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    def test_find_potential_devices_enumerate_no_match(self, mock_hid_enumerate):
        mock_hid_enumerate.return_value = [
            {'vendor_id': 0x0001, 'product_id': 0x0001, 'path': b'path1', 'release_number': 1, 'interface_number': 0, 'usage_page': 0, 'usage': 0, 'product_string': 'DeviceNonMatch'},
            {'vendor_id': STEELSERIES_VID, 'product_id': 0x9999, 'path': b'path2', 'release_number': 1, 'interface_number': 0, 'usage_page': 0, 'usage': 0, 'product_string': 'DeviceWrongPID'}
        ]
        result = self.service._find_potential_hid_devices()
        self.assertEqual(result, [])

    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    def test_find_potential_devices_enumerate_matches(self, mock_hid_enumerate):
        # Ensure TARGET_PIDS has at least two distinct PIDs for a more robust test, or adjust if not.
        pid1 = TARGET_PIDS[0] if TARGET_PIDS else 0x0001 # Default if empty
        pid2 = TARGET_PIDS[1] if len(TARGET_PIDS) > 1 else pid1
        if pid1 == pid2 and len(TARGET_PIDS) > 1:
             pid2 = TARGET_PIDS[2] if len(TARGET_PIDS) > 2 else pid1


        matching_device1 = {'vendor_id': STEELSERIES_VID, 'product_id': pid1, 'path': b'path1', 'release_number': 1, 'interface_number': 0, 'usage_page': 0, 'usage': 0, 'product_string': 'MatchingDevice1'}
        non_matching_device = {'vendor_id': 0x0001, 'product_id': 0x9999, 'path': b'path2', 'release_number': 1, 'interface_number': 0, 'usage_page': 0, 'usage': 0, 'product_string': 'NonMatchingDevice'}
        matching_device2 = {'vendor_id': STEELSERIES_VID, 'product_id': pid2, 'path': b'path3', 'release_number': 1, 'interface_number': 0, 'usage_page': 0, 'usage': 0, 'product_string': 'MatchingDevice2'}

        mock_hid_enumerate.return_value = [matching_device1, non_matching_device, matching_device2]

        result = self.service._find_potential_hid_devices()

        # Construct expected_devices based on what should match from TARGET_PIDS
        expected_devices = []
        if matching_device1['product_id'] in TARGET_PIDS:
            expected_devices.append(matching_device1)
        if matching_device2['product_id'] in TARGET_PIDS and matching_device1['product_id'] != matching_device2['product_id']: # Avoid duplicates if pid1==pid2
            expected_devices.append(matching_device2)
        elif matching_device2['product_id'] in TARGET_PIDS and matching_device1['product_id'] == matching_device2['product_id'] and matching_device1['path'] != matching_device2['path']:
             # If PIDs are the same but paths are different, both could be valid targets.
             expected_devices.append(matching_device2)


        self.assertEqual(len(result), len(expected_devices))
        for dev_info in result: # Check if all items in result are in expected_devices
            self.assertIn(dev_info, expected_devices)
        for dev_info in expected_devices: # Check if all items in expected_devices are in result
            self.assertIn(dev_info, result)

        self.assertNotIn(non_matching_device, result)


    @patch('headsetcontrol_tray.headset_service.hid.enumerate')
    @patch('headsetcontrol_tray.headset_service.logger')
    def test_find_potential_devices_enumerate_exception(self, mock_logger, mock_hid_enumerate):
        mock_hid_enumerate.side_effect = Exception("HID enumeration failed")
        result = self.service._find_potential_hid_devices()
        self.assertEqual(result, [])
        mock_logger.error.assert_called_with("Error enumerating HID devices: HID enumeration failed")

    # Tests for _sort_hid_devices
    def test_sort_hid_devices_empty_list(self):
        self.assertEqual(self.service._sort_hid_devices([]), [])

    def test_sort_hid_devices_single_device(self):
        pid_for_test_sort = TARGET_PIDS[0] if TARGET_PIDS else 0x1234
        single_device = {
            'vendor_id': STEELSERIES_VID,
            'product_id': pid_for_test_sort,
            'path': b'path1',
            'interface_number': -1,
            'usage_page': 0,
            'usage': 0
        }
        # Create a list and pass a copy to the method, as it sorts in-place
        single_device_list_copy = [single_device.copy()]
        # The method sorts in-place and returns the list.
        # For a single device, the content of the list (the dict itself) should remain unchanged.
        sorted_list = self.service._sort_hid_devices(single_device_list_copy)
        self.assertEqual(sorted_list, [single_device]) # Compare content


    def test_sort_hid_devices_sorting_logic(self):
        # Base attributes for all devices, ensuring all necessary keys are present
        base_attrs = {
            'vendor_id': STEELSERIES_VID,
            'interface_number': -1, # Default, overridden if specific to sort tier
            'usage_page': 0,      # Default, overridden if specific
            'usage': 0,           # Default, overridden if specific
        }

        pid_for_sort_tests = TARGET_PIDS[0] if TARGET_PIDS else 0x1234
        # Device E: Default priority (2)
        dev_e_default = {**base_attrs, 'product_id': pid_for_sort_tests, 'path': b'pathE', 'interface_number': 1, 'usage_page': 0x0000, 'usage': 0x0000, 'name': 'E_Default'}
        # Device D: Usage page 0xFFC0 (1)
        dev_d_usage_page = {**base_attrs, 'product_id': pid_for_sort_tests, 'path': b'pathD', 'interface_number': 1, 'usage_page': app_config.HID_REPORT_USAGE_PAGE, 'usage': 0x0000, 'name': 'D_UsagePage'}
        # Device C: Interface 3 (0)
        dev_c_interface3 = {**base_attrs, 'product_id': pid_for_sort_tests, 'path': b'pathC', 'interface_number': 3, 'usage_page': 0x0000, 'usage': 0x0000, 'name': 'C_Interface3'}
        # Device B: PID 0x2202 (ARCTIS_NOVA_7_USER_PID) and interface 0 (-1)
        # Ensure ARCTIS_NOVA_7_USER_PID is in TARGET_PIDS for this test to be meaningful
        # For this test, let's assume it is, or use a PID known to be in TARGET_PIDS for the ARCTIS_NOVA_7_USER_PID role.
        # If app_config.ARCTIS_NOVA_7_USER_PID is not guaranteed to be in TARGET_PIDS (which it should be),
        # this test might need adjustment or ensure TARGET_PIDS includes it for the test setup.
        user_pid_for_test = app_config.ARCTIS_NOVA_7_USER_PID if app_config.ARCTIS_NOVA_7_USER_PID in TARGET_PIDS else pid_for_sort_tests

        dev_b_pid2202_if0 = {**base_attrs, 'product_id': user_pid_for_test, 'path': b'pathB', 'interface_number': 0, 'usage_page': 0x0000, 'usage': 0x0000, 'name': 'B_PID_User_IF0'}

        target_pid_for_a = pid_for_sort_tests # Default
        # Select a PID for dev_a_exact that is in TARGET_PIDS but ideally not ARCTIS_NOVA_7_USER_PID
        # to distinguish it from dev_b, unless TARGET_PIDS only has ARCTIS_NOVA_7_USER_PID.
        if len(TARGET_PIDS) > 1:
            for pid_val in TARGET_PIDS:
                if pid_val != user_pid_for_test:
                    target_pid_for_a = pid_val
                    break
        # If all PIDs in TARGET_PIDS are user_pid_for_test, then target_pid_for_a will be user_pid_for_test.

        dev_a_exact = {**base_attrs, 'product_id': target_pid_for_a, 'path': b'pathA',
                       'interface_number': app_config.HID_REPORT_INTERFACE, # Should be 3
                       'usage_page': app_config.HID_REPORT_USAGE_PAGE,     # Should be 0xffc0
                       'usage': app_config.HID_REPORT_USAGE_ID,            # Should be 0x0001
                       'name': 'A_Exact'}

        # Device F: Another default priority device to check stability (should come after E if E was first)
        dev_f_default_stable = {**base_attrs, 'product_id': pid_for_sort_tests, 'path': b'pathF', 'interface_number': 2, 'usage_page': 0x0001, 'usage': 0x0001, 'name': 'F_DefaultStable'}


        # Intentionally unsorted list
        devices_to_sort = [dev_e_default, dev_d_usage_page, dev_c_interface3, dev_b_pid2202_if0, dev_a_exact, dev_f_default_stable]

        # Expected order after sorting (lowest sort key value first)
        expected_order = [dev_a_exact, dev_b_pid2202_if0, dev_c_interface3, dev_d_usage_page, dev_e_default, dev_f_default_stable]

        # Ensure no mutation of the input list if the method sorts in-place then returns (it does)
        sorted_devices = self.service._sort_hid_devices(list(devices_to_sort)) # Pass a copy

        # Assert based on the 'name' field for simplicity, assuming paths or other fields could be used too
        self.assertEqual([d.get('name') for d in sorted_devices], [d.get('name') for d in expected_order])


class TestHeadsetServiceStatusParsingHelpers(unittest.TestCase):
    def setUp(self):
        # Patch _connect_hid_device to prevent it running during HeadsetService instantiation
        self.connect_patcher = patch.object(HeadsetService, '_connect_hid_device', return_value=None)
        self.mock_connect_hid_in_init = self.connect_patcher.start()
        self.service = HeadsetService()

    def tearDown(self):
        self.connect_patcher.stop()

    def _create_mock_response_data(self, status_byte_val: int,
                                 level_byte_val: int = 0x00,
                                 game_byte_val: int = 0,
                                 chat_byte_val: int = 0) -> bytes:
        """Helper to create mock response_data byte array for status, battery, and chatmix."""
        data = [0] * app_config.HID_INPUT_REPORT_LENGTH_STATUS

        if app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE < len(data):
            data[app_config.HID_RES_STATUS_BATTERY_STATUS_BYTE] = status_byte_val
        else:
            raise IndexError("HID_RES_STATUS_BATTERY_STATUS_BYTE out of bounds.")

        if app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE < len(data):
            data[app_config.HID_RES_STATUS_BATTERY_LEVEL_BYTE] = level_byte_val
        else:
            raise IndexError("HID_RES_STATUS_BATTERY_LEVEL_BYTE out of bounds.")

        if app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE < len(data):
            data[app_config.HID_RES_STATUS_CHATMIX_GAME_BYTE] = game_byte_val
        else:
            raise IndexError("HID_RES_STATUS_CHATMIX_GAME_BYTE out of bounds.")

        if app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE < len(data):
            data[app_config.HID_RES_STATUS_CHATMIX_CHAT_BYTE] = chat_byte_val
        else:
            raise IndexError("HID_RES_STATUS_CHATMIX_CHAT_BYTE out of bounds.")

        return bytes(data)

    # Tests for _determine_headset_online_status (existing)
    def test_determine_headset_online_status_offline(self):
        # Status byte 0x00 indicates offline
        response_data_offline = self._create_mock_response_data(0x00)
        self.assertFalse(self.service._determine_headset_online_status(response_data_offline))

    def test_determine_headset_online_status_online_charging(self):
        # Status byte 0x01 indicates charging (which implies online)
        response_data_online_charging = self._create_mock_response_data(0x01)
        self.assertTrue(self.service._determine_headset_online_status(response_data_online_charging))

    def test_determine_headset_online_status_online_not_charging(self):
        # Status byte 0x02 (or any non-zero other than 0x01) indicates online but not charging
        response_data_online_not_charging = self._create_mock_response_data(0x02)
        self.assertTrue(self.service._determine_headset_online_status(response_data_online_not_charging))

        response_data_online_other = self._create_mock_response_data(status_byte_val=0x03) # Example other online status
        self.assertTrue(self.service._determine_headset_online_status(response_data_online_other))

    # Tests for _parse_battery_info (new)
    def test_parse_battery_info_offline(self):
        # For is_online=False, byte values shouldn't matter for the output.
        # Using arbitrary valid byte values for completeness.
        response_data = self._create_mock_response_data(status_byte_val=0x00, level_byte_val=0x02)
        expected = {"battery_percent": None, "battery_charging": None}
        self.assertEqual(self.service._parse_battery_info(response_data, is_online=False), expected)

    def test_parse_battery_info_online_levels(self):
        test_cases = [
            (0x00, 0), (0x01, 25), (0x02, 50), (0x03, 75), (0x04, 100)
        ]
        # Assuming status byte 0x02 means "online, not charging" for these level tests
        for level_byte, expected_percent in test_cases:
            with self.subTest(level_byte=level_byte):
                response_data = self._create_mock_response_data(status_byte_val=0x02, level_byte_val=level_byte)
                # is_online=True, battery_charging should be False based on status_byte_val=0x02
                expected = {"battery_percent": expected_percent, "battery_charging": False}
                self.assertEqual(self.service._parse_battery_info(response_data, is_online=True), expected)

    @patch('headsetcontrol_tray.headset_service.logger')
    def test_parse_battery_info_online_level_unknown(self, mock_logger):
        response_data = self._create_mock_response_data(status_byte_val=0x02, level_byte_val=0x05) # Unknown level
        expected = {"battery_percent": None, "battery_charging": False} # Charging is False due to status_byte=0x02
        self.assertEqual(self.service._parse_battery_info(response_data, is_online=True), expected)
        mock_logger.warning.assert_called_with("_parse_battery_info: Unknown raw battery level: 5")

    def test_parse_battery_info_online_charging_true(self):
        # Level 0x02 (50%) and status 0x01 (charging)
        response_data = self._create_mock_response_data(status_byte_val=0x01, level_byte_val=0x02)
        expected = {"battery_percent": 50, "battery_charging": True}
        self.assertEqual(self.service._parse_battery_info(response_data, is_online=True), expected)

    def test_parse_battery_info_online_charging_false(self):
        # Level 0x03 (75%) and status 0x02 (online, not charging)
        response_data = self._create_mock_response_data(status_byte_val=0x02, level_byte_val=0x03)
        expected = {"battery_percent": 75, "battery_charging": False}
        self.assertEqual(self.service._parse_battery_info(response_data, is_online=True), expected)

        # Test with another non-0x01 "online" status byte, e.g. 0x03 (if it means online & not charging)
        # The _parse_battery_info method interprets any status_byte != 0x01 as not charging when is_online=True
        response_data_other_online = self._create_mock_response_data(status_byte_val=0x03, level_byte_val=0x04) # 100%
        expected_other_online = {"battery_percent": 100, "battery_charging": False}
        self.assertEqual(self.service._parse_battery_info(response_data_other_online, is_online=True), expected_other_online)

    # Tests for _parse_chatmix_info (new)
    def test_parse_chatmix_info_offline(self):
        # For is_online=False, byte values shouldn't matter for the output.
        response_data = self._create_mock_response_data(status_byte_val=0x00, game_byte_val=50, chat_byte_val=50)
        self.assertIsNone(self.service._parse_chatmix_info(response_data, is_online=False))

    def test_parse_chatmix_info_online_various_values(self):
        # Formula: mapped_game = int((raw_game_clamped / 100.0) * 64.0)
        #          mapped_chat = int((raw_chat_clamped / 100.0) * -64.0)
        #          chatmix_value = 64 - (mapped_chat + mapped_game)
        #          clamped to 0-128
        test_cases = [
            # (game_raw, chat_raw, expected_chatmix_value)
            # Values for game_byte_val and chat_byte_val must be in range(0, 256) for bytes() conversion.
            # The method under test (_parse_chatmix_info) clamps these to 0-100 internally.
            (100, 0, 0),    # Full Game
            (0, 100, 128),  # Full Chat
            (50, 50, 64),   # Balanced
            (0, 0, 64),     # Centered (both game/chat at 0)
            (75, 25, 32),   # More Game
            (25, 75, 96),   # More Chat
            # Test clamping of raw values (method clamps to 0-100)
            # Provide valid byte values (0-255) that are outside 0-100 logical range for game/chat.
            (150, 0, 0),    # Game > 100 (will be clamped to 100 by SUT)
            (0, 150, 128),  # Chat > 100 (will be clamped to 100 by SUT)
            # Negative values cannot be directly in bytes; test with 0 for already clamped inputs.
            # The method's internal clamping from negative to 0 is tested by providing 0.
            # (0, 0, 64) already tests game=0, chat=0.
            # To test if SUT would clamp e.g. -50 to 0 for game, and chat=0:
            # expected is mapped_game=0, mapped_chat=0 -> chatmix = 64.
            # This is already covered by (0,0,64).
            # Test final clamping to 0-128 (though formula seems to naturally stay in this range if inputs are 0-100)
            # The formula itself: 64 - ( (c/100*-64) + (g/100*64) )
            # If g=100, c=100: 64 - (-64 + 64) = 64. This is already a test case.
        ]

        for game, chat, expected_val in test_cases:
            with self.subTest(game=game, chat=chat):
                # Using status_byte_val=0x02 (online, not charging) as a default online state
                response_data = self._create_mock_response_data(status_byte_val=0x02, game_byte_val=game, chat_byte_val=chat)
                self.assertEqual(self.service._parse_chatmix_info(response_data, is_online=True), expected_val)


if __name__ == "__main__":
    unittest.main()
