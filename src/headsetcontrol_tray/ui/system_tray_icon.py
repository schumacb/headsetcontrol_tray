"""
Manages the system tray icon, its context menu, and status updates by coordinating
various helper components.
"""

from collections.abc import Callable
import logging

from PySide6.QtCore import Slot
from PySide6.QtGui import QCursor, QIcon  # QCursor needed for _on_activated
from PySide6.QtWidgets import QSystemTrayIcon, QWidget

from headsetcontrol_tray import app_config
from headsetcontrol_tray import config_manager as cfg_mgr
from headsetcontrol_tray import headset_service as hs_svc

from .chatmix_manager import ChatMixManager  # Still needed for direct ChatMix updates
from .equalizer_editor_widget import EQ_TYPE_CUSTOM, EQ_TYPE_HARDWARE  # For set_initial_headset_settings

# New component imports
from .headset_polling_service import HeadsetPollingService
from .settings_dialog import SettingsDialog
from .tray_icon_painter import TrayIconPainter
from .tray_menu_manager import TrayMenuManager
from .tray_tooltip_manager import TrayTooltipManager

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class SystemTrayIcon(QSystemTrayIcon):
    """
    Coordinates components to manage the system tray icon, its context menu,
    and status updates.
    """

    def __init__(
        self,
        headset_service: hs_svc.HeadsetService,
        config_manager: cfg_mgr.ConfigManager,
        application_quit_fn: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        logger.debug("SystemTrayIcon initializing.")
        self.headset_service = headset_service
        self.config_manager = config_manager
        self.application_quit_fn = application_quit_fn

        # Initialize helper components
        base_theme_icon = QIcon.fromTheme("audio-headset", QIcon.fromTheme("multimedia-audio-player"))
        self.icon_painter = TrayIconPainter(base_icon=base_theme_icon)
        self.tooltip_manager = TrayTooltipManager(config_manager_getter=lambda: self.config_manager)

        # TrayMenuManager needs a reference to this SystemTrayIcon instance to show messages
        self.menu_manager = TrayMenuManager(
            headset_service=self.headset_service,
            config_manager=self.config_manager,
            tray_icon_parent_widget=self,  # Pass self
            application_quit_fn=self.application_quit_fn,
            open_settings_fn=self._open_settings_dialog,
        )
        self.setContextMenu(self.menu_manager.get_context_menu())

        self.polling_service = HeadsetPollingService(headset_service=self.headset_service, parent=self)
        self.polling_service.status_updated.connect(self._on_status_updated)

        # Still need ChatMixManager for direct volume updates based on polling
        self.chatmix_manager = ChatMixManager(self.config_manager)
        self.settings_dialog: SettingsDialog | None = None

        self.activated.connect(self._on_activated)

        # Initial state fetch and UI update
        self.polling_service.start()  # This will trigger an initial _on_status_updated
        self.set_initial_headset_settings()
        logger.info("SystemTrayIcon initialized and polling service started.")

    @Slot(dict)
    def _on_status_updated(self, status_data: dict) -> None:
        """
        Handles status updates from the HeadsetPollingService.
        Updates the icon, tooltip, and menu.
        """
        logger.debug("Received status update from polling service: %s", status_data)

        is_connected = status_data.get(HeadsetPollingService.KEY_IS_CONNECTED, False)
        battery_level = status_data.get(HeadsetPollingService.KEY_BATTERY_LEVEL)
        battery_status_text = status_data.get(HeadsetPollingService.KEY_BATTERY_STATUS_TEXT)
        chatmix_value = status_data.get(HeadsetPollingService.KEY_CHATMIX_VALUE)

        # Update Icon
        new_icon = self.icon_painter.create_status_icon(
            is_connected=is_connected,
            battery_level=battery_level,
            battery_status_text=battery_status_text,
            chatmix_value=chatmix_value,
        )
        current_icon_key = self.icon().cacheKey() if self.icon() else -1
        new_icon_key = new_icon.cacheKey()
        if current_icon_key != new_icon_key:
            self.setIcon(new_icon)

        # Update Tooltip
        # Fetch EQ info directly from config_manager for tooltip
        active_eq_type = self.config_manager.get_active_eq_type()
        current_custom_eq_name = None
        current_hw_preset_id = None
        if active_eq_type == EQ_TYPE_CUSTOM:
            current_custom_eq_name = self.config_manager.get_last_custom_eq_curve_name()
        elif active_eq_type == EQ_TYPE_HARDWARE:
            current_hw_preset_id = self.config_manager.get_last_active_eq_preset_id()

        new_tooltip = self.tooltip_manager.get_tooltip(
            is_connected=is_connected,
            battery_level=battery_level,
            battery_status_text=battery_status_text,
            chatmix_value=chatmix_value,
            active_eq_type=active_eq_type,
            current_custom_eq_name=current_custom_eq_name,
            current_hw_preset_id=current_hw_preset_id,
        )
        if self.toolTip() != new_tooltip:
            self.setToolTip(new_tooltip)

        # Update Menu (texts and checks)
        # The menu manager needs formatted battery/chatmix text for its status actions
        # We can reuse the tooltip manager's formatting logic or have menu manager format itself.
        # For now, let's pass basic data and let menu_manager format if needed, or pass formatted.
        # Re-using tooltip logic for simplicity:
        battery_tooltip_part = "Battery: Disconnected"
        chatmix_tooltip_part = "ChatMix: Disconnected"
        if is_connected:
            # Simplified for menu status line, full details in tooltip
            battery_tooltip_part = f"Battery: {battery_level}%" if battery_level is not None else "Battery: N/A"
            if battery_status_text == "BATTERY_CHARGING":
                battery_tooltip_part += " (Charging)"

            chatmix_percent = "N/A"
            if chatmix_value is not None:
                chatmix_percent = f"{round((chatmix_value / float(app_config.CHATMIX_VALUE_FULL_GAME)) * 100)}%"  # CHATMIX_VALUE_FULL_GAME from app_config
            chatmix_tooltip_part = f"ChatMix: {chatmix_percent}"

        self.menu_manager.update_menu_state(battery_tooltip_part, chatmix_tooltip_part)

        # Update ChatMixManager if headset is connected
        if is_connected and chatmix_value is not None:
            try:
                self.chatmix_manager.update_volumes(chatmix_value)
            except Exception as e:  # More specific exception if possible
                logger.exception("Error during chatmix_manager.update_volumes: %s", e)

        # Refresh settings dialog if visible
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.refresh_chatmix_display()  # This method needs to exist on SettingsDialog
            self.settings_dialog.equalizer_widget.refresh_view()

    def _open_settings_dialog(self) -> None:
        logger.debug("Open Settings dialog action triggered.")
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            # Create dialog if it doesn't exist or was closed
            self.settings_dialog = SettingsDialog(
                self.config_manager,
                self.headset_service,
            )
            # Connect signals from settings dialog
            self.settings_dialog.eq_applied.connect(self._handle_settings_dialog_change)
            self.settings_dialog.settings_changed.connect(self._handle_settings_dialog_change)
            self.settings_dialog.finished.connect(self._on_settings_dialog_closed)
            self.settings_dialog.show()
        else:
            # If dialog exists and is visible, just bring it to front
            self.settings_dialog.activateWindow()
            self.settings_dialog.raise_()
            # Ensure its view is current, e.g., if EQ was changed via menu
            self.settings_dialog.equalizer_widget.refresh_view()

    @Slot()  # Argument type can be more specific if SettingsDialog emits typed data
    def _handle_settings_dialog_change(self) -> None:
        """Handles signals from SettingsDialog indicating a potential state change."""
        logger.info("SystemTray received change signal from SettingsDialog.")
        # Force a poll and UI update by triggering the polling service's _poll_status
        # This ensures consistency as polling_service is the source of truth for UI updates
        self.polling_service._poll_status()  # pylint: disable=protected-access
        # Also, immediately update menu checks as config might have changed
        # The _poll_status will call menu_manager.update_menu_state eventually,
        # but direct call ensures immediate reflection of config changes from settings dialog.
        # This might be redundant if _poll_status is quick enough.
        # For now, let polling service handle it to keep single flow.

    def _on_settings_dialog_closed(self, result: int) -> None:
        logger.debug("Settings dialog closed with result: %s", result)
        # No specific action needed other than what _handle_settings_dialog_change might do
        # if changes were accepted. The polling service will continue to update.

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Typically left click
            self._open_settings_dialog()
        elif reason == QSystemTrayIcon.ActivationReason.Context:  # Typically right click
            # Menu is managed by menu_manager, ensure it's shown at cursor
            self.context_menu.popup(QCursor.pos())

    def set_initial_headset_settings(self) -> None:
        """Applies stored settings to the headset upon application startup."""
        logger.info("Attempting to apply initial headset settings.")
        if not self.headset_service.is_device_connected():
            # Try to connect first if polling service hasn't established it yet
            # This might be redundant if polling_service.start() does an immediate poll
            # that successfully connects.
            if not self.polling_service._is_currently_connected:  # pylint: disable=protected-access
                logger.warning("Cannot apply initial settings, device not connected by polling service yet.")
                return

        # Ensure we use the most recent connection status from polling service
        if not self.polling_service._is_currently_connected:  # pylint: disable=protected-access
            logger.warning("Cannot apply initial settings, polling service reports device not connected.")
            return

        logger.info("Applying initial sidetone and timeout settings.")
        self.headset_service.set_sidetone_level(
            self.config_manager.get_last_sidetone_level(),
        )
        self.headset_service.set_inactive_timeout(
            self.config_manager.get_last_inactive_timeout(),
        )

        logger.info("Applying initial EQ settings.")
        active_type = self.config_manager.get_active_eq_type()
        if active_type == EQ_TYPE_CUSTOM:
            name = self.config_manager.get_last_custom_eq_curve_name()
            vals = self.config_manager.get_custom_eq_curve(name)
            if not vals:  # Fallback to default flat if stored name is invalid
                logger.warning("Initial custom EQ '%s' not found, falling back to default Flat.", name)
                name = app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME  # Should be "Flat" or similar
                # Ensure default "Flat" exists or use a hardcoded safe default
                vals = (
                    self.config_manager.get_custom_eq_curve(name)
                    or app_config.DEFAULT_EQ_CURVES.get(app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME)
                    or [0.0] * app_config.NUM_EQ_BANDS
                )  # Absolute fallback
                self.config_manager.set_last_custom_eq_curve_name(name)

            if vals:  # If vals could be resolved
                float_vals = [float(v) for v in vals]
                self.headset_service.set_eq_values(float_vals)
            else:
                logger.error("Could not resolve any EQ values for initial custom EQ.")

        elif active_type == EQ_TYPE_HARDWARE:
            self.headset_service.set_eq_preset_id(
                self.config_manager.get_last_active_eq_preset_id(),
            )
        else:
            logger.warning("Unknown active_eq_type '%s' during initial settings.", active_type)

        logger.info("Initial headset settings application attempt finished.")
        # Trigger a refresh to ensure UI reflects these settings
        self.polling_service._poll_status()  # pylint: disable=protected-access

    def cleanup(self) -> None:
        """Clean up resources, like stopping the polling service."""
        logger.info("SystemTrayIcon cleaning up.")
        self.polling_service.stop()


# Ensure application_quit_fn in __init__ is called via the menu manager.
# The SystemTrayIcon's quit_application method is no longer needed if
# the application_quit_fn is passed directly to the MenuManager.
# If SystemTrayIcon needs to do its own cleanup before app quit,
# then it should provide a method that MenuManager calls, which then calls application_quit_fn.
# For now, direct pass is simpler.
