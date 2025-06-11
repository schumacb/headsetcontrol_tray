import os
import subprocess  # For subprocess.CompletedProcess
import sys
from typing import Any  # Added typing.Any
import unittest
from unittest.mock import MagicMock, Mock, patch  # Removed Any from here

# Ensure the application modules can be imported
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")),
)

from PySide6.QtWidgets import QApplication, QMessageBox
from unittest.mock import MagicMock, Mock # This line was already effectively present but re-adding for completeness if original was different
import pytest  # Added for @pytest.mark.usefixtures

# Modules to be tested or mocked
try:
    from headsetcontrol_tray.app import SteelSeriesTrayApp
except ImportError as e:
    print(f"ImportError in test_app.py: {e}")
    raise


@pytest.mark.usefixtures("qapp")
class TestSteelSeriesTrayAppUdevDialog(unittest.TestCase):
    # qapp_for_class is no longer needed as qapp fixture handles instance per test.
    # setUpClass is no longer needed as qapp fixture handles setup per test.
    # tearDownClass is no longer needed as qapp fixture handles teardown per test.

    def setUp(self):
        # qapp fixture ensures QApplication.instance() is available here.
        self.qapp_instance = QApplication.instance()
        assert self.qapp_instance is not None, (
            "qapp fixture did not provide a QApplication instance for setUp."
        )

        # Patch 'headsetcontrol_tray.app.QApplication' to return the qapp fixture's instance
        self.qapplication_patch = patch(
            "headsetcontrol_tray.app.QApplication",
            return_value=self.qapp_instance,
        )
        self.qapplication_patch.start()

        self.sample_details = {
            "temp_file_path": "/tmp/test_rules_sample.txt",
            "final_file_path": "/etc/udev/rules.d/99-sample.rules",
            "rule_filename": "99-sample.rules",
        }

        # Ensure __file__ is not None for path operations
        app_module_file = sys.modules["headsetcontrol_tray.app"].__file__
        assert app_module_file is not None, (
            "sys.modules['headsetcontrol_tray.app'].__file__ is None"
        )
        current_script_dir = os.path.dirname(os.path.abspath(app_module_file))
        repo_root = os.path.abspath(os.path.join(current_script_dir, ".."))
        self.expected_helper_script_path = os.path.join(
            repo_root,
            "scripts",
            "install-udev-rules.sh",
        )

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    def test_initial_dialog_shown_when_details_present(
        self,
        MockHeadsetService: MagicMock,
        MockQMessageBoxClass: MagicMock,
        _MockSystemTrayIcon: MagicMock,
    ):
        mock_service_instance = MockHeadsetService.return_value
        # Simulate that HeadsetService failed to connect and thus populated udev_setup_details
        mock_service_instance.udev_setup_details = self.sample_details
        # is_device_connected would likely be false if udev_setup_details is populated due to connection failure
        mock_service_instance.is_device_connected = Mock(return_value=False)
        mock_service_instance.close = Mock()

        mock_dialog_instance = MockQMessageBoxClass.return_value

        # close_button_mock was unused
        added_buttons_initial = []

        def side_effect_add_button_initial(text_or_button: str | QMessageBox.StandardButton, role: QMessageBox.ButtonRole | None = None):
            button = MagicMock(spec=QMessageBox.StandardButton)
            added_buttons_initial.append(
                {"button": button, "role": role, "text_or_enum": text_or_button},
            )
            return button

        mock_dialog_instance.addButton.side_effect = side_effect_add_button_initial

        def set_clicked_button_to_close_equivalent(*_, **_):
            found_close_button = None
            for b_info in added_buttons_initial:
                if (
                    b_info.get("text_or_enum") == QMessageBox.StandardButton.Close
                ):  # Corrected Enum
                    found_close_button = b_info["button"]
                    break
            if not found_close_button:
                found_close_button = MagicMock(spec=QMessageBox.StandardButton)
            mock_dialog_instance.clickedButton.return_value = found_close_button

        mock_dialog_instance.exec.side_effect = set_clicked_button_to_close_equivalent

        SteelSeriesTrayApp()  # Constructor called for side effects

        MockQMessageBoxClass.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()
        mock_dialog_instance.setWindowTitle.assert_called_with(
            "Headset Permissions Setup Required",
        )
        # Updated assertion for the main text
        mock_dialog_instance.setText.assert_called_with(
            "Could not connect to your SteelSeries headset. This may be due to missing udev permissions (udev rules).",
        )

        informative_text_call_args = mock_dialog_instance.setInformativeText.call_args[
            0
        ][0]
        self.assertIn(
            "To resolve this, you can use the 'Install Automatically' button",
            informative_text_call_args,
        )
        self.assertIn(self.sample_details["temp_file_path"], informative_text_call_args)
        self.assertNotIn("Show Manual Instructions Only", informative_text_call_args)

    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")
    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    def test_initial_dialog_not_shown_when_details_absent(
        self,
        MockHeadsetService: MagicMock,
        MockQMessageBoxClass: MagicMock,
        _MockSystemTrayIcon: MagicMock,
    ):
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = None
        mock_service_instance.is_device_connected = Mock(
            return_value=True,
        )  # Or False, shouldn't matter if details are None
        mock_service_instance.close = Mock()

        SteelSeriesTrayApp()  # Constructor called for side effects
        MockQMessageBoxClass.assert_not_called()

    # tearDown is no longer strictly needed to stop the QApplication patch,
    # but can be kept for other cleanup if necessary.
    def tearDown(self):
        self.qapplication_patch.stop()
        # If any test instance of SteelSeriesTrayApp is stored on self, clean it up.
        # e.g., if self.tray_app = SteelSeriesTrayApp() was in setUp:
        # if hasattr(self, 'tray_app') and self.tray_app:

        # pass # Removed duplicate pass, only one tearDown needed.


if __name__ == "__main__":
    unittest.main()
