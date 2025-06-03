import unittest
from unittest.mock import patch, Mock, MagicMock
import os
import sys
import subprocess # For subprocess.CompletedProcess

# Ensure the application modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QApplication, QMessageBox

# Modules to be tested or mocked
try:
    from headsetcontrol_tray.app import SteelSeriesTrayApp
    # Import HeadsetService from its original location to mock it where it's defined
    # from headsetcontrol_tray import headset_service as hs_svc_module # Not strictly needed if only mocking via app path
except ImportError as e:
    print(f"ImportError in test_app.py: {e}")
    raise


class TestSteelSeriesTrayAppUdevDialog(unittest.TestCase):

    def setUp(self):
        """Ensure a QApplication instance exists for each test."""
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

        self.sample_details = {
            "temp_file_path": "/tmp/test_rules_sample.txt",
            "final_file_path": "/etc/udev/rules.d/99-sample.rules",
            "rule_filename": "99-sample.rules"
        }

        # Expected path to the helper script based on app.py's location
        current_script_dir = os.path.dirname(os.path.abspath(sys.modules['headsetcontrol_tray.app'].__file__))
        repo_root = os.path.abspath(os.path.join(current_script_dir, ".."))
        self.expected_helper_script_path = os.path.join(repo_root, "scripts", "install-udev-rules.sh")


    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.QMessageBox')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    def test_initial_dialog_shown_when_details_present(self,
                                                 MockHeadsetService,
                                                 MockQMessageBoxClass, # Now mocking the class
                                                 MockSystemTrayIcon):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = self.sample_details
        mock_service_instance.is_device_connected = Mock(return_value=True)
        mock_service_instance.close = Mock()

        # Mock the instance that QMessageBox() will produce
        mock_dialog_instance = MockQMessageBoxClass.return_value
        # Simulate user closing the first dialog without choosing an action for pkexec
        mock_dialog_instance.clickedButton.return_value = dialog.addButton(QMessageBox.Close)


        tray_app_instance = SteelSeriesTrayApp()

        # Check that the dialog was created and shown
        MockQMessageBoxClass.assert_called_once() # Check if QMessageBox() was called
        mock_dialog_instance.exec.assert_called_once() # Check if dialog.exec() was called

        # Verify title and text (illustrative, specific checks depend on how it's set)
        mock_dialog_instance.setWindowTitle.assert_called_with("Headset Permissions Setup Required")
        self.assertIn("Your SteelSeries headset may not work correctly", mock_dialog_instance.setText.call_args[0][0])
        self.assertIn(self.sample_details["temp_file_path"], mock_dialog_instance.setInformativeText.call_args[0][0])


    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.QMessageBox')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    def test_initial_dialog_not_shown_when_details_absent(self,
                                                      MockHeadsetService,
                                                      MockQMessageBoxClass,
                                                      MockSystemTrayIcon):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = None
        mock_service_instance.is_device_connected = Mock(return_value=True)
        mock_service_instance.close = Mock()

        tray_app_instance = SteelSeriesTrayApp()
        MockQMessageBoxClass.assert_not_called()


    def run_pkexec_test_flow(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon, pkexec_returncode, pkexec_stdout, pkexec_stderr, expected_feedback_type):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = self.sample_details
        mock_service_instance.is_device_connected = Mock(return_value=True)
        mock_service_instance.close = Mock()

        mock_os_path_exists.return_value = True # Assume helper script exists

        # Mock the initial dialog
        mock_initial_dialog = MockQMessageBoxClass.return_value

        # Simulate clicking "Install Automatically"
        # We need to make addButton for "Install Automatically" return a specific mock object
        # and then make clickedButton return that same mock object.
        auto_button_mock = MagicMock(spec=QMessageBox.StandardButton) # Or just Mock()

        # Store all buttons added to find the auto_button
        added_buttons = []
        def side_effect_add_button(text, role):
            button = MagicMock(spec=QMessageBox.StandardButton)
            button.text = text # Store text for identification if needed
            added_buttons.append({"button": button, "role": role, "text": text})
            return button

        mock_initial_dialog.addButton.side_effect = side_effect_add_button

        # This will be called after all buttons are added
        def set_clicked_button_auto(*args, **kwargs):
            # Find the auto_button we stored via side_effect
            found_auto_button = None
            for b_info in added_buttons:
                if b_info["role"] == QMessageBox.AcceptRole: # "Install Automatically"
                    found_auto_button = b_info["button"]
                    break
            if not found_auto_button:
                raise Exception("Auto button not added or role mismatch") # Should not happen
            mock_initial_dialog.clickedButton.return_value = found_auto_button

        # Call exec, then immediately set the return for clickedButton
        mock_initial_dialog.exec.side_effect = set_clicked_button_auto

        # Configure subprocess.run mock
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["pkexec", self.expected_helper_script_path, self.sample_details["temp_file_path"], self.sample_details["final_file_path"]],
            returncode=pkexec_returncode,
            stdout=pkexec_stdout,
            stderr=pkexec_stderr
        )

        # Reset call counts for QMessageBox for feedback dialog
        MockQMessageBoxClass.reset_mock() # Reset class mock

        # We need a new instance for the feedback dialog
        mock_feedback_dialog = MockQMessageBoxClass.return_value

        tray_app_instance = SteelSeriesTrayApp()

        mock_subprocess_run.assert_called_once()
        cmd_called = mock_subprocess_run.call_args[0][0]
        self.assertEqual(cmd_called[0], "pkexec")
        self.assertEqual(cmd_called[1], self.expected_helper_script_path)
        self.assertEqual(cmd_called[2], self.sample_details["temp_file_path"])
        self.assertEqual(cmd_called[3], self.sample_details["final_file_path"])

        # Check that the correct type of feedback QMessageBox was shown
        if expected_feedback_type == "information":
            MockQMessageBoxClass.information.assert_called_once()
        elif expected_feedback_type == "warning":
            MockQMessageBoxClass.warning.assert_called_once()
        elif expected_feedback_type == "critical":
            MockQMessageBoxClass.critical.assert_called_once()
        else: # No feedback dialog expected (e.g. if initial dialog was cancelled)
            MockQMessageBoxClass.information.assert_not_called()
            MockQMessageBoxClass.warning.assert_not_called()
            MockQMessageBoxClass.critical.assert_not_called()


    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    @patch('headsetcontrol_tray.app.QMessageBox') # Mock the class
    @patch('headsetcontrol_tray.app.os.path.exists')
    @patch('headsetcontrol_tray.app.subprocess.run')
    def test_pkexec_flow_success_and_feedback(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon):
        self.run_pkexec_test_flow(mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon,
                                  pkexec_returncode=0, pkexec_stdout="Success", pkexec_stderr="",
                                  expected_feedback_type="information")
        # Check specific message content for success
        args, _ = MockQMessageBoxClass.information.call_args
        self.assertIn("Udev rules installed successfully", args[1]) # Title check
        self.assertIn("Please replug your headset", args[2]) # Message check

    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    @patch('headsetcontrol_tray.app.QMessageBox')
    @patch('headsetcontrol_tray.app.os.path.exists')
    @patch('headsetcontrol_tray.app.subprocess.run')
    def test_pkexec_flow_user_cancelled(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon):
        self.run_pkexec_test_flow(mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon,
                                  pkexec_returncode=126, pkexec_stdout="", pkexec_stderr="User cancelled",
                                  expected_feedback_type="warning")
        args, _ = MockQMessageBoxClass.warning.call_args
        self.assertIn("Authentication Cancelled", args[1])
        self.assertIn("Authentication was not provided", args[2])


    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    @patch('headsetcontrol_tray.app.QMessageBox')
    @patch('headsetcontrol_tray.app.os.path.exists')
    @patch('headsetcontrol_tray.app.subprocess.run')
    def test_pkexec_flow_auth_error(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon):
        stderr_msg = "Authorization failed (polkit)"
        self.run_pkexec_test_flow(mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon,
                                  pkexec_returncode=127, pkexec_stdout="", pkexec_stderr=stderr_msg,
                                  expected_feedback_type="critical")
        args, _ = MockQMessageBoxClass.critical.call_args
        self.assertIn("Authorization Error", args[1])
        self.assertIn(stderr_msg, args[2])

    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    @patch('headsetcontrol_tray.app.QMessageBox')
    @patch('headsetcontrol_tray.app.os.path.exists')
    @patch('headsetcontrol_tray.app.subprocess.run')
    def test_pkexec_flow_script_error(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon):
        stderr_msg = "Helper script failed: cp error"
        self.run_pkexec_test_flow(mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon,
                                  pkexec_returncode=4, pkexec_stdout="", pkexec_stderr=stderr_msg,
                                  expected_feedback_type="critical")
        args, _ = MockQMessageBoxClass.critical.call_args
        self.assertIn("Installation Failed", args[1])
        self.assertIn(stderr_msg, args[2])
        self.assertIn("Error (code 4)", args[2])

    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    @patch('headsetcontrol_tray.app.QMessageBox') # Mock the class
    @patch('headsetcontrol_tray.app.os.path.exists')
    @patch('headsetcontrol_tray.app.subprocess.run') # Mock subprocess too
    def test_pkexec_helper_script_not_found(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = self.sample_details
        mock_service_instance.is_device_connected = Mock(return_value=True)
        mock_service_instance.close = Mock()

        mock_os_path_exists.return_value = False # Helper script does NOT exist

        mock_initial_dialog = MockQMessageBoxClass.return_value
        auto_button_mock = MagicMock()
        added_buttons = []
        def side_effect_add_button(text, role):
            button = MagicMock(spec=QMessageBox.StandardButton); button.text = text
            added_buttons.append({"button": button, "role": role, "text": text}); return button
        mock_initial_dialog.addButton.side_effect = side_effect_add_button
        def set_clicked_button_auto(*args, **kwargs):
            found_auto_button = next(b_info["button"] for b_info in added_buttons if b_info["role"] == QMessageBox.AcceptRole)
            mock_initial_dialog.clickedButton.return_value = found_auto_button
        mock_initial_dialog.exec.side_effect = set_clicked_button_auto

        MockQMessageBoxClass.reset_mock() # Reset for the critical dialog check

        tray_app_instance = SteelSeriesTrayApp()

        mock_subprocess_run.assert_not_called() # pkexec should not be called
        MockQMessageBoxClass.critical.assert_called_once()
        args, _ = MockQMessageBoxClass.critical.call_args
        self.assertIn("Installation script not found", args[1])
        self.assertIn(self.expected_helper_script_path, args[2])


if __name__ == '__main__':
    unittest.main()
