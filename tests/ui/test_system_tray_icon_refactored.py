"""
Unit tests for the refactored SystemTrayIcon class.
Focuses on its coordinator role with new components.
"""

import unittest
from unittest.mock import ANY, MagicMock, patch

from PySide6.QtGui import QIcon  # For type hinting if needed
from PySide6.QtWidgets import QMenu, QSystemTrayIcon  # For ActivationReason, QMenu

from headsetcontrol_tray.ui.equalizer_editor_widget import EQ_TYPE_CUSTOM
from headsetcontrol_tray.ui.headset_polling_service import HeadsetPollingService

# Assuming components are in src.headsetcontrol_tray.ui
from headsetcontrol_tray.ui.system_tray_icon import SystemTrayIcon


class TestSystemTrayIconRefactored(unittest.TestCase):
    """Test suite for the refactored SystemTrayIcon."""

    @patch("headsetcontrol_tray.ui.system_tray_icon.TrayIconPainter")
    @patch("headsetcontrol_tray.ui.system_tray_icon.TrayTooltipManager")
    @patch("headsetcontrol_tray.ui.system_tray_icon.TrayMenuManager")
    @patch("headsetcontrol_tray.ui.system_tray_icon.HeadsetPollingService")
    @patch("headsetcontrol_tray.ui.system_tray_icon.ChatMixManager")
    @patch("headsetcontrol_tray.ui.system_tray_icon.SettingsDialog")
    @patch("headsetcontrol_tray.ui.system_tray_icon.QIcon")  # Mock QIcon.fromTheme
    def setUp(
        self,
        mock_qicon_from_theme,
        mock_settings_dialog_class,
        mock_chatmix_manager_class,
        mock_polling_service_class,
        mock_menu_manager_class,
        mock_tooltip_manager_class,
        mock_icon_painter_class,
    ) -> None:
        self.mock_headset_service = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_app_quit_fn = MagicMock()

        # Setup return values for mocked component instances
        self.mock_icon_painter_instance = mock_icon_painter_class.return_value
        self.mock_tooltip_manager_instance = mock_tooltip_manager_class.return_value
        self.mock_menu_manager_instance = mock_menu_manager_class.return_value
        self.mock_polling_service_instance = mock_polling_service_class.return_value
        self.mock_chatmix_manager_instance = mock_chatmix_manager_class.return_value
        self.mock_settings_dialog_instance = mock_settings_dialog_class.return_value

        # Mock QIcon.fromTheme to return a mock QIcon
        self.mock_base_theme_icon = MagicMock(spec=QIcon)
        mock_qicon_from_theme.fromTheme.return_value = self.mock_base_theme_icon

        # Store mock classes on self for use in tests
        # Order matches @patch decorators from bottom up
        self.mock_icon_painter_class_mock = mock_icon_painter_class
        self.mock_tooltip_manager_class_mock = mock_tooltip_manager_class
        self.mock_menu_manager_class_mock = mock_menu_manager_class
        self.mock_polling_service_class_mock = mock_polling_service_class
        self.mock_chatmix_manager_class_mock = mock_chatmix_manager_class
        self.mock_settings_dialog_class_mock = mock_settings_dialog_class
        self.mock_qicon_class_mock = mock_qicon_from_theme # This is the QIcon class itself

        # Use a real QMenu instance for setContextMenu, as MagicMock(spec=QMenu) caused ValueError
        self.real_qmenu_for_test = QMenu()
        self.mock_menu_manager_instance.get_context_menu.return_value = self.real_qmenu_for_test

        self.tray_icon = SystemTrayIcon(
            headset_service=self.mock_headset_service,
            config_manager=self.mock_config_manager,
            application_quit_fn=self.mock_app_quit_fn,
            parent=None,
        )
        # REMOVED: self.tray_icon.setIcon = MagicMock() - will be handled by @patch.object in specific tests
        # REMOVED: self.tray_icon.setToolTip = MagicMock() - will be handled by @patch.object in specific tests

    def test_initialization(self) -> None:
        """Test initialization of SystemTrayIcon and its components."""
        self.mock_icon_painter_instance = self.tray_icon.icon_painter  # Get instance from tray_icon
        self.mock_icon_painter_instance = self.tray_icon.icon_painter.__class__(
            base_icon=self.mock_base_theme_icon,
        )  # Re-init with expected arg

        # Assert on the mock classes passed to setUp (now stored on self)
        self.mock_icon_painter_class_mock.assert_called_once_with(base_icon=self.mock_base_theme_icon)
        self.mock_tooltip_manager_class_mock.assert_called_once_with(config_manager_getter=ANY)  # callable
        self.mock_menu_manager_class_mock.assert_called_once_with(
            headset_service=self.mock_headset_service,
            config_manager=self.mock_config_manager,
            tray_icon_parent_widget=self.tray_icon,
            application_quit_fn=self.mock_app_quit_fn,
            open_settings_fn=self.tray_icon._open_settings_dialog,
        )
        self.mock_polling_service_class_mock.assert_called_once_with(
            headset_service=self.mock_headset_service, parent=self.tray_icon,
        )
        self.mock_chatmix_manager_class_mock.assert_called_once_with(self.mock_config_manager)

        # Verify the context menu was set correctly on the real SystemTrayIcon instance
        self.assertIs(self.tray_icon.contextMenu(), self.real_qmenu_for_test)
        self.mock_polling_service_instance.status_updated.connect.assert_called_once_with(
            self.tray_icon._on_status_updated,
        )
        self.mock_polling_service_instance.start.assert_called_once()
        # set_initial_headset_settings is called, check a part of its effect
        self.mock_headset_service.is_device_connected.assert_called()  # Called by set_initial_headset_settings

    @patch.object(SystemTrayIcon, "setToolTip")  # Mock the instance method
    @patch.object(SystemTrayIcon, "setIcon")  # Mock the instance method
    def test_on_status_updated_flow(self, mock_set_icon, mock_set_tooltip) -> None:
        """Test the flow when a status update is received."""
        mock_new_icon = MagicMock(spec=QIcon)
        mock_new_icon.cacheKey.return_value = 2  # Different from initial
        self.mock_icon_painter_instance.create_status_icon.return_value = mock_new_icon

        mock_new_tooltip = "New Tooltip"
        self.mock_tooltip_manager_instance.get_tooltip.return_value = mock_new_tooltip

        # Simulate an initial icon state for cacheKey comparison
        initial_mock_icon = MagicMock(spec=QIcon)
        initial_mock_icon.cacheKey.return_value = 1
        self.tray_icon.icon = MagicMock(return_value=initial_mock_icon)  # Mock self.icon() call
        self.tray_icon.toolTip = MagicMock(return_value="Old Tooltip")  # Mock self.toolTip()

        status_data = {
            HeadsetPollingService.KEY_IS_CONNECTED: True,
            HeadsetPollingService.KEY_BATTERY_LEVEL: 80,
            HeadsetPollingService.KEY_BATTERY_STATUS_TEXT: "BATTERY_AVAILABLE",
            HeadsetPollingService.KEY_CHATMIX_VALUE: 64,
        }
        # Config manager return values for tooltip part
        self.mock_config_manager.get_active_eq_type.return_value = EQ_TYPE_CUSTOM
        self.mock_config_manager.get_last_custom_eq_curve_name.return_value = "TestEQ"

        self.tray_icon._on_status_updated(status_data)

        self.mock_icon_painter_instance.create_status_icon.assert_called_once_with(
            is_connected=True, battery_level=80, battery_status_text="BATTERY_AVAILABLE", chatmix_value=64,
        )
        mock_set_icon.assert_called_once_with(mock_new_icon)  # Check if SystemTrayIcon.setIcon was called

        self.mock_tooltip_manager_instance.get_tooltip.assert_called_once_with(
            is_connected=True,
            battery_level=80,
            battery_status_text="BATTERY_AVAILABLE",
            chatmix_value=64,
            active_eq_type=EQ_TYPE_CUSTOM,
            current_custom_eq_name="TestEQ",
            current_hw_preset_id=None,
        )
        mock_set_tooltip.assert_called_once_with(mock_new_tooltip)  # Check if SystemTrayIcon.setToolTip was called

        self.mock_menu_manager_instance.update_menu_state.assert_called_once_with(ANY, ANY)  # Texts
        self.mock_chatmix_manager_instance.update_volumes.assert_called_once_with(64)

    def test_open_settings_dialog_new_instance(self) -> None:
        """Test opening settings dialog when no instance exists."""
        self.tray_icon.settings_dialog = None  # Ensure no existing dialog

        self.tray_icon._open_settings_dialog()

        self.tray_icon.settings_dialog.__class__.assert_called_once_with(
            self.mock_config_manager, self.mock_headset_service,
        )
        # Check connections
        self.mock_settings_dialog_instance.eq_applied.connect.assert_called_with(
            self.tray_icon._handle_settings_dialog_change,
        )
        self.mock_settings_dialog_instance.settings_changed.connect.assert_called_with(
            self.tray_icon._handle_settings_dialog_change,
        )
        self.mock_settings_dialog_instance.finished.connect.assert_called_with(
            self.tray_icon._on_settings_dialog_closed,
        )
        self.mock_settings_dialog_instance.show.assert_called_once()

    def test_open_settings_dialog_existing_instance(self) -> None:
        """Test opening settings dialog when an instance already exists and is visible."""
        self.tray_icon.settings_dialog = self.mock_settings_dialog_instance
        self.mock_settings_dialog_instance.isVisible.return_value = True  # Dialog is visible

        self.tray_icon._open_settings_dialog()

        self.mock_settings_dialog_instance.activateWindow.assert_called_once()
        self.mock_settings_dialog_instance.raise_.assert_called_once()
        self.mock_settings_dialog_instance.equalizer_widget.refresh_view.assert_called_once()
        # Ensure show is not called again if already visible
        self.mock_settings_dialog_instance.show.assert_not_called()

    def test_handle_settings_dialog_change(self) -> None:
        """Test handling changes from the settings dialog."""
        # Reset mock for _poll_status as it's called during initialization
        self.mock_polling_service_instance._poll_status.reset_mock()
        self.tray_icon._handle_settings_dialog_change()
        # pylint: disable=protected-access
        self.mock_polling_service_instance._poll_status.assert_called_once()

    @patch.object(SystemTrayIcon, "_open_settings_dialog")
    def test_on_activated_trigger(self, mock_open_settings) -> None:
        """Test left-click activation opens settings."""
        self.tray_icon._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
        mock_open_settings.assert_called_once()

    @patch.object(QMenu, "popup")
    def test_on_activated_context(self, mock_qmenu_popup_method: MagicMock) -> None:
        """Test right-click activation shows context menu."""
        self.tray_icon._on_activated(QSystemTrayIcon.ActivationReason.Context)
        # self.real_qmenu_for_test is the instance whose popup method should be patched
        # by @patch.object(QMenu, "popup") and thus should be mock_qmenu_popup_method
        # if it's an instance method patch on all QMenus.
        # More directly, assert that the specific instance's popup was called.
        self.real_qmenu_for_test.popup.assert_called_once_with(ANY)  # QCursor.pos()

    def test_set_initial_headset_settings_connected(self) -> None:
        """Test applying initial settings when device is connected."""
        # pylint: disable=protected-access
        self.mock_polling_service_instance._is_currently_connected = True
        self.mock_headset_service.is_device_connected.return_value = True  # Also ensure service agrees

        self.mock_config_manager.get_active_eq_type.return_value = EQ_TYPE_CUSTOM
        self.mock_config_manager.get_last_custom_eq_curve_name.return_value = "InitialEQ"
        self.mock_config_manager.get_custom_eq_curve.return_value = [0.1, 0.2]

        # Reset mocks as set_initial_headset_settings is called during __init__
        self.mock_headset_service.set_sidetone_level.reset_mock()
        self.mock_headset_service.set_inactive_timeout.reset_mock()
        self.mock_headset_service.set_eq_values.reset_mock()
        self.mock_polling_service_instance._poll_status.reset_mock()

        self.tray_icon.set_initial_headset_settings()

        self.mock_headset_service.set_sidetone_level.assert_called_once()
        self.mock_headset_service.set_inactive_timeout.assert_called_once()
        self.mock_headset_service.set_eq_values.assert_called_once_with([0.1, 0.2])
        self.mock_polling_service_instance._poll_status.assert_called_once()

    def test_set_initial_headset_settings_not_connected(self) -> None:
        """Test initial settings are not applied if device is not connected."""
        # pylint: disable=protected-access
        self.mock_polling_service_instance._is_currently_connected = False
        self.mock_headset_service.is_device_connected.return_value = False  # Service also reports not connected

        # Reset mocks as set_initial_headset_settings might be (partially) called during __init__
        # or previous tests if instance is reused (though unittest creates new instances)
        # More importantly, we are testing this specific call's behavior.
        self.mock_headset_service.set_sidetone_level.reset_mock()
        self.mock_headset_service.set_inactive_timeout.reset_mock()
        self.mock_headset_service.set_eq_values.reset_mock()

        self.tray_icon.set_initial_headset_settings()

        self.mock_headset_service.set_sidetone_level.assert_not_called()
        self.mock_headset_service.set_inactive_timeout.assert_not_called()
        self.mock_headset_service.set_eq_values.assert_not_called()
        # _poll_status might still be called by set_initial_headset_settings regardless,
        # for now, we don't assert its call count here as the primary check is that settings are not applied.

    def test_cleanup(self) -> None:
        """Test cleanup stops the polling service."""
        self.tray_icon.cleanup()
        self.mock_polling_service_instance.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
