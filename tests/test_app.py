"""Tests for the main application logic (SteelSeriesTrayApp)."""

# Standard library imports
import logging
from pathlib import Path
import sys
import tempfile
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

# Third-party imports

# Logger instance
logger = logging.getLogger(__name__)

# Ensure the application modules can be imported by modifying sys.path
# This needs to be done before attempting to import application-specific modules.
sys.path.insert(
    0,
    str((Path(__file__).parent / ".." / "src").resolve()),
)

# Application-specific imports
# Modules to be tested or mocked
try:
    from headsetcontrol_tray.app import SteelSeriesTrayApp
except ImportError:
    logger.exception("ImportError in test_app.py")  # Removed redundant exception object e
    raise

    # @pytest.mark.usefixtures("qapp")
    # class TestSteelSeriesTrayAppUdevDialog(unittest.TestCase):
    #     """Tests UDEV dialog interactions in the SteelSeriesTrayApp."""
    #
    #     # qapp_for_class is no longer needed as qapp fixture handles instance per test.
    # setUpClass is no longer needed as qapp fixture handles setup per test.
    # tearDownClass is no longer needed as qapp fixture handles teardown per test.

    def setUp(self) -> None:
        """Set up test environment before each test."""
        # qapp fixture ensures QApplication.instance() is available here.
        self.qapp_instance = QApplication.instance()
        assert self.qapp_instance is not None, "qapp fixture did not provide a QApplication instance for setUp."

        # Patch 'headsetcontrol_tray.app.QApplication' to return the qapp fixture's instance
        self.qapplication_patch = patch(
            "headsetcontrol_tray.app.QApplication",
            return_value=self.qapp_instance,
        )
        self.qapplication_patch.start()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file_obj:
            self.temp_file = temp_file_obj  # Still assign to self for teardown
            temp_file_path = temp_file_obj.name
        # temp_file_obj is now closed. self.temp_file.name can be used for cleanup.


    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")  # Restored
    def test_initial_dialog_shown_when_details_present(
        self,
        _mock_system_tray_icon: MagicMock,  # noqa: PT019 # Corrected order, renamed
        mock_headset_service: MagicMock,  # Corrected order, renamed
        mock_qmessage_box_class: MagicMock,  # Corrected order, renamed
    ) -> None:
        """Test that the initial udev help dialog is shown if udev details are present."""
        mock_service_instance = mock_headset_service.return_value
        # is_device_connected would likely be false if udev_setup_details is populated due to connection failure
        mock_service_instance.is_device_connected = Mock(return_value=False)
        mock_service_instance.close = Mock()

        mock_dialog_instance = mock_qmessage_box_class.return_value

        # close_button_mock was unused
        added_buttons_initial = []

        def side_effect_add_button_initial(
            text_or_button: str | QMessageBox.StandardButton,
            role: QMessageBox.ButtonRole | None = None,
        ) -> MagicMock:  # Added return type
            button = MagicMock(spec=QMessageBox.StandardButton)
            added_buttons_initial.append(
                {"button": button, "role": role, "text_or_enum": text_or_button},
            )
            return button

        mock_dialog_instance.addButton.side_effect = side_effect_add_button_initial

        def set_clicked_button_to_close_equivalent(*_args: Any, **_kwargs: Any) -> None:  # Added arg and return types
            found_close_button = None
            for b_info in added_buttons_initial:
                if b_info.get("text_or_enum") == QMessageBox.StandardButton.Close:  # Corrected Enum
                    found_close_button = b_info["button"]
                    break
            if not found_close_button:
                found_close_button = MagicMock(spec=QMessageBox.StandardButton)
            mock_dialog_instance.clickedButton.return_value = found_close_button

        mock_dialog_instance.exec.side_effect = set_clicked_button_to_close_equivalent

        SteelSeriesTrayApp()  # Constructor called for side effects

        mock_qmessage_box_class.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()
        mock_dialog_instance.setWindowTitle.assert_called_with(
            "Headset Permissions Setup Required",
        )
        # Updated assertion for the main text
        mock_dialog_instance.setText.assert_called_with(
            "Could not connect to your SteelSeries headset. This may be due to missing udev permissions (udev rules).",
        )

        informative_text_call_args = mock_dialog_instance.setInformativeText.call_args[0][0]
        assert "To resolve this, you can use the 'Install Automatically' button" in informative_text_call_args
        assert "Show Manual Instructions Only" not in informative_text_call_args

    @patch("headsetcontrol_tray.app.QMessageBox")
    @patch("headsetcontrol_tray.app.hs_svc.HeadsetService")
    @patch("headsetcontrol_tray.app.sti.SystemTrayIcon")  # Restored
    def test_initial_dialog_not_shown_when_details_absent(
        self,
        _mock_system_tray_icon: MagicMock,  # noqa: PT019 # Corrected order, renamed
        mock_headset_service: MagicMock,  # Corrected order, renamed
        mock_qmessage_box_class: MagicMock,  # Corrected order, renamed
    ) -> None:
        """Test that the initial udev help dialog is not shown if udev details are absent."""
        mock_service_instance = mock_headset_service.return_value
        mock_service_instance.udev_setup_details = None
        mock_service_instance.is_device_connected = Mock(
            return_value=True,
        )  # Or False, shouldn't matter if details are None
        mock_service_instance.close = Mock()

        SteelSeriesTrayApp()  # Constructor called for side effects
        mock_qmessage_box_class.assert_not_called()

    # tearDown is no longer strictly needed to stop the QApplication patch,
    # but can be kept for other cleanup if necessary.
