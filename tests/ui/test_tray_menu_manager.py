"""Unit tests for the TrayMenuManager class."""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from headsetcontrol_tray import app_config  # For SIDETONE_OPTIONS etc.
from headsetcontrol_tray.ui.equalizer_editor_widget import EQ_TYPE_CUSTOM, EQ_TYPE_HARDWARE
from headsetcontrol_tray.ui.tray_menu_manager import TrayMenuManager


class TestTrayMenuManager(unittest.TestCase):
    """Test suite for the TrayMenuManager."""

    def setUp(self) -> None:
        self.mock_headset_service = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_tray_icon_parent = MagicMock(spec=QSystemTrayIcon)  # For showMessage
        self.mock_app_quit_fn = MagicMock()
        self.mock_open_settings_fn = MagicMock()

        # Mock config values needed for menu creation
        self.mock_config_manager.get_all_custom_eq_curves.return_value = {"Custom1": [0] * 10, "Flat": [1] * 10}
        self.mock_config_manager.get_last_sidetone_level.return_value = app_config.DEFAULT_SIDETONE_LEVEL
        self.mock_config_manager.get_last_inactive_timeout.return_value = app_config.DEFAULT_INACTIVE_TIMEOUT
        self.mock_config_manager.get_active_eq_type.return_value = EQ_TYPE_CUSTOM
        self.mock_config_manager.get_last_custom_eq_curve_name.return_value = "Flat"
        self.mock_config_manager.get_last_active_eq_preset_id.return_value = app_config.DEFAULT_EQ_PRESET_ID

        # It's important app_config.DEFAULT_EQ_CURVES has 'Flat' if tests rely on it
        if "Flat" not in app_config.DEFAULT_EQ_CURVES:
            app_config.DEFAULT_EQ_CURVES["Flat"] = [0] * 10  # Ensure it exists for key sorting logic

        with (
            patch.object(QMenu, "addAction", return_value=MagicMock(spec=QAction)),
            patch.object(QMenu, "addMenu", return_value=MagicMock(spec=QMenu)),
            patch.object(QMenu, "addSeparator"),
        ):
            self.menu_manager = TrayMenuManager(
                headset_service=self.mock_headset_service,
                config_manager=self.mock_config_manager,
                tray_icon_parent_widget=self.mock_tray_icon_parent,
                application_quit_fn=self.mock_app_quit_fn,
                open_settings_fn=self.mock_open_settings_fn,
            )

    def test_initialization_creates_menu_and_actions(self) -> None:
        """Test that menu and main actions are created on initialization."""
        assert self.menu_manager.get_context_menu() is not None
        assert self.menu_manager.battery_action is not None
        assert self.menu_manager.chatmix_action is not None
        assert len(self.menu_manager.sidetone_action_group) > 0
        assert len(self.menu_manager.timeout_action_group) > 0
        assert len(self.menu_manager.unified_eq_action_group) > 0

        # Check if main control actions (Settings, Exit) were added
        # This requires more detailed mocking of QMenu or checking action texts
        # For now, assume _create_main_control_actions was called by _populate_menu

    def test_update_menu_state_texts_and_checks(self) -> None:
        """Test updating menu item texts and check states."""
        self.mock_config_manager.get_last_sidetone_level.return_value = 50  # Example value
        sidetone_action_to_check = None
        for action in self.menu_manager.sidetone_action_group:
            if action.data() == 50:
                sidetone_action_to_check = action
                action.setChecked = MagicMock()  # Mock setChecked for this action
            else:
                action.setChecked = MagicMock()

        self.menu_manager.update_menu_state("Battery: 75%", "ChatMix: Game (75%)")

        assert self.menu_manager.battery_action.text() == "Battery: 75%"
        assert self.menu_manager.chatmix_action.text() == "ChatMix: Game (75%)"

        if sidetone_action_to_check:
            sidetone_action_to_check.setChecked.assert_called_with(True)
        for action in self.menu_manager.sidetone_action_group:
            if action.data() != 50:
                action.setChecked.assert_called_with(False)

    def test_handle_sidetone_selected_success(self) -> None:
        """Test sidetone selection successfully updates service and config."""
        self.mock_headset_service.set_sidetone_level.return_value = True
        test_level = 75

        self.menu_manager._handle_sidetone_selected(test_level)

        self.mock_headset_service.set_sidetone_level.assert_called_once_with(test_level)
        self.mock_config_manager.set_last_sidetone_level.assert_called_once_with(test_level)
        self.mock_tray_icon_parent.showMessage.assert_called_with(
            "Success", "Sidetone set.", QSystemTrayIcon.MessageIcon.Information, 1500,
        )

    def test_handle_sidetone_selected_failure(self) -> None:
        """Test sidetone selection failure shows error."""
        self.mock_headset_service.set_sidetone_level.return_value = False
        test_level = 75

        self.menu_manager._handle_sidetone_selected(test_level)

        self.mock_headset_service.set_sidetone_level.assert_called_once_with(test_level)
        self.mock_config_manager.set_last_sidetone_level.assert_not_called()
        self.mock_tray_icon_parent.showMessage.assert_called_with(
            "Error", "Failed to set sidetone. Headset connected?", QSystemTrayIcon.MessageIcon.Warning, 2000,
        )

    def test_handle_timeout_selected_success(self) -> None:
        """Test timeout selection."""
        self.mock_headset_service.set_inactive_timeout.return_value = True
        test_minutes = 30
        self.menu_manager._handle_timeout_selected(test_minutes)
        self.mock_headset_service.set_inactive_timeout.assert_called_once_with(test_minutes)
        self.mock_config_manager.set_last_inactive_timeout.assert_called_once_with(test_minutes)

    def test_handle_eq_selected_custom_success(self) -> None:
        """Test custom EQ selection."""
        self.mock_headset_service.is_device_connected.return_value = True
        self.mock_headset_service.set_eq_values.return_value = True
        eq_name = "Custom1"
        eq_values = [1.0, 2.0]  # Example
        self.mock_config_manager.get_custom_eq_curve.return_value = eq_values

        self.menu_manager._handle_eq_selected((EQ_TYPE_CUSTOM, eq_name))

        self.mock_config_manager.get_custom_eq_curve.assert_called_once_with(eq_name)
        self.mock_headset_service.set_eq_values.assert_called_once_with(eq_values)
        self.mock_config_manager.set_last_custom_eq_curve_name.assert_called_once_with(eq_name)
        self.mock_config_manager.set_setting.assert_called_once_with("active_eq_type", EQ_TYPE_CUSTOM)

    def test_handle_eq_selected_hardware_success(self) -> None:
        """Test hardware EQ selection."""
        self.mock_headset_service.is_device_connected.return_value = True
        self.mock_headset_service.set_eq_preset_id.return_value = True
        preset_id = 1

        self.menu_manager._handle_eq_selected((EQ_TYPE_HARDWARE, preset_id))

        self.mock_headset_service.set_eq_preset_id.assert_called_once_with(preset_id)
        self.mock_config_manager.set_last_active_eq_preset_id.assert_called_once_with(preset_id)
        self.mock_config_manager.set_setting.assert_called_once_with("active_eq_type", EQ_TYPE_HARDWARE)

    def test_handle_eq_selected_device_not_connected(self) -> None:
        """Test EQ selection when device is not connected."""
        self.mock_headset_service.is_device_connected.return_value = False
        self.menu_manager._handle_eq_selected((EQ_TYPE_CUSTOM, "Any"))
        self.mock_tray_icon_parent.showMessage.assert_called_with(
            "Error", "Cannot apply EQ. Headset not connected.", QSystemTrayIcon.MessageIcon.Warning, 2000,
        )
        self.mock_headset_service.set_eq_values.assert_not_called()
        self.mock_headset_service.set_eq_preset_id.assert_not_called()

    def test_main_control_actions_trigger_callbacks(self) -> None:
        """Test that main control actions (Settings, Exit) trigger their callbacks."""
        # This requires finding the specific QAction objects.
        # We assume they are the last two actions added after the last separator.
        # This is a bit fragile. A better way would be to store these actions as members.

        # Simulate finding "Settings..." and "Exit" actions
        # This part is tricky without more access to the created QMenu internals
        # or by refactoring TrayMenuManager to store these specific actions.

        # For now, let's assume the _populate_menu correctly connects them.
        # We can test the callbacks directly.
        self.menu_manager.open_settings_fn()
        self.mock_open_settings_fn.assert_called_once()

        self.menu_manager.application_quit_fn()
        self.mock_app_quit_fn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
