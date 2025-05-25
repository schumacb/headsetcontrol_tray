# steelseries_tray/ui/system_tray_icon.py
import logging
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QMessageBox
)
from PySide6.QtGui import QIcon, QAction, QPainter, QPixmap, QColor, QCursor
from PySide6.QtCore import Qt, QTimer, Slot
from typing import Optional, List, Tuple

from .. import headset_service as hs_svc
from .. import config_manager as cfg_mgr
from .. import app_config
from .settings_dialog import SettingsDialog
# Ensure EqualizerEditorWidget constants are accessible if needed, or rely on string parsing
from .equalizer_editor_widget import EQ_TYPE_CUSTOM, EQ_TYPE_HARDWARE, HW_PRESET_DISPLAY_PREFIX


logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class SystemTrayIcon(QSystemTrayIcon):
    """Manages the system tray icon and its context menu."""

    def __init__(self, headset_service: hs_svc.HeadsetService,
                 config_manager: cfg_mgr.ConfigManager,
                 application_quit_fn, parent=None):
        super().__init__(parent)
        logger.debug("SystemTrayIcon initializing.")
        self.headset_service = headset_service
        self.config_manager = config_manager
        self.application_quit_fn = application_quit_fn

        self.settings_dialog: Optional[SettingsDialog] = None

        self._base_icon = QIcon.fromTheme("audio-headset", QIcon.fromTheme("multimedia-audio-player"))
        self.setIcon(self._base_icon)
        self.activated.connect(self._on_activated)

        # These will be updated by refresh_status from config_manager
        self.battery_level: Optional[int] = None
        self.chatmix_value: Optional[int] = None
        self.current_custom_eq_name_for_tooltip: Optional[str] = None # Specific for tooltip
        self.current_hw_preset_name_for_tooltip: Optional[str] = None # Specific for tooltip
        self.active_eq_type_for_tooltip: Optional[str] = None # Specific for tooltip


        self.context_menu = QMenu()
        self.battery_action: Optional[QAction] = None
        self.chatmix_action: Optional[QAction] = None
        self.sidetone_action_group: List[QAction] = []
        self.timeout_action_group: List[QAction] = []
        # The EQ action groups will now refer to items in the unified combo
        self.unified_eq_action_group: List[QAction] = []


        self._populate_context_menu() # Initial population
        self.setContextMenu(self.context_menu)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(app_config.REFRESH_INTERVAL_MS)
        logger.info(f"Refresh timer started with interval {app_config.REFRESH_INTERVAL_MS}ms.")

        self.refresh_status() # Initial full refresh


    def _create_battery_icon(self, level: Optional[int]) -> QIcon:
        if level is None:
            pixmap = self._base_icon.pixmap(32, 32).copy()
            painter = QPainter(pixmap)
            painter.setPen(QColor(Qt.GlobalColor.red))
            font = painter.font(); font.setBold(True); font.setPointSize(font.pointSize() + 4)
            painter.setFont(font)
            rect = pixmap.rect()
            painter.drawText(rect.adjusted(2,2,-2,-2), Qt.AlignmentFlag.AlignCenter, "?")
            painter.end()
            return QIcon(pixmap)

        pixmap = self._base_icon.pixmap(32, 32).copy()
        painter = QPainter(pixmap)
        if level > 70: color = QColor(Qt.GlobalColor.green)
        elif level > 30: color = QColor(Qt.GlobalColor.yellow)
        else: color = QColor(Qt.GlobalColor.red)
        painter.setPen(color)
        font = painter.font(); font.setPointSize(font.pointSize() - 2)
        painter.setFont(font)
        text_rect = pixmap.rect().adjusted(pixmap.width() // 2, pixmap.height() // 2, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, str(level))
        painter.end()
        return QIcon(pixmap)

    def _get_chatmix_display_string_for_tray(self, chatmix_val: Optional[int]) -> str:
        if chatmix_val is None: return "N/A"
        percentage = round((chatmix_val / 128) * 100)
        if chatmix_val == 0: return f"Chat ({percentage}%)"
        if chatmix_val == 64: return f"Balanced ({percentage}%)"
        if chatmix_val == 128: return f"Game ({percentage}%)"
        return f"{chatmix_val} ({percentage}%)"


    def _update_tooltip_and_icon(self):
        tooltip_parts = []
        is_connected = self.headset_service.is_device_connected()

        if is_connected:
            if self.battery_level is not None:
                tooltip_parts.append(f"Battery: {self.battery_level}%")
                self.setIcon(self._create_battery_icon(self.battery_level))
            else:
                tooltip_parts.append("Battery: N/A")
                self.setIcon(self._create_battery_icon(None))

            chatmix_str = self._get_chatmix_display_string_for_tray(self.chatmix_value)
            tooltip_parts.append(f"ChatMix: {chatmix_str}")

            # Use the tooltip-specific state variables updated by refresh_status
            if self.active_eq_type_for_tooltip == EQ_TYPE_CUSTOM:
                tooltip_parts.append(f"EQ: {self.current_custom_eq_name_for_tooltip}")
            elif self.active_eq_type_for_tooltip == EQ_TYPE_HARDWARE:
                tooltip_parts.append(f"EQ: {self.current_hw_preset_name_for_tooltip}")
            else:
                tooltip_parts.append("EQ: Unknown")
        else:
            tooltip_parts.append("Headset disconnected")
            self.setIcon(self._create_battery_icon(None))

        final_tooltip = "\n".join(tooltip_parts)
        self.setToolTip(final_tooltip)
        logger.debug(f"Tooltip set to: \"{final_tooltip.replace('\n', ' | ')}\"")


    def _populate_context_menu(self):
        logger.debug("Populating context menu.")
        self.context_menu.clear()
        self.sidetone_action_group.clear()
        self.timeout_action_group.clear()
        self.unified_eq_action_group.clear() # Use the new unified group

        self.battery_action = QAction("Battery: Unknown", self.context_menu)
        self.battery_action.setEnabled(False)
        self.context_menu.addAction(self.battery_action)

        self.chatmix_action = QAction("ChatMix: Unknown", self.context_menu)
        self.chatmix_action.setEnabled(False)
        self.context_menu.addAction(self.chatmix_action)
        self.context_menu.addSeparator()

        sidetone_menu = self.context_menu.addMenu("Sidetone")
        # Sidetone options (from app_config.SIDETONE_OPTIONS) are still relevant for the menu
        current_sidetone_val_from_config = self.config_manager.get_last_sidetone_level()
        for text, level in sorted(app_config.SIDETONE_OPTIONS.items(), key=lambda item: item[1]):
            action = QAction(text, sidetone_menu, checkable=True)
            action.setData(level) # Store level
            action.setChecked(level == current_sidetone_val_from_config)
            action.triggered.connect(lambda checked, l=level: self._set_sidetone_from_menu(l))
            sidetone_menu.addAction(action)
            self.sidetone_action_group.append(action)


        timeout_menu = self.context_menu.addMenu("Inactive Timeout")
        current_timeout_val_from_config = self.config_manager.get_last_inactive_timeout()
        for text, minutes in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
            action = QAction(text, timeout_menu, checkable=True)
            action.setData(minutes)
            action.setChecked(minutes == current_timeout_val_from_config)
            action.triggered.connect(lambda checked, m=minutes: self._set_inactive_timeout(m))
            timeout_menu.addAction(action)
            self.timeout_action_group.append(action)

        # Unified Equalizer Menu
        eq_menu = self.context_menu.addMenu("Equalizer")
        
        # Get current active EQ from config manager to determine checks
        active_eq_type = self.config_manager.get_active_eq_type()
        active_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        active_hw_id = self.config_manager.get_last_active_eq_preset_id()

        # Add Custom EQ Curves
        custom_curves = self.config_manager.get_all_custom_eq_curves()
        sorted_custom_names = sorted(custom_curves.keys(), key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()))
        for name in sorted_custom_names:
            action = QAction(name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_CUSTOM, name)) # Store type and name
            action.setChecked(active_eq_type == EQ_TYPE_CUSTOM and name == active_custom_name)
            action.triggered.connect(lambda checked, data=(EQ_TYPE_CUSTOM, name): self._apply_eq_from_menu(data))
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)

        if custom_curves and app_config.HARDWARE_EQ_PRESET_NAMES:
            eq_menu.addSeparator()

        # Add Hardware Presets
        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            display_name = HW_PRESET_DISPLAY_PREFIX + name
            action = QAction(display_name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_HARDWARE, preset_id)) # Store type and ID
            action.setChecked(active_eq_type == EQ_TYPE_HARDWARE and preset_id == active_hw_id)
            action.triggered.connect(lambda checked, data=(EQ_TYPE_HARDWARE, preset_id): self._apply_eq_from_menu(data))
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)
        
        self.context_menu.addSeparator()
        open_settings_action = QAction("Settings...", self.context_menu)
        open_settings_action.triggered.connect(self._open_settings_dialog)
        self.context_menu.addAction(open_settings_action)
        self.context_menu.addSeparator()
        refresh_action = QAction("Refresh Status", self.context_menu)
        refresh_action.triggered.connect(self.refresh_status)
        self.context_menu.addAction(refresh_action)
        exit_action = QAction("Exit", self.context_menu)
        exit_action.triggered.connect(self.application_quit_fn)
        self.context_menu.addAction(exit_action)
        # No need to call _update_menu_checks here, refresh_status does it.

    def _update_menu_checks(self):
        logger.debug("Updating menu checks based on ConfigManager.")
        current_sidetone = self.config_manager.get_last_sidetone_level()
        for action in self.sidetone_action_group: action.setChecked(action.data() == current_sidetone)
        
        current_timeout = self.config_manager.get_last_inactive_timeout()
        for action in self.timeout_action_group: action.setChecked(action.data() == current_timeout)
        
        active_eq_type = self.config_manager.get_active_eq_type()
        active_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        active_hw_id = self.config_manager.get_last_active_eq_preset_id()

        for action in self.unified_eq_action_group:
            action_data = action.data()
            if not action_data: continue
            eq_type, identifier = action_data
            if eq_type == EQ_TYPE_CUSTOM:
                action.setChecked(active_eq_type == EQ_TYPE_CUSTOM and identifier == active_custom_name)
            elif eq_type == EQ_TYPE_HARDWARE:
                action.setChecked(active_eq_type == EQ_TYPE_HARDWARE and identifier == active_hw_id)


    @Slot()
    def refresh_status(self):
        logger.info("SystemTray: Refreshing status...")
        is_connected = self.headset_service.is_device_connected()

        if not is_connected:
            logger.warning("SystemTray: Device not connected during refresh.")
            self.battery_level = None; self.chatmix_value = None
            if self.battery_action: self.battery_action.setText("Battery: Disconnected")
            if self.chatmix_action: self.chatmix_action.setText("ChatMix: Disconnected")
        else:
            if self.battery_action: self.battery_action.setText("Battery: Updating...")
            self.battery_level = self.headset_service.get_battery_level()
            if self.battery_action: self.battery_action.setText(f"Battery: {self.battery_level}%" if self.battery_level is not None else "Battery: N/A")

            if self.chatmix_action: self.chatmix_action.setText("ChatMix: Updating...")
            self.chatmix_value = self.headset_service.get_chatmix_value()
            chatmix_display_str = self._get_chatmix_display_string_for_tray(self.chatmix_value)
            if self.chatmix_action: self.chatmix_action.setText(f"ChatMix: {chatmix_display_str}")
        
        # Update tooltip-specific state from ConfigManager
        self.active_eq_type_for_tooltip = self.config_manager.get_active_eq_type()
        if self.active_eq_type_for_tooltip == EQ_TYPE_CUSTOM:
            self.current_custom_eq_name_for_tooltip = self.config_manager.get_last_custom_eq_curve_name()
        elif self.active_eq_type_for_tooltip == EQ_TYPE_HARDWARE:
            hw_id = self.config_manager.get_last_active_eq_preset_id()
            self.current_hw_preset_name_for_tooltip = app_config.HARDWARE_EQ_PRESET_NAMES.get(hw_id, f"Preset {hw_id}")

        self._update_menu_checks() # Update menu checks based on config
        self._update_tooltip_and_icon() # Update tooltip based on internal state
        
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.refresh_chatmix_display()
            # Crucially, refresh the EQ editor if the dialog is open, as tray actions might change EQ
            self.settings_dialog.equalizer_widget.refresh_view()

        logger.info("SystemTray: Refresh status complete.")

    def _set_sidetone_from_menu(self, level: int):
        logger.info(f"Setting sidetone to {level} via menu.")
        if self.headset_service.set_sidetone_level(level):
            self.config_manager.set_last_sidetone_level(level)
            self.showMessage("Success", f"Sidetone set.", QSystemTrayIcon.MessageIcon.Information, 1500)
            self.refresh_status() 
        else:
            self.showMessage("Error", "Failed to set sidetone.", QSystemTrayIcon.MessageIcon.Warning, 1500)
            self._update_menu_checks() # Revert check if failed

    def _set_inactive_timeout(self, minutes: int):
        logger.info(f"Setting inactive timeout to {minutes} minutes via menu.")
        if self.headset_service.set_inactive_timeout(minutes):
            self.config_manager.set_last_inactive_timeout(minutes)
            self.showMessage("Success", f"Inactive timeout set.", QSystemTrayIcon.MessageIcon.Information, 1500)
            self.refresh_status()
        else:
            self.showMessage("Error", "Failed to set inactive timeout.", QSystemTrayIcon.MessageIcon.Warning, 1500)
            self._update_menu_checks() # Revert check

    def _apply_eq_from_menu(self, eq_data: Tuple[str, any]):
        eq_type, identifier = eq_data
        logger.info(f"Applying EQ from menu: Type={eq_type}, ID/Name='{identifier}'")

        success = False
        message = ""

        if eq_type == EQ_TYPE_CUSTOM:
            curve_name = str(identifier)
            values = self.config_manager.get_custom_eq_curve(curve_name)
            if values and self.headset_service.set_eq_values(values):
                self.config_manager.set_last_custom_eq_curve_name(curve_name)
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_CUSTOM)
                message = f"Custom EQ '{curve_name}' applied."
                success = True
            else: message = f"Failed to apply custom EQ '{curve_name}'."
        
        elif eq_type == EQ_TYPE_HARDWARE:
            preset_id = int(identifier)
            if self.headset_service.set_eq_preset_id(preset_id):
                self.config_manager.set_last_active_eq_preset_id(preset_id)
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_HARDWARE)
                preset_display_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(preset_id, f"Preset {preset_id}")
                message = f"Hardware EQ '{preset_display_name}' applied."
                success = True
            else: message = f"Failed to apply hardware EQ preset ID {preset_id}."

        if success:
            self.showMessage("Success", message, QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", message, QSystemTrayIcon.MessageIcon.Warning, 1500)
        
        self.refresh_status() # This will update menu checks and tooltip


    def _open_settings_dialog(self):
        logger.debug("Open Settings dialog action triggered.")
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            self.settings_dialog = SettingsDialog(self.config_manager, self.headset_service)
            self.settings_dialog.eq_applied.connect(self._handle_settings_dialog_eq_applied)
            self.settings_dialog.settings_changed.connect(self.refresh_status)
            self.settings_dialog.finished.connect(self._on_settings_dialog_closed)
            self.settings_dialog.show()
        else:
            # If dialog is already open, ensure its EQ section is up-to-date with tray changes
            self.settings_dialog.equalizer_widget.refresh_view() # Important!
        self.settings_dialog.activateWindow()
        self.settings_dialog.raise_()

    @Slot(str)
    def _handle_settings_dialog_eq_applied(self, eq_identifier_signal_str: str):
        # This signal comes from EqualizerEditorWidget, which already updated ConfigManager
        logger.info(f"SystemTray received eq_applied signal from SettingsDialog: '{eq_identifier_signal_str}'")
        self.refresh_status() # Refresh tray state from ConfigManager

    def _on_settings_dialog_closed(self, result):
        logger.debug(f"Settings dialog closed with result: {result}")
        self.refresh_status() # Ensure tray reflects any final changes

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: self._open_settings_dialog()
        elif reason == QSystemTrayIcon.ActivationReason.Context: self.context_menu.popup(QCursor.pos())

    def set_initial_headset_settings(self):
        logger.info("Attempting to apply initial headset settings.")
        if not self.headset_service.is_device_connected():
            logger.warning("Cannot apply initial settings, device not connected."); return

        self.headset_service.set_sidetone_level(self.config_manager.get_last_sidetone_level())
        self.headset_service.set_inactive_timeout(self.config_manager.get_last_inactive_timeout())

        active_type = self.config_manager.get_active_eq_type()
        if active_type == EQ_TYPE_CUSTOM:
            name = self.config_manager.get_last_custom_eq_curve_name()
            vals = self.config_manager.get_custom_eq_curve(name)
            if not vals: # Fallback if stored curve name somehow invalid
                name = app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME
                vals = self.config_manager.get_custom_eq_curve(name) or app_config.DEFAULT_EQ_CURVES["Flat"]
                self.config_manager.set_last_custom_eq_curve_name(name) # Persist fallback
            self.headset_service.set_eq_values(vals)
        elif active_type == EQ_TYPE_HARDWARE:
            self.headset_service.set_eq_preset_id(self.config_manager.get_last_active_eq_preset_id())
        
        logger.info("Initial headset settings applied.")
        self.refresh_status() # Full update of tray state after initial apply