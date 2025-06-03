import unittest
from unittest import mock
from unittest.mock import Mock, patch, mock_open
import os
import tempfile # Will be needed for testing _create_udev_rules

# Attempt to import from the correct location
try:
    from headsetcontrol_tray.headset_service import HeadsetService, UDEV_RULE_CONTENT, UDEV_RULE_FILENAME
    from headsetcontrol_tray import app_config # To allow mocking app_config constants if needed
except ImportError:
    # Fallback for different execution context (e.g. if tests are run directly from tests folder)
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from headset_service import HeadsetService, UDEV_RULE_CONTENT, UDEV_RULE_FILENAME
    import app_config


class TestHeadsetServiceUdevRules(unittest.TestCase):

    def setUp(self):
        """
        Set up for test methods.
        This will mock the __init__ of HeadsetService to prevent actual HID connection attempts.
        """
        # Patch the __init__ method of HeadsetService to do nothing
        self.mock_headset_service_init = patch('headsetcontrol_tray.headset_service.HeadsetService.__init__', return_value=None)
        self.mock_headset_service_init.start()
        self.service = HeadsetService() # Now __init__ is mocked

        # If app_config constants like STEELSERIES_VID or TARGET_PIDS are needed directly by
        # the global UDEV_RULE_CONTENT, and you want to test with specific PIDs for example,
        # you might need to mock them here or ensure they are loaded as expected.
        # For now, we'll assume UDEV_RULE_CONTENT is correctly formed by the module upon import.

    def tearDown(self):
        self.mock_headset_service_init.stop()

    # --- Tests for _check_udev_rules ---

    @patch('os.path.exists')
    def test_check_rules_file_not_exists(self, mock_exists):
        mock_exists.return_value = False
        self.assertFalse(self.service._check_udev_rules())
        mock_exists.assert_called_once_with(os.path.join("/etc/udev/rules.d/", UDEV_RULE_FILENAME))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=UDEV_RULE_CONTENT)
    def test_check_rules_file_exists_content_matches(self, mock_file_open, mock_exists):
        self.assertTrue(self.service._check_udev_rules())

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data="SOME OTHER RULE CONTENT")
    def test_check_rules_file_exists_content_mismatch(self, mock_file_open, mock_exists):
        self.assertFalse(self.service._check_udev_rules())

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data="")
    def test_check_rules_file_exists_empty_content(self, mock_file_open, mock_exists):
        # UDEV_RULE_CONTENT is expected to be non-empty.
        # If UDEV_RULE_CONTENT could be empty, this test might need adjustment
        # or the function's behavior for empty content defined.
        if not UDEV_RULE_CONTENT.strip(): # Edge case if UDEV_RULE_CONTENT itself is empty
            self.assertTrue(self.service._check_udev_rules())
        else:
            self.assertFalse(self.service._check_udev_rules())

    @patch('os.path.exists', return_value=True)
    def test_check_rules_file_exists_content_matches_unordered(self, mock_exists):
        # Assumes UDEV_RULE_CONTENT might have multiple lines
        lines = UDEV_RULE_CONTENT.strip().split('\n')
        if len(lines) > 1:
            import random
            shuffled_lines = lines[:]
            random.shuffle(shuffled_lines)
            shuffled_content = "\n".join(shuffled_lines) + "\n" # Ensure trailing newline like typical files

            with patch('builtins.open', new_callable=mock_open, read_data=shuffled_content):
                self.assertTrue(self.service._check_udev_rules())
        else:
            # If only one line, this test is same as content_matches
            with patch('builtins.open', new_callable=mock_open, read_data=UDEV_RULE_CONTENT):
                self.assertTrue(self.service._check_udev_rules())


    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=IOError("Test IOError"))
    def test_check_rules_io_error_on_read(self, mock_file_open_ioerror, mock_exists_ioerror):
        self.assertFalse(self.service._check_udev_rules())

    # --- Tests for _create_udev_rules ---

    @patch('headsetcontrol_tray.headset_service.logger')
    @patch('tempfile.NamedTemporaryFile')
    def test_create_rules_success(self, mock_named_temp_file, mock_logger):
        # Configure the mock for NamedTemporaryFile
        mock_temp_fd = Mock()
        mock_temp_fd.name = "/tmp/fake_temp_rule_file.rules"
        mock_temp_fd_context_manager = mock_named_temp_file.return_value.__enter__.return_value
        mock_temp_fd_context_manager.name = "/tmp/fake_temp_rule_file.rules"
        mock_temp_fd_context_manager.write = Mock()

        self.assertTrue(self.service._create_udev_rules())

        # Check if write was called with UDEV_RULE_CONTENT
        mock_temp_fd_context_manager.write.assert_called_once_with(UDEV_RULE_CONTENT + "\n")

        # Check logger calls for instructions
        # This checks if specific parts of the instructions are logged.
        # It's more robust to check call_args_list for specific messages.
        # For simplicity, checking if logger.info was called multiple times.
        self.assertGreaterEqual(mock_logger.info.call_count, 4) # Initial log, path, 3 instruction lines, temp file deletion note

        # Example of checking a specific log message
        expected_log_substr_copy = f"sudo cp \"{mock_temp_fd_context_manager.name}\""
        self.assertTrue(any(expected_log_substr_copy in call_args[0][0] for call_args in mock_logger.info.call_args_list if call_args[0]))


    @patch('headsetcontrol_tray.headset_service.logger')
    @patch('tempfile.NamedTemporaryFile')
    def test_create_rules_io_error_on_write(self, mock_named_temp_file_ioerror, mock_logger_ioerror):
        mock_temp_fd_context_manager = mock_named_temp_file_ioerror.return_value.__enter__.return_value
        mock_temp_fd_context_manager.name = "/tmp/fake_temp_rule_file_ioerror.rules"
        mock_temp_fd_context_manager.write.side_effect = IOError("Failed to write temp file")

        self.assertFalse(self.service._create_udev_rules())
        mock_logger_ioerror.error.assert_called_with(mock.ANY) # Check that an error was logged


if __name__ == '__main__':
    unittest.main()
