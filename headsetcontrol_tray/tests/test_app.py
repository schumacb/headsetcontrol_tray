import os
import subprocess  # For subprocess.CompletedProcess
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

# Ensure the application modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest # Added for @pytest.mark.usefixtures
from PySide6.QtWidgets import QApplication, QMessageBox

# Modules to be tested or mocked
try:
    from headsetcontrol_tray.app import SteelSeriesTrayApp
except ImportError as e:
    print(f"ImportError in test_app.py: {e}")
    raise


# Removed @pytest.mark.usefixtures("qapp")
class TestSteelSeriesTrayAppUdevDialog(unittest.TestCase):
    qapp_for_class = None
    _qapp_created_by_class = False

    @classmethod
    def setUpClass(cls):
        cls.qapp_for_class = QApplication.instance()
        if cls.qapp_for_class is None:
            cls.qapp_for_class = QApplication([]) # Use an empty list for args
            cls._qapp_created_by_class = True
        else:
            cls._qapp_created_by_class = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_qapp_created_by_class", False) and QApplication.instance():
            QApplication.quit()
        # cls.qapp_for_class = None # Optional: clear class reference

    def setUp(self):
        # Use the class-level QApplication instance
        self.qapp_instance = TestSteelSeriesTrayAppUdevDialog.qapp_for_class

        # Patch 'headsetcontrol_tray.app.QApplication' to return the class-level instance
        self.qapplication_patch = patch('headsetcontrol_tray.app.QApplication', return_value=self.qapp_instance)
        self.mock_qapplication_constructor = self.qapplication_patch.start()

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
        mock_service_instance.udev_setup_details = self.sample_details
        mock_service_instance.is_device_connected = Mock(return_value=False)
        mock_service_instance.close = Mock()

        mock_os_path_exists.return_value = True # For these flows, pkexec is attempted, so script must exist

        mock_initial_dialog = MagicMock(spec=QMessageBox)
        mock_feedback_dialog = MagicMock(spec=QMessageBox)
        MockQMessageBoxClass.side_effect = [mock_initial_dialog, mock_feedback_dialog]

        captured_auto_button = [None] # Using a list to allow modification in closure

        def initial_dialog_add_button_side_effect(text_or_button, role=None):
            button_mock = MagicMock(spec=QMessageBox.StandardButton)
            if isinstance(text_or_button, str):
                button_mock.text = text_or_button
            else:
                button_mock.standard_button_enum = text_or_button

            if role == QMessageBox.AcceptRole:
                captured_auto_button[0] = button_mock
                # When the "Install Automatically" button is added by the app,
                # immediately set the mock_initial_dialog's clickedButton behavior.
                mock_initial_dialog.clickedButton.return_value = captured_auto_button[0]
            return button_mock

        mock_initial_dialog.addButton.side_effect = initial_dialog_add_button_side_effect

        # Fallback if AcceptRole button somehow not added (shouldn't happen in these tests)
        # but this ensures clickedButton always has a return_value before exec()
        if mock_initial_dialog.clickedButton.return_value is None:
             mock_initial_dialog.clickedButton.return_value = MagicMock(spec=QMessageBox.StandardButton) # Non-Accept button

        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["pkexec", self.expected_helper_script_path, self.sample_details["temp_file_path"], self.sample_details["final_file_path"]],
            returncode=pkexec_returncode, stdout=pkexec_stdout, stderr=pkexec_stderr,
        )

        # Instantiate the app, which will trigger the dialog flow
        SteelSeriesTrayApp()

        # Assertions for subprocess
        mock_subprocess_run.assert_called_once()
        cmd_called = mock_subprocess_run.call_args[0][0]
        self.assertEqual(cmd_called[0], "pkexec")
        self.assertEqual(cmd_called[1], self.expected_helper_script_path)
        self.assertEqual(cmd_called[2], self.sample_details["temp_file_path"])
        self.assertEqual(cmd_called[3], self.sample_details["final_file_path"])

        # Assertions for the feedback dialog (which is the second dialog shown)
        mock_feedback_dialog.setIcon.assert_called_with(expected_icon)
        mock_feedback_dialog.setWindowTitle.assert_called_with(expected_title)
        mock_feedback_dialog.setText.assert_called_with(expected_text)
        if isinstance(expected_informative_text_contains, str):
             self.assertIn(expected_informative_text_contains, mock_feedback_dialog.setInformativeText.call_args[0][0])
        else:
            for item in expected_informative_text_contains:
                 self.assertIn(item, mock_feedback_dialog.setInformativeText.call_args[0][0])
        mock_feedback_dialog.exec.assert_called_once()

        # Check that initial dialog was also shown
        mock_initial_dialog.exec.assert_called_once()

    # tearDown is no longer strictly needed to stop the QApplication patch,
    # but can be kept for other cleanup if necessary.
    def tearDown(self):
        self.qapplication_patch.stop()
        # If any test instance of SteelSeriesTrayApp is stored on self, clean it up.
        # e.g., if self.tray_app = SteelSeriesTrayApp() was in setUp:
        # if hasattr(self, 'tray_app') and self.tray_app:
        #     self.tray_app.quit_application() # Assuming such a method exists for proper cleanup
        pass


class TestHandleUdevPermissionsFlow(unittest.TestCase):
    qapp_for_class = None
    _qapp_created_by_class = False

    @classmethod
    def setUpClass(cls):
        cls.qapp_for_class = QApplication.instance()
        if cls.qapp_for_class is None:
            cls.qapp_for_class = QApplication([])
            cls._qapp_created_by_class = True
        else:
            cls._qapp_created_by_class = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_qapp_created_by_class", False) and QApplication.instance():
            QApplication.quit()
        # cls.qapp_for_class = None

    def setUp(self):
        self.qapp_instance = TestHandleUdevPermissionsFlow.qapp_for_class

        self.qapplication_patch = patch('headsetcontrol_tray.app.QApplication', return_value=self.qapp_instance)
        self.mock_qapplication_constructor = self.qapplication_patch.start()

        # Prevent _handle_udev_permissions_flow from running during SteelSeriesTrayApp instantiation
        # as we want to test it in isolation.
        with patch.object(SteelSeriesTrayApp, '_handle_udev_permissions_flow', MagicMock()) as _:
            # Also, to prevent actual headset connection attempts during app instantiation for these UI tests
            with patch('headsetcontrol_tray.app.hs_svc.HeadsetService') as MockHeadsetSvcForInit, \
                 patch('headsetcontrol_tray.app.cfg_mgr.ConfigManager') as MockConfigManagerForInit:

                mock_hs_instance = MockHeadsetSvcForInit.return_value
                mock_hs_instance.udev_setup_details = None
                mock_hs_instance.is_device_connected.return_value = True
                # Provide default return values for methods called by SystemTrayIcon.__init__
                mock_hs_instance.get_battery_level.return_value = 75
                mock_hs_instance.is_charging.return_value = False
                mock_hs_instance.get_chatmix_value.return_value = 64
                mock_hs_instance.get_sidetone_level.return_value = 0
                mock_hs_instance.get_current_eq_preset_id.return_value = 0 # Used by set_initial_headset_settings
                # get_current_eq_values might also be called if eq_type is custom and a curve is applied
                mock_hs_instance.get_current_eq_values.return_value = [0]*10


                mock_cfg_instance = MockConfigManagerForInit.return_value
                mock_cfg_instance.get_last_active_eq_preset_id.return_value = 0
                mock_cfg_instance.get_active_eq_type.return_value = "hardware" # or "custom"
                mock_cfg_instance.get_last_custom_eq_curve_name.return_value = "Flat"
                # Ensure get_all_custom_eq_curves returns a dict, and Flat exists if it's default
                mock_cfg_instance.get_all_custom_eq_curves.return_value = {"Flat": [0,0,0,0,0,0,0,0,0,0]}
                mock_cfg_instance.get_custom_eq_curve.return_value = [0,0,0,0,0,0,0,0,0,0] # For "Flat"
                mock_cfg_instance.get_last_sidetone_level.return_value = 0
                mock_cfg_instance.get_last_inactive_timeout.return_value = 15

                self.app_instance = SteelSeriesTrayApp()


        self.mock_qmessagebox_class_patch = patch('headsetcontrol_tray.app.QMessageBox')
        self.MockQMessageBoxClass = self.mock_qmessagebox_class_patch.start()

        self.subprocess_run_patch = patch('headsetcontrol_tray.app.subprocess.run')
        self.mock_subprocess_run = self.subprocess_run_patch.start()

        self.os_path_exists_patch = patch('headsetcontrol_tray.app.os.path.exists')
        self.mock_os_path_exists = self.os_path_exists_patch.start()

        self.sample_udev_details = {
            "temp_file_path": "/tmp/test_rules_sample_flow.txt",
            "final_file_path": "/etc/udev/rules.d/98-sample-flow.rules",
            "rule_filename": "98-sample-flow.rules",
        }
        # Determine path to the helper script relative to app.py
        # This needs to be done carefully as __file__ in tests points to the test file.
        # We get the app module's file path to correctly determine the script path.
        app_module_path = sys.modules["headsetcontrol_tray.app"].__file__
        if app_module_path is None: # Should not happen if app is imported
            raise FileNotFoundError("Could not determine app.py path")
        current_script_dir = os.path.dirname(os.path.abspath(app_module_path))
        repo_root = os.path.abspath(os.path.join(current_script_dir, ".."))
        self.expected_helper_script_path = os.path.join(repo_root, "scripts", "install-udev-rules.sh")


    def tearDown(self):
        self.qapplication_patch.stop()
        self.mock_qmessagebox_class_patch.stop()
        self.subprocess_run_patch.stop()
        self.os_path_exists_patch.stop()
        # Ensure to stop ConfigManager patch if it was started in setUp for the class
        # However, it's patched within a 'with' block in setUp, so it's auto-stopped.
        # If it were self.config_manager_patch = patch(...); self.mock_cfg = self.config_manager_patch.start(),
        # then self.config_manager_patch.stop() would be needed here.

    def _configure_dialog_flow(self, click_auto_button: bool, script_exists: bool = True, pkexec_result_code: int = 0, pkexec_stdout: str = "", pkexec_stderr: str = ""):
        mock_initial_dialog = MagicMock(spec=QMessageBox, name="InitialDialogInstance")
        mock_feedback_dialog = MagicMock(spec=QMessageBox, name="FeedbackDialogInstance")

        # If script doesn't exist, only initial dialog is shown, then QMessageBox.critical
        # The side_effect should provide enough mocks for all QMessageBox instantiations in the flow.
        # For script_not_found, after initial, a QMessageBox.critical (static) is called, not an instance.
        # For other pkexec flows, after initial, a feedback dialog instance is created.
        if not script_exists and click_auto_button:
            # Initial dialog, then the static QMessageBox.critical is called.
            # No second instance like mock_feedback_dialog is created by app for this path.
            self.MockQMessageBoxClass.side_effect = [mock_initial_dialog, MagicMock(), MagicMock(), MagicMock()]
        else:
            self.MockQMessageBoxClass.side_effect = [mock_initial_dialog, mock_feedback_dialog, MagicMock(), MagicMock()]


        auto_button_mock = MagicMock(spec=QMessageBox.StandardButton, name="AutoButton")
        close_button_mock = MagicMock(spec=QMessageBox.StandardButton, name="CloseButton")

        def add_button_side_effect(text_or_button, role=None):
            # Check for "Install Automatically" button
            if role == QMessageBox.AcceptRole and text_or_button == "Install Automatically":
                return auto_button_mock
            # Check for Close button (usually added as a standard enum)
            elif isinstance(text_or_button, QMessageBox.StandardButton) and text_or_button == QMessageBox.Close:
                return close_button_mock
            # Fallback for any other buttons
            return MagicMock(spec=QMessageBox.StandardButton, name=f"OtherButton_{text_or_button}")

        mock_initial_dialog.addButton.side_effect = add_button_side_effect

        if click_auto_button:
            mock_initial_dialog.clickedButton.return_value = auto_button_mock
        else:
            mock_initial_dialog.clickedButton.return_value = close_button_mock # Or any non-auto button

        self.mock_os_path_exists.return_value = script_exists
        if script_exists: # Only setup subprocess_run if script is supposed to exist and be called
            self.mock_subprocess_run.return_value = subprocess.CompletedProcess(
                args=["pkexec", self.expected_helper_script_path, self.sample_udev_details["temp_file_path"], self.sample_udev_details["final_file_path"]],
                returncode=pkexec_result_code, stdout=pkexec_stdout, stderr=pkexec_stderr
            )
        return mock_initial_dialog, mock_feedback_dialog


    def test_user_chooses_auto_script_not_found(self):
        mock_initial_dialog, _ = self._configure_dialog_flow(click_auto_button=True, script_exists=False)

        self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)

        mock_initial_dialog.exec.assert_called_once()
        self.mock_os_path_exists.assert_called_with(self.expected_helper_script_path)
        self.MockQMessageBoxClass.critical.assert_called_once()
        args, _ = self.MockQMessageBoxClass.critical.call_args
        self.assertIn("Installation script not found", args[2])
        self.mock_subprocess_run.assert_not_called()

    def test_user_chooses_auto_pkexec_success(self):
        mock_initial_dialog, mock_feedback_dialog = self._configure_dialog_flow(click_auto_button=True, script_exists=True, pkexec_result_code=0)

        self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)

        mock_initial_dialog.exec.assert_called_once()
        self.mock_subprocess_run.assert_called_once()
        mock_feedback_dialog.setText.assert_called_with("Udev rules installed successfully.")
        mock_feedback_dialog.exec.assert_called_once()

    def test_user_chooses_auto_pkexec_auth_cancelled(self):
        mock_initial_dialog, mock_feedback_dialog = self._configure_dialog_flow(click_auto_button=True, script_exists=True, pkexec_result_code=126)
        self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)
        mock_initial_dialog.exec.assert_called_once()
        self.mock_subprocess_run.assert_called_once()
        mock_feedback_dialog.setText.assert_called_with("Udev rule installation was cancelled.")
        mock_feedback_dialog.exec.assert_called_once()

    def test_user_chooses_auto_pkexec_auth_error(self):
        mock_initial_dialog, mock_feedback_dialog = self._configure_dialog_flow(click_auto_button=True, script_exists=True, pkexec_result_code=127, pkexec_stderr="Auth fail")
        self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)
        mock_initial_dialog.exec.assert_called_once()
        self.mock_subprocess_run.assert_called_once()
        mock_feedback_dialog.setText.assert_called_with("Failed to install udev rules due to an authorization error.")
        self.assertIn("Auth fail", mock_feedback_dialog.setInformativeText.call_args[0][0])
        mock_feedback_dialog.exec.assert_called_once()

    def test_user_chooses_auto_pkexec_script_error(self):
        mock_initial_dialog, mock_feedback_dialog = self._configure_dialog_flow(click_auto_button=True, script_exists=True, pkexec_result_code=1, pkexec_stderr="Script error")
        self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)
        mock_initial_dialog.exec.assert_called_once()
        self.mock_subprocess_run.assert_called_once()
        mock_feedback_dialog.setText.assert_called_with("The udev rule installation script failed.")
        self.assertIn("Script error", mock_feedback_dialog.setInformativeText.call_args[0][0])
        mock_feedback_dialog.exec.assert_called_once()

    def test_user_chooses_auto_pkexec_not_found(self):
        # This simulates pkexec itself not being found
        mock_initial_dialog, _ = self._configure_dialog_flow(click_auto_button=True, script_exists=True)
        self.mock_subprocess_run.side_effect = FileNotFoundError("pkexec not found")

        self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)

        mock_initial_dialog.exec.assert_called_once()
        self.mock_subprocess_run.assert_called_once() # Attempt to run is made
        self.MockQMessageBoxClass.critical.assert_called_once()
        args, _ = self.MockQMessageBoxClass.critical.call_args
        self.assertIn("pkexec command not found", args[2])

    def test_user_chooses_close_on_initial_dialog(self):
        mock_initial_dialog, mock_feedback_dialog = self._configure_dialog_flow(click_auto_button=False) # Simulate clicking Close

        with patch('headsetcontrol_tray.app.logger') as mock_logger:
            self.app_instance._handle_udev_permissions_flow(self.sample_udev_details)
            mock_initial_dialog.exec.assert_called_once()
            self.mock_subprocess_run.assert_not_called()
            mock_feedback_dialog.exec.assert_not_called() # No feedback dialog if closed
            self.MockQMessageBoxClass.critical.assert_not_called() # No critical error either
            # Check for specific log message
            found_log = False
            for call in mock_logger.info.call_args_list:
                if "User closed or cancelled the udev rules dialog" in call[0][0]:
                    found_log = True
                    break
            self.assertTrue(found_log, "Log message for closing dialog not found.")


if __name__ == "__main__":
    unittest.main()
