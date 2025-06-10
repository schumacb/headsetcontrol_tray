import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

# Ensure src is in path for imports
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")),
)

# NUM_EQ_BANDS is not used here, but if other constants from headset_status were needed,
# they could be imported. For now, only app_config for logger name.
from headsetcontrol_tray.udev_manager import (
    UDEV_RULE_CONTENT,
    UDEV_RULE_FILENAME,
    UDEVManager,
)


class TestUDEVManager(unittest.TestCase):  # Removed class decorator
    def setUp(self):  # Signature changed
        self.logger_patcher = patch(
            f"{UDEVManager.__module__}.logger",
            new_callable=MagicMock,
        )
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        self.manager = UDEVManager()
        # self.mock_logger is now available

    @patch("tempfile.NamedTemporaryFile")
    def test_create_rules_interactive_success(
        self,
        mock_named_temp_file,
    ):  # Removed mock_logger_passed_in_test_method_ignored
        mock_temp_file_context = MagicMock()
        mock_temp_file_context.name = "/tmp/fake_headsetcontrol_abcdef.rules"
        mock_temp_file_context.write = MagicMock()

        # Configure the context manager behavior for NamedTemporaryFile
        mock_named_temp_file.return_value.__enter__.return_value = (
            mock_temp_file_context
        )

        result = self.manager.create_rules_interactive()

        self.assertTrue(result)
        mock_named_temp_file.assert_called_once_with(
            mode="w",
            delete=False,
            prefix="headsetcontrol_",
            suffix=".rules",
        )
        mock_temp_file_context.write.assert_called_once_with(UDEV_RULE_CONTENT + "\n")

        expected_details = {
            "temp_file_path": "/tmp/fake_headsetcontrol_abcdef.rules",
            "final_file_path": f"/etc/udev/rules.d/{UDEV_RULE_FILENAME}",
            "rule_filename": UDEV_RULE_FILENAME,
            "rule_content": UDEV_RULE_CONTENT,
        }
        self.assertEqual(self.manager.last_udev_setup_details, expected_details)

        # Check for specific log messages
        self.mock_logger.info.assert_any_call(
            "Successfully wrote udev rule content to temporary file: %s",
            expected_details["temp_file_path"],
        )

        # Verify key log messages using call objects
        expected_action_required_log = call(
            "ACTION REQUIRED: To complete headset setup, please run the "
            "following commands:",
        )
        self.assertIn(
            expected_action_required_log,
            self.mock_logger.info.call_args_list,
        )

        expected_cp_log = call(
            '1. Copy the rule file: sudo cp "%s" "%s"',
            expected_details["temp_file_path"],
            expected_details["final_file_path"],
        )
        self.assertIn(expected_cp_log, self.mock_logger.info.call_args_list)

        expected_reload_log = call(
            "2. Reload udev rules: sudo udevadm control --reload-rules && "
            "sudo udevadm trigger",
        )
        self.assertIn(expected_reload_log, self.mock_logger.info.call_args_list)

        expected_replug_log = call(
            "3. Replug your SteelSeries headset if it was connected.",
        )
        self.assertIn(expected_replug_log, self.mock_logger.info.call_args_list)

    @patch("tempfile.NamedTemporaryFile")
    def test_create_rules_interactive_os_error_on_write(
        self,
        mock_named_temp_file,
    ):  # Removed mock_logger_passed_in_test_method_ignored
        mock_temp_file_context = MagicMock()
        mock_temp_file_context.name = "/tmp/fake_headsetcontrol_oserror.rules"
        mock_temp_file_context.write.side_effect = OSError("Disk full")

        mock_named_temp_file.return_value.__enter__.return_value = (
            mock_temp_file_context
        )

        result = self.manager.create_rules_interactive()

        self.assertFalse(result)
        self.assertIsNone(self.manager.last_udev_setup_details)
        # Updated to check for logger.exception and the specific message format
        self.mock_logger.exception.assert_called_once_with(
            "Could not write temporary udev rule file",  # The original code logs the exception object as part of the message if using %s, e
        )

    @patch("tempfile.NamedTemporaryFile")
    def test_create_rules_interactive_unexpected_error(
        self,
        mock_named_temp_file,
    ):  # Removed mock_logger_passed_in_test_method_ignored
        # Simulate an error other than OSError during the tempfile operation
        mock_named_temp_file.side_effect = Exception("Unexpected tempfile system error")

        result = self.manager.create_rules_interactive()

        self.assertFalse(result)
        self.assertIsNone(self.manager.last_udev_setup_details)
        # Updated to check for logger.exception and the specific message format
        self.mock_logger.exception.assert_called_once_with(
            "An unexpected error occurred during temporary udev rule file creation",
        )

    def test_get_last_udev_setup_details_initially_none(
        self,
    ):  # Removed mock_logger_passed_in_test_method_ignored
        self.assertIsNone(self.manager.get_last_udev_setup_details())

    @patch(
        "tempfile.NamedTemporaryFile",
    )  # Still need to mock this even if we just set details manually
    def test_get_last_udev_setup_details_returns_set_details(
        self,
        mock_temp_file_unused,
    ):  # Removed mock_logger_passed_in_test_method_ignored
        dummy_details = {
            "temp_file_path": "/tmp/dummy",
            "final_file_path": "/etc/dummy.rules",
        }
        # Manually set the details for this test after manager initialization
        self.manager.last_udev_setup_details = dummy_details

        retrieved_details = self.manager.get_last_udev_setup_details()
        self.assertEqual(retrieved_details, dummy_details)


if __name__ == "__main__":
    unittest.main()
