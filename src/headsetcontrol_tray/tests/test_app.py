import os
import subprocess  # For subprocess.CompletedProcess
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

# Ensure the application modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtWidgets import QApplication, QMessageBox

# Modules to be tested or mocked
try:
    from headsetcontrol_tray.app import SteelSeriesTrayApp
except ImportError as e:
    print(f"ImportError in test_app.py: {e}")
    raise


class TestSteelSeriesTrayAppUdevDialog(unittest.TestCase):

    def setUp(self):
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

        self.sample_details = {
            "temp_file_path": "/tmp/test_rules_sample.txt",
            "final_file_path": "/etc/udev/rules.d/99-sample.rules",
            "rule_filename": "99-sample.rules",
        }

        current_script_dir = os.path.dirname(os.path.abspath(sys.modules["headsetcontrol_tray.app"].__file__))
        repo_root = os.path.abspath(os.path.join(current_script_dir, ".."))
        self.expected_helper_script_path = os.path.join(repo_root, "scripts", "install-udev-rules.sh")

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    def test_initial_dialog_shown_when_details_present(self, MockHeadsetService, MockQMessageBoxClass, MockSystemTrayIcon):
        mock_service_instance = MockHeadsetService.return_value
        # Simulate that HeadsetService failed to connect and thus populated udev_setup_details
        mock_service_instance.udev_setup_details = self.sample_details
        # is_device_connected would likely be false if udev_setup_details is populated due to connection failure
        mock_service_instance.is_device_connected = Mock(return_value=False)
        mock_service_instance.close = Mock()

        mock_dialog_instance = MockQMessageBoxClass.return_value

        # close_button_mock was unused
        added_buttons_initial = []
        def side_effect_add_button_initial(text_or_button, role=None):
            button = MagicMock(spec=QMessageBox.StandardButton)
            if isinstance(text_or_button, QMessageBox.StandardButton):
                 button.standard_button_enum = text_or_button
            else:
                button.text = text_or_button
            added_buttons_initial.append({"button": button, "role": role, "text_or_enum": text_or_button})
            return button
        mock_dialog_instance.addButton.side_effect = side_effect_add_button_initial

        def set_clicked_button_to_close_equivalent(*args, **kwargs):
            found_close_button = None
            for b_info in added_buttons_initial:
                if b_info.get("text_or_enum") == QMessageBox.Close:
                    found_close_button = b_info["button"]
                    break
            if not found_close_button:
                 found_close_button = MagicMock(spec=QMessageBox.StandardButton)
            mock_dialog_instance.clickedButton.return_value = found_close_button
        mock_dialog_instance.exec.side_effect = set_clicked_button_to_close_equivalent

        SteelSeriesTrayApp() # Constructor called for side effects

        MockQMessageBoxClass.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()
        mock_dialog_instance.setWindowTitle.assert_called_with("Headset Permissions Setup Required")
        # Updated assertion for the main text
        mock_dialog_instance.setText.assert_called_with(
            "Could not connect to your SteelSeries headset. This may be due to missing udev permissions (udev rules).",
        )

        informative_text_call_args = mock_dialog_instance.setInformativeText.call_args[0][0]
        self.assertIn("To resolve this, you can use the 'Install Automatically' button", informative_text_call_args)
        self.assertIn(self.sample_details["temp_file_path"], informative_text_call_args)
        self.assertNotIn("Show Manual Instructions Only", informative_text_call_args)


    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    def test_initial_dialog_not_shown_when_details_absent(self, MockHeadsetService, MockQMessageBoxClass, MockSystemTrayIcon):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = None
        mock_service_instance.is_device_connected = Mock(return_value=True) # Or False, shouldn't matter if details are None
        mock_service_instance.close = Mock()

        SteelSeriesTrayApp() # Constructor called for side effects
        MockQMessageBoxClass.assert_not_called()

    def run_pkexec_test_flow(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon,
                             pkexec_returncode, pkexec_stdout, pkexec_stderr,
                             expected_icon, expected_title, expected_text, expected_informative_text_contains):
        mock_service_instance = MockHeadsetService.return_value
        # Simulate that HeadsetService failed to connect and thus populated udev_setup_details
        mock_service_instance.udev_setup_details = self.sample_details
        mock_service_instance.is_device_connected = Mock(return_value=False) # Consistent with udev_setup_details being present
        mock_service_instance.close = Mock()

        mock_os_path_exists.return_value = True

        mock_initial_dialog_instance = MockQMessageBoxClass.return_value

        auto_button_mock = MagicMock(spec=QMessageBox.StandardButton)
        # added_buttons was unused
        def side_effect_add_button(text_or_button, role=None):
            button = MagicMock(spec=QMessageBox.StandardButton)
            button.text = str(text_or_button)
            if role == QMessageBox.AcceptRole:
                nonlocal auto_button_mock
                auto_button_mock = button
            return button

        mock_initial_dialog_instance.addButton.side_effect = side_effect_add_button
        mock_initial_dialog_instance.clickedButton.return_value = auto_button_mock

        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["pkexec", self.expected_helper_script_path, self.sample_details["temp_file_path"], self.sample_details["final_file_path"]],
            returncode=pkexec_returncode, stdout=pkexec_stdout, stderr=pkexec_stderr,
        )

        MockQMessageBoxClass.reset_mock()
        mock_feedback_dialog_instance = MockQMessageBoxClass.return_value

        SteelSeriesTrayApp() # Constructor called for side effects

        mock_subprocess_run.assert_called_once()
        cmd_called = mock_subprocess_run.call_args[0][0]
        self.assertEqual(cmd_called[0], "pkexec")
        self.assertEqual(cmd_called[1], self.expected_helper_script_path)
        self.assertEqual(cmd_called[2], self.sample_details["temp_file_path"])
        self.assertEqual(cmd_called[3], self.sample_details["final_file_path"])

        MockQMessageBoxClass.assert_called_once()
        mock_feedback_dialog_instance.setIcon.assert_called_with(expected_icon)
        mock_feedback_dialog_instance.setWindowTitle.assert_called_with(expected_title)
        mock_feedback_dialog_instance.setText.assert_called_with(expected_text)
        if isinstance(expected_informative_text_contains, str):
             self.assertIn(expected_informative_text_contains, mock_feedback_dialog_instance.setInformativeText.call_args[0][0])
        else:
            for item in expected_informative_text_contains:
                 self.assertIn(item, mock_feedback_dialog_instance.setInformativeText.call_args[0][0])
        mock_feedback_dialog_instance.exec.assert_called_once()

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.os.path.exists")
    @patch("headsetcontrol_tray.app.subprocess.run")
    def test_pkexec_flow_success_and_feedback(self, m_run, m_exists, MQMsgBox, MHsvc, MSTIcon):
        self.run_pkexec_test_flow(m_run, m_exists, MQMsgBox, MHsvc, MSTIcon,
                                  pkexec_returncode=0, pkexec_stdout="Success", pkexec_stderr="",
                                  expected_icon=QMessageBox.Information,
                                  expected_title="Success",
                                  expected_text="Udev rules installed successfully.",
                                  expected_informative_text_contains="Please replug your headset")

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.os.path.exists")
    @patch("headsetcontrol_tray.app.subprocess.run")
    def test_pkexec_flow_user_cancelled(self, m_run, m_exists, MQMsgBox, MHsvc, MSTIcon):
        self.run_pkexec_test_flow(m_run, m_exists, MQMsgBox, MHsvc, MSTIcon,
                                  pkexec_returncode=126, pkexec_stdout="", pkexec_stderr="User cancelled",
                                  expected_icon=QMessageBox.Warning,
                                  expected_title="Authentication Cancelled",
                                  expected_text="Udev rule installation was cancelled.",
                                  expected_informative_text_contains="Authentication was not provided")

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.os.path.exists")
    @patch("headsetcontrol_tray.app.subprocess.run")
    def test_pkexec_flow_auth_error(self, m_run, m_exists, MQMsgBox, MHsvc, MSTIcon):
        stderr_msg = "Authorization failed (polkit)"
        self.run_pkexec_test_flow(m_run, m_exists, MQMsgBox, MHsvc, MSTIcon,
                                  pkexec_returncode=127, pkexec_stdout="", pkexec_stderr=stderr_msg,
                                  expected_icon=QMessageBox.Critical,
                                  expected_title="Authorization Error",
                                  expected_text="Failed to install udev rules due to an authorization error.",
                                  expected_informative_text_contains=[stderr_msg, "Please ensure you have privileges"])

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.os.path.exists")
    @patch("headsetcontrol_tray.app.subprocess.run")
    def test_pkexec_flow_script_error(self, m_run, m_exists, MQMsgBox, MHsvc, MSTIcon):
        stderr_msg = "Helper script failed: cp error"
        self.run_pkexec_test_flow(m_run, m_exists, MQMsgBox, MHsvc, MSTIcon,
                                  pkexec_returncode=4, pkexec_stdout="", pkexec_stderr=stderr_msg,
                                  expected_icon=QMessageBox.Critical,
                                  expected_title="Installation Failed",
                                  expected_text="The udev rule installation script failed.",
                                  expected_informative_text_contains=[f"Error (code 4): {stderr_msg}", "Please check the output"])

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.os.path.exists")
    @patch("headsetcontrol_tray.app.subprocess.run")
    def test_pkexec_helper_script_not_found(self, mock_subprocess_run, mock_os_path_exists, MockQMessageBoxClass, MockHeadsetService, MockSystemTrayIcon):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = self.sample_details
        mock_service_instance.is_device_connected = Mock(return_value=False) # Consistent with details being present
        mock_service_instance.close = Mock()

        mock_os_path_exists.return_value = False

        mock_initial_dialog_instance = MockQMessageBoxClass.return_value
        auto_button_mock = MagicMock(spec=QMessageBox.StandardButton)
        def side_effect_add_button_script_not_found(text_or_button, role=None):
            button = MagicMock(spec=QMessageBox.StandardButton)
            if role == QMessageBox.AcceptRole:
                nonlocal auto_button_mock
                auto_button_mock = button
            return button
        mock_initial_dialog_instance.addButton.side_effect = side_effect_add_button_script_not_found
        mock_initial_dialog_instance.clickedButton.return_value = auto_button_mock

        MockQMessageBoxClass.reset_mock()

        SteelSeriesTrayApp() # Constructor called for side effects

        mock_subprocess_run.assert_not_called()
        MockQMessageBoxClass.critical.assert_called_once()
        args, _ = MockQMessageBoxClass.critical.call_args
        self.assertEqual(args[0], None)
        self.assertIn("Error", args[1])
        self.assertIn("Installation script not found", args[2])
        self.assertIn(self.expected_helper_script_path, args[2])


if __name__ == "__main__":
    unittest.main()
