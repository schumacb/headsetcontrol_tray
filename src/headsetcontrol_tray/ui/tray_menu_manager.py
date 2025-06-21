"""
Manages the creation, population, and state of the system tray context menu,
and handles actions triggered from the menu.
"""

from collections.abc import Callable
import logging
from typing import Any

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon  # QSystemTrayIcon for MessageIcon

from headsetcontrol_tray import app_config
from headsetcontrol_tray import config_manager as cfg_mgr
from headsetcontrol_tray import headset_service as hs_svc

from .equalizer_editor_widget import (  # For string constants
    EQ_TYPE_CUSTOM,
    EQ_TYPE_HARDWARE,
    HW_PRESET_DISPLAY_PREFIX,
)

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class TrayMenuManager:
    """Manages the system tray icon's context menu.

    This includes creation, updates, and handling of menu actions.
    """

    def __init__(
        self,
        headset_service: hs_svc.HeadsetService,
        config_manager: cfg_mgr.ConfigManager,
        tray_icon_parent_widget: QSystemTrayIcon,  # For showing messages
        application_quit_fn: Callable[[], None],
        open_settings_fn: Callable[[], None],
    ) -> None:
        self.headset_service = headset_service
        self.config_manager = config_manager
        self.tray_icon_parent_widget = tray_icon_parent_widget
        self.application_quit_fn = application_quit_fn
        self.open_settings_fn = open_settings_fn

        self.context_menu = QMenu()
        self.battery_action: QAction | None = None
        self.chatmix_action: QAction | None = None
        self.sidetone_action_group: list[QAction] = []
        self.timeout_action_group: list[QAction] = []
        self.unified_eq_action_group: list[QAction] = []

        self._populate_menu()

    def get_context_menu(self) -> QMenu:
        """Returns the managed context menu."""
        return self.context_menu

    def _populate_menu(self) -> None:
        """Clears and populates the context menu with all actions and submenus."""
        logger.debug("Populating context menu.")
        self.context_menu.clear()
        self.sidetone_action_group.clear()
        self.timeout_action_group.clear()
        self.unified_eq_action_group.clear()

        self._create_status_actions()
        self.context_menu.addSeparator()
        self._create_sidetone_menu()
        self._create_timeout_menu()
        self._create_eq_menu()
        self.context_menu.addSeparator()
        self._create_main_control_actions()

        # Initial update of checks based on current config
        self.update_menu_state("Battery: Initializing...", "ChatMix: Initializing...")

    def _create_status_actions(self) -> None:
        self.battery_action = QAction("Battery: Unknown", self.context_menu)
        self.battery_action.setEnabled(False)
        self.context_menu.addAction(self.battery_action)

        self.chatmix_action = QAction("ChatMix: Unknown", self.context_menu)
        self.chatmix_action.setEnabled(False)
        self.context_menu.addAction(self.chatmix_action)

    def _create_sidetone_menu(self) -> None:
        sidetone_menu = self.context_menu.addMenu("Sidetone")
        # current_sidetone_val initially read during update_menu_state
        for text, level in sorted(
            app_config.SIDETONE_OPTIONS.items(),
            key=lambda item: item[1],
        ):
            action = QAction(text, sidetone_menu, checkable=True)
            action.setData(level)
            # Connection is a bit tricky with lambda and loop var.
            # functools.partial is safer, or ensure correct capture.
            action.triggered.connect(lambda checked=False, lvl=level: self._handle_sidetone_selected(lvl))
            sidetone_menu.addAction(action)
            self.sidetone_action_group.append(action)

    def _create_timeout_menu(self) -> None:
        timeout_menu = self.context_menu.addMenu("Inactive Timeout")
        for text, minutes in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
            action = QAction(text, timeout_menu, checkable=True)
            action.setData(minutes)
            action.triggered.connect(lambda checked=False, m=minutes: self._handle_timeout_selected(m))
            timeout_menu.addAction(action)
            self.timeout_action_group.append(action)

    def _create_eq_menu(self) -> None:
        eq_menu = self.context_menu.addMenu("Equalizer")
        # Initial check states are set in update_menu_state
        custom_curves = self.config_manager.get_all_custom_eq_curves()
        sorted_custom_names = sorted(
            custom_curves.keys(),
            key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()),
        )

        for name in sorted_custom_names:
            action = QAction(name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_CUSTOM, name))
            action.triggered.connect(lambda checked=False, data=(EQ_TYPE_CUSTOM, name): self._handle_eq_selected(data))
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)

        if custom_curves and app_config.HARDWARE_EQ_PRESET_NAMES:
            eq_menu.addSeparator()

        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            display_name = HW_PRESET_DISPLAY_PREFIX + name
            action = QAction(display_name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_HARDWARE, preset_id))
            action.triggered.connect(
                lambda checked=False, data=(EQ_TYPE_HARDWARE, preset_id): self._handle_eq_selected(data),
            )
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)

    def _create_main_control_actions(self) -> None:
        open_settings_action = QAction("Settings...", self.context_menu)
        open_settings_action.triggered.connect(self.open_settings_fn)
        self.context_menu.addAction(open_settings_action)

        self.context_menu.addSeparator()
        exit_action = QAction("Exit", self.context_menu)
        exit_action.triggered.connect(self.application_quit_fn)
        self.context_menu.addAction(exit_action)

    def update_menu_state(self, battery_text: str, chatmix_text: str) -> None:
        """Updates dynamic menu item texts and check states."""
        logger.debug("Updating menu states and texts.")
        if self.battery_action and self.battery_action.text() != battery_text:
            self.battery_action.setText(battery_text)
        if self.chatmix_action and self.chatmix_action.text() != chatmix_text:
            self.chatmix_action.setText(chatmix_text)

        current_sidetone = self.config_manager.get_last_sidetone_level()
        for action in self.sidetone_action_group:
            action.setChecked(action.data() == current_sidetone)

        current_timeout = self.config_manager.get_last_inactive_timeout()
        for action in self.timeout_action_group:
            action.setChecked(action.data() == current_timeout)

        active_eq_type = self.config_manager.get_active_eq_type()
        active_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        active_hw_id = self.config_manager.get_last_active_eq_preset_id()

        for action in self.unified_eq_action_group:
            action_data = action.data()
            if not isinstance(action_data, tuple) or len(action_data) != 2:  # Basic type check
                continue
            eq_type, identifier = action_data
            if eq_type == EQ_TYPE_CUSTOM:
                action.setChecked(active_eq_type == EQ_TYPE_CUSTOM and identifier == active_custom_name)
            elif eq_type == EQ_TYPE_HARDWARE:
                action.setChecked(active_eq_type == EQ_TYPE_HARDWARE and identifier == active_hw_id)

    def _show_message(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon, duration_ms: int) -> None:
        """Helper to show system tray messages via the parent QSystemTrayIcon."""
        if self.tray_icon_parent_widget:
            self.tray_icon_parent_widget.showMessage(title, message, icon, duration_ms)
        else:
            logger.warning("Cannot show tray message, parent_widget not set.")

    def _handle_sidetone_selected(self, level: int) -> None:
        logger.info("Setting sidetone to %s via menu.", level)
        if self.headset_service.set_sidetone_level(level):
            self.config_manager.set_last_sidetone_level(level)
            self._show_message("Success", "Sidetone set.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self._show_message(
                "Error", "Failed to set sidetone. Headset connected?", QSystemTrayIcon.MessageIcon.Warning, 2000,
            )
        self.update_menu_state(
            self.battery_action.text() if self.battery_action else "",
            self.chatmix_action.text() if self.chatmix_action else "",
        )  # Force update checks

    def _handle_timeout_selected(self, minutes: int) -> None:
        logger.info("Setting inactive timeout to %s minutes via menu.", minutes)
        if self.headset_service.set_inactive_timeout(minutes):
            self.config_manager.set_last_inactive_timeout(minutes)
            self._show_message("Success", "Inactive timeout set.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self._show_message(
                "Error", "Failed to set inactive timeout. Headset connected?", QSystemTrayIcon.MessageIcon.Warning, 2000,
            )
        self.update_menu_state(
            self.battery_action.text() if self.battery_action else "",
            self.chatmix_action.text() if self.chatmix_action else "",
        )

    def _handle_eq_selected(self, eq_data: tuple[str, Any]) -> None:
        eq_type, identifier = eq_data
        logger.info("Applying EQ from menu: Type=%s, ID/Name='%s'", eq_type, identifier)

        if not self.headset_service.is_device_connected():
            self._show_message(
                "Error", "Cannot apply EQ. Headset not connected.", QSystemTrayIcon.MessageIcon.Warning, 2000,
            )
            self.update_menu_state(
                self.battery_action.text() if self.battery_action else "",
                self.chatmix_action.text() if self.chatmix_action else "",
            )
            return

        success = False
        message = ""

        if eq_type == EQ_TYPE_CUSTOM:
            curve_name = str(identifier)
            values = self.config_manager.get_custom_eq_curve(curve_name)
            if values:
                float_values = [float(v) for v in values]
                if self.headset_service.set_eq_values(float_values):
                    self.config_manager.set_last_custom_eq_curve_name(curve_name)
                    self.config_manager.set_setting("active_eq_type", EQ_TYPE_CUSTOM)
                    message = f"Custom EQ '{curve_name}' applied."
                    success = True
                else:
                    message = f"Failed to apply custom EQ '{curve_name}' to headset."
            else:
                message = f"Custom EQ '{curve_name}' not found or has no values."
        elif eq_type == EQ_TYPE_HARDWARE:
            preset_id = int(identifier)
            if self.headset_service.set_eq_preset_id(preset_id):
                self.config_manager.set_last_active_eq_preset_id(preset_id)
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_HARDWARE)
                preset_display_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(preset_id, f"Preset {preset_id}")
                message = f"Hardware EQ '{preset_display_name}' applied."
                success = True
            else:
                message = f"Failed to apply hardware EQ preset ID {preset_id}."

        if success:
            self._show_message("Success", message, QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self._show_message("Error", message, QSystemTrayIcon.MessageIcon.Warning, 2000)

        self.update_menu_state(
            self.battery_action.text() if self.battery_action else "",
            self.chatmix_action.text() if self.chatmix_action else "",
        )
