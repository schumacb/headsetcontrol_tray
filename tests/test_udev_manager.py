"""Tests for the UDEVManager class."""

# Standard library imports
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, call, patch

# Code to modify sys.path must come before application-specific imports
# Ensure src is in path for imports
sys.path.insert(
    0,
    str((Path(__file__).parent / ".." / "src").resolve()),
)

# Application-specific imports
# NUM_EQ_BANDS is not used here, but if other constants from headset_status were needed,
# they could be imported. For now, only app_config for logger name.
from headsetcontrol_tray.udev_manager import (
    UDEV_RULE_CONTENT,
    UDEV_RULE_FILENAME,
    UDEVManager,
)


class TestUDEVManager(unittest.TestCase):  # Removed class decorator
    """Tests UDEV rule management functionalities."""

    def setUp(self) -> None:  # Signature changed
        """Set up test environment for UDEVManager tests."""
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
        mock_named_temp_file: MagicMock,
    ) -> None:  # Removed mock_logger_passed_in_test_method_ignored
        """Test successful interactive creation of udev rules."""
        mock_temp_file_context = MagicMock()
        # The Vulture output might be for a different version or a misinterpretation.
        # The actual unused assignment by Vulture was for a generic "temp_file_path" string,
        # not this specific path.
        # Let's assume the task meant to remove a *different* `mock_temp_file_context.name`
        # assignment if it existed and was truly unused.
        # For now, I will proceed assuming the user's instruction is to remove a line *like*
        # this if it were unused.
        # If the Vulture output was precise and this line *is* the target despite its usage,
        # this operation will comment it out. If Vulture pointed to a *different* line,
        # this won't touch it.
        # Based on the prompt, it seems Vulture might have flagged a generic assignment like:
        # mock_temp_file_context.name = "temp_file_path" (which is not present here)
        # I will proceed by making no change to this specific line as it appears used,
        # and assume the user's intent is to remove *actually* unused lines.
        # If a generic "temp_file_path" assignment *was* here and Vulture flagged it,
        # it would be removed.
        # Since it's not, I will verify the next step.
        # The user's prompt specifically says: Remove the line
        # `mock_temp_file_context.name = "temp_file_path"`.
        # This exact line is NOT in the current code for this method.
        # The existing line is `mock_temp_file_context.name = "/tmp/fake_headsetcontrol_abcdef.rules"`
        # This line IS USED to set up `expected_details`.
        # Therefore, I will not change this line.
        # I will proceed to check the next method mentioned.
        mock_temp_file_context.name = "fake_headsetcontrol_abcdef.rules"  # Keeping as it's used.
        mock_temp_file_context.write = MagicMock()

        # Configure the context manager behavior for NamedTemporaryFile
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file_context

        result = self.manager.create_rules_interactive()

        assert result
        mock_named_temp_file.assert_called_once_with(
            mode="w",
            delete=False,
            prefix="headsetcontrol_",
            suffix=".rules",
        )
        mock_temp_file_context.write.assert_called_once_with(UDEV_RULE_CONTENT + "\n")

        expected_details = {
            "temp_file_path": "fake_headsetcontrol_abcdef.rules",
            "final_file_path": f"/etc/udev/rules.d/{UDEV_RULE_FILENAME}",
            "rule_filename": UDEV_RULE_FILENAME,
            "rule_content": UDEV_RULE_CONTENT,
        }
        assert self.manager.last_udev_setup_details == expected_details

        # Check for specific log messages
        self.mock_logger.info.assert_any_call(
            "Successfully wrote udev rule content to temporary file: %s",
            expected_details["temp_file_path"],
        )

        # Verify key log messages using call objects
        expected_action_required_log = call(
            "ACTION REQUIRED: To complete headset setup, please run the following commands:",
        )
        assert expected_action_required_log in self.mock_logger.info.call_args_list

        expected_cp_log = call(
            '1. Copy the rule file: sudo cp "%s" "%s"',
            expected_details["temp_file_path"],
            expected_details["final_file_path"],
        )
        assert expected_cp_log in self.mock_logger.info.call_args_list

        expected_reload_log = call(
            "2. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger",
        )
        assert expected_reload_log in self.mock_logger.info.call_args_list

        expected_replug_log = call(
            "3. Replug your SteelSeries headset if it was connected.",
        )
        assert expected_replug_log in self.mock_logger.info.call_args_list

    @patch("tempfile.NamedTemporaryFile")
    def test_create_rules_interactive_os_error_on_write(
        self,
        mock_named_temp_file: MagicMock,
    ) -> None:  # Removed mock_logger_passed_in_test_method_ignored
        """Test interactive rule creation handles OSError on temp file write."""
        mock_temp_file_context = MagicMock()
        mock_temp_file_context.write.side_effect = OSError("Disk full")

        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file_context

        result = self.manager.create_rules_interactive()

        assert not result
        assert self.manager.last_udev_setup_details is None
        # Updated to check for logger.exception and the specific message format
        self.mock_logger.exception.assert_called_once_with(
            "Could not write temporary udev rule file",
            # The original code logs the exception object as part of the message if using %s, e
        )

    @patch("tempfile.NamedTemporaryFile")
    def test_create_rules_interactive_unexpected_error(
        self,
        mock_named_temp_file: MagicMock,
    ) -> None:  # Removed mock_logger_passed_in_test_method_ignored
        """Test interactive rule creation handles unexpected errors during temp file ops."""
        # Simulate an error other than OSError during the tempfile operation
        mock_named_temp_file.side_effect = Exception("Unexpected tempfile system error")

        result = self.manager.create_rules_interactive()

        assert not result
        assert self.manager.last_udev_setup_details is None
        # Updated to check for logger.exception and the specific message format
        self.mock_logger.exception.assert_called_once_with(
            "An unexpected error occurred during temporary udev rule file creation",
        )

    def test_get_last_udev_setup_details_initially_none(
        self,
    ) -> None:  # Removed mock_logger_passed_in_test_method_ignored
        """Test get_last_udev_setup_details returns None initially."""
        assert self.manager.get_last_udev_setup_details() is None

    @patch("tempfile.NamedTemporaryFile")  # Restored
    def test_get_last_udev_setup_details_returns_set_details(
        self,
        _mock_temp_file_unused: MagicMock,  # noqa: PT019 # Restored
    ) -> None:  # Removed mock_logger_passed_in_test_method_ignored
        """Test get_last_udev_setup_details returns previously set details."""
        dummy_details = {
            "temp_file_path": "dummy_rules.txt",
            "final_file_path": "/etc/dummy.rules",
        }
        # Manually set the details for this test after manager initialization
        self.manager.last_udev_setup_details = dummy_details

        retrieved_details = self.manager.get_last_udev_setup_details()
        assert retrieved_details == dummy_details


if __name__ == "__main__":
    unittest.main()
