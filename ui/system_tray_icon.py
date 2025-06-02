import logging
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QMessageBox
)
from PySide6.QtGui import QIcon, QAction, QPainter, QPixmap, QColor, QCursor, QFontMetrics, QPen, qGray, qAlpha # Added qGray, qAlpha
from PySide6.QtCore import Qt, QTimer, Slot, QRect
from typing import Optional, List, Tuple

from .. import headset_service as hs_svc
from .. import config_manager as cfg_mgr
from .. import app_config
from .settings_dialog import SettingsDialog
# Ensure EqualizerEditorWidget constants are accessible if needed, or rely on string parsing
from .equalizer_editor_widget import EQ_TYPE_CUSTOM, EQ_TYPE_HARDWARE, HW_PRESET_DISPLAY_PREFIX
from .chatmix_manager import ChatMixManager

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class SystemTrayIcon(QSystemTrayIcon):
    """Manages the system tray icon and its context menu."""

    NORMAL_REFRESH_INTERVAL_MS = 1000
    FAST_REFRESH_INTERVAL_MS = 100
    FAST_POLL_NO_CHANGE_THRESHOLD = 3 # Number of fast polls with no change before reverting to normal
    ICON_DRAW_SIZE = 32 # The size we'll use for generating our pixmap

    def __init__(self, headset_service: hs_svc.HeadsetService,
                 config_manager: cfg_mgr.ConfigManager,
                 application_quit_fn, parent=None):
        super().__init__(parent)
        logger.debug("SystemTrayIcon initializing.")
        self.headset_service = headset_service
        self.config_manager = config_manager
        self.application_quit_fn = application_quit_fn

        self.chatmix_manager = ChatMixManager(self.config_manager)
        self.settings_dialog: Optional[SettingsDialog] = None

        self._base_icon = QIcon.fromTheme("audio-headset", QIcon.fromTheme("multimedia-audio-player"))
        
        self.activated.connect(self._on_activated)

        # State for adaptive polling and change detection
        self.fast_poll_active = False
        self.fast_poll_no_change_counter = 0
        self.is_tray_view_connected = False # Tracks connection state as last seen by the tray
        self.last_known_battery_level: Optional[int] = None
        self.last_known_chatmix_value: Optional[int] = None
        
        # Variables to store current fetched values for tooltip/menu (updated in refresh_status)
        self.battery_level: Optional[int] = None
        self.chatmix_value: Optional[int] = None
        self.current_custom_eq_name_for_tooltip: Optional[str] = None
        self.current_hw_preset_name_for_tooltip: Optional[str] = None
        self.active_eq_type_for_tooltip: Optional[str] = None

        self.context_menu = QMenu()
        self.battery_action: Optional[QAction] = None
        self.chatmix_action: Optional[QAction] = None
        self.sidetone_action_group: List[QAction] = []
        self.timeout_action_group: List[QAction] = []
        self.unified_eq_action_group: List[QAction] = []

        self._populate_context_menu()
        self.setContextMenu(self.context_menu)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.setInterval(self.NORMAL_REFRESH_INTERVAL_MS) # Start with normal interval
        self.refresh_timer.start()
        logger.info(f"Refresh timer started with initial interval {self.NORMAL_REFRESH_INTERVAL_MS}ms.")

        self.refresh_status()


    def _create_status_icon(self) -> QIcon:
        # Base pixmap from the theme icon
        pixmap = self._base_icon.pixmap(self.ICON_DRAW_SIZE, self.ICON_DRAW_SIZE).copy()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.is_tray_view_connected:
            # Draw red '/'
            pen = QPen(QColor(Qt.GlobalColor.red))
            pen.setWidth(self.ICON_DRAW_SIZE // 16 or 1) # Make / line width proportional
            painter.setPen(pen)
            margin = self.ICON_DRAW_SIZE // 10 
            painter.drawLine(self.ICON_DRAW_SIZE - margin, margin, margin, self.ICON_DRAW_SIZE - margin)
        else: # Connected
            # --- Battery Indicator (Bottom Right) ---
            # Define dimensions for the small battery symbol relative to ICON_DRAW_SIZE
            # These numbers are tuned for a 32x32 icon, adjust if ICON_DRAW_SIZE changes.
            BATTERY_AREA_SIZE_W = self.ICON_DRAW_SIZE // 2 
            BATTERY_AREA_SIZE_H = self.ICON_DRAW_SIZE // 3 
            BATTERY_MARGIN_X = 2
            BATTERY_MARGIN_Y = 2
            
            battery_outer_rect_x = self.ICON_DRAW_SIZE - BATTERY_AREA_SIZE_W - BATTERY_MARGIN_X
            battery_outer_rect_y = self.ICON_DRAW_SIZE - BATTERY_AREA_SIZE_H - BATTERY_MARGIN_Y
            battery_outer_rect = QRect(battery_outer_rect_x, battery_outer_rect_y, BATTERY_AREA_SIZE_W, BATTERY_AREA_SIZE_H)

            # Actual battery body dimensions, smaller than its designated area
            body_width = int(battery_outer_rect.width() * 0.75)
            body_height = int(battery_outer_rect.height() * 0.70)
            body_x = battery_outer_rect.left() + (battery_outer_rect.width() - body_width) // 2
            body_y = battery_outer_rect.top() + (battery_outer_rect.height() - body_height) // 2
            battery_body_rect = QRect(body_x, body_y, body_width, body_height)

            # Battery cap
            cap_width = max(1, body_width // 8) 
            cap_height = max(2, body_height // 2)
            cap_rect = QRect(battery_body_rect.right(), 
                             battery_body_rect.top() + (battery_body_rect.height() - cap_height) // 2,
                             cap_width, cap_height)

            painter.setPen(QColor(Qt.GlobalColor.black))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(battery_body_rect)
            painter.drawRect(cap_rect)

            if self.battery_level is not None:
                fill_color = QColor(Qt.GlobalColor.gray)
                if self.battery_level > 70: fill_color = QColor(Qt.GlobalColor.green)
                elif self.battery_level > 25: fill_color = QColor(Qt.GlobalColor.yellow) # Changed from 30 to 25 for critical
                else: fill_color = QColor(Qt.GlobalColor.red)
                
                border_thickness = 1 
                fill_max_width = battery_body_rect.width() - (2 * border_thickness)
                if fill_max_width > 0: # Ensure positive width
                    fill_width = max(0, int(fill_max_width * (self.battery_level / 100.0)))
                    fill_rect = QRect(battery_body_rect.left() + border_thickness,
                                    battery_body_rect.top() + border_thickness,
                                    fill_width,
                                    battery_body_rect.height() - (2 * border_thickness))
                    painter.fillRect(fill_rect, fill_color)
            
            # --- ChatMix Indicator (Top-Right) ---
            # Show only if battery is not critically low (<=25%)
            if not (self.battery_level is not None and self.battery_level <= 25):
                if self.chatmix_value is not None and self.chatmix_value != 64:
                    dot_radius = self.ICON_DRAW_SIZE // 10 or 2 # Proportional dot size
                    dot_margin = self.ICON_DRAW_SIZE // 10 or 2
                    
                    chatmix_indicator_color = QColor(Qt.GlobalColor.gray) # Default
                    if self.chatmix_value < 64: # Towards Chat
                        chatmix_indicator_color = QColor(Qt.GlobalColor.cyan)
                    else: # Towards Game
                        chatmix_indicator_color = QColor(Qt.GlobalColor.green) 
                    
                    painter.setBrush(chatmix_indicator_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(self.ICON_DRAW_SIZE - (2 * dot_radius) - dot_margin, 
                                        dot_margin,
                                        2 * dot_radius, 2 * dot_radius)
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
        
        if self.is_tray_view_connected:
            if self.battery_level is not None:
                tooltip_parts.append(f"Battery: {self.battery_level}%")
            else:
                tooltip_parts.append("Battery: N/A")

            chatmix_str = self._get_chatmix_display_string_for_tray(self.chatmix_value)
            tooltip_parts.append(f"ChatMix: {chatmix_str}")

            if self.active_eq_type_for_tooltip == EQ_TYPE_CUSTOM:
                tooltip_parts.append(f"EQ: {self.current_custom_eq_name_for_tooltip}")
            elif self.active_eq_type_for_tooltip == EQ_TYPE_HARDWARE:
                tooltip_parts.append(f"EQ: {self.current_hw_preset_name_for_tooltip}")
            else:
                tooltip_parts.append("EQ: Unknown")
        else:
            tooltip_parts.append("Headset disconnected")

        new_icon = self._create_status_icon()
        current_icon_key = self.icon().cacheKey()
        new_icon_key = new_icon.cacheKey()

        if current_icon_key != new_icon_key:
            self.setIcon(new_icon)
        
        final_tooltip = "\n".join(tooltip_parts)
        if self.toolTip() != final_tooltip:
            self.setToolTip(final_tooltip)


    def _populate_context_menu(self):
        logger.debug("Populating context menu.")
        self.context_menu.clear()
        self.sidetone_action_group.clear()
        self.timeout_action_group.clear()
        self.unified_eq_action_group.clear()

        self.battery_action = QAction("Battery: Unknown", self.context_menu)
        self.battery_action.setEnabled(False)
        self.context_menu.addAction(self.battery_action)

        self.chatmix_action = QAction("ChatMix: Unknown", self.context_menu)
        self.chatmix_action.setEnabled(False)
        self.context_menu.addAction(self.chatmix_action)
        self.context_menu.addSeparator()

        sidetone_menu = self.context_menu.addMenu("Sidetone")
        current_sidetone_val_from_config = self.config_manager.get_last_sidetone_level()
        for text, level in sorted(app_config.SIDETONE_OPTIONS.items(), key=lambda item: item[1]):
            action = QAction(text, sidetone_menu, checkable=True)
            action.setData(level) 
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

        eq_menu = self.context_menu.addMenu("Equalizer")
        active_eq_type = self.config_manager.get_active_eq_type()
        active_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        active_hw_id = self.config_manager.get_last_active_eq_preset_id()

        custom_curves = self.config_manager.get_all_custom_eq_curves()
        sorted_custom_names = sorted(custom_curves.keys(), key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()))
        for name in sorted_custom_names:
            action = QAction(name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_CUSTOM, name)) 
            action.setChecked(active_eq_type == EQ_TYPE_CUSTOM and name == active_custom_name)
            action.triggered.connect(lambda checked, data=(EQ_TYPE_CUSTOM, name): self._apply_eq_from_menu(data))
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)

        if custom_curves and app_config.HARDWARE_EQ_PRESET_NAMES:
            eq_menu.addSeparator()

        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            display_name = HW_PRESET_DISPLAY_PREFIX + name
            action = QAction(display_name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_HARDWARE, preset_id)) 
            action.setChecked(active_eq_type == EQ_TYPE_HARDWARE and preset_id == active_hw_id)
            action.triggered.connect(lambda checked, data=(EQ_TYPE_HARDWARE, preset_id): self._apply_eq_from_menu(data))
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)
        
        self.context_menu.addSeparator()
        open_settings_action = QAction("Settings...", self.context_menu)
        open_settings_action.triggered.connect(self._open_settings_dialog)
        self.context_menu.addAction(open_settings_action)
        self.context_menu.addSeparator()
        exit_action = QAction("Exit", self.context_menu)
        exit_action.triggered.connect(self.application_quit_fn)
        self.context_menu.addAction(exit_action)

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
        logger.debug(f"SystemTray: Refreshing status (Interval: {self.refresh_timer.interval()}ms)...")

        # Store previous known state for change detection
        prev_battery = self.last_known_battery_level
        prev_chatmix = self.last_known_chatmix_value
        prev_connection_state = self.is_tray_view_connected

        current_is_connected = self.headset_service.is_device_connected()
        self.is_tray_view_connected = current_is_connected # Update tray's view of connection

        new_battery_text = ""
        new_chatmix_text = ""
        data_changed_while_connected = False

        if not current_is_connected:
            if prev_connection_state: # Was connected, now isn't
                logger.info("SystemTray: Headset disconnected.")
            self.battery_level = None
            self.chatmix_value = None
            new_battery_text = "Battery: Disconnected"
            new_chatmix_text = "ChatMix: Disconnected"
        else: # Is connected
            if not prev_connection_state: # Was disconnected, now is
                logger.info("SystemTray: Headset connected.")
            
            self.battery_level = self.headset_service.get_battery_level()
            self.chatmix_value = self.headset_service.get_chatmix_value()

            new_battery_text = f"Battery: {self.battery_level}%" if self.battery_level is not None else "Battery: N/A"
            chatmix_display_str = self._get_chatmix_display_string_for_tray(self.chatmix_value)
            new_chatmix_text = f"ChatMix: {chatmix_display_str}"

            if self.battery_level != prev_battery: data_changed_while_connected = True
            if self.chatmix_value != prev_chatmix: data_changed_while_connected = True
        
        # Update menu item texts if they changed
        if self.battery_action and self.battery_action.text() != new_battery_text:
            self.battery_action.setText(new_battery_text)
        if self.chatmix_action and self.chatmix_action.text() != new_chatmix_text:
            self.chatmix_action.setText(new_chatmix_text)

        # Update PipeWire volumes if connected and chatmix is valid
        if current_is_connected and self.chatmix_value is not None:
            try:
                self.chatmix_manager.update_volumes(self.chatmix_value)
            except Exception as e:
                logger.error(f"Error during chatmix_manager.update_volumes: {e}", exc_info=True)

        # Update tooltip state from ConfigManager (EQ settings)
        self.active_eq_type_for_tooltip = self.config_manager.get_active_eq_type()
        if self.active_eq_type_for_tooltip == EQ_TYPE_CUSTOM:
            self.current_custom_eq_name_for_tooltip = self.config_manager.get_last_custom_eq_curve_name()
        elif self.active_eq_type_for_tooltip == EQ_TYPE_HARDWARE:
            hw_id = self.config_manager.get_last_active_eq_preset_id()
            self.current_hw_preset_name_for_tooltip = app_config.HARDWARE_EQ_PRESET_NAMES.get(hw_id, f"Preset {hw_id}")

        self._update_menu_checks() 
        self._update_tooltip_and_icon() 
        
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.refresh_chatmix_display()
            self.settings_dialog.equalizer_widget.refresh_view()

        # Update last known state for next cycle's change detection
        self.last_known_battery_level = self.battery_level
        self.last_known_chatmix_value = self.chatmix_value

        # Adaptive timer logic
        connection_state_changed = (current_is_connected != prev_connection_state)
        
        if not current_is_connected:
            if self.refresh_timer.interval() != self.NORMAL_REFRESH_INTERVAL_MS:
                self.refresh_timer.setInterval(self.NORMAL_REFRESH_INTERVAL_MS)
                logger.debug(f"Device disconnected. Switched to normal refresh interval ({self.NORMAL_REFRESH_INTERVAL_MS}ms).")
            self.fast_poll_active = False
            self.fast_poll_no_change_counter = 0
        elif self.fast_poll_active: # Connected and was on fast poll
            if not data_changed_while_connected:
                self.fast_poll_no_change_counter += 1
                if self.fast_poll_no_change_counter >= self.FAST_POLL_NO_CHANGE_THRESHOLD:
                    self.refresh_timer.setInterval(self.NORMAL_REFRESH_INTERVAL_MS)
                    self.fast_poll_active = False
                    self.fast_poll_no_change_counter = 0
                    logger.debug(f"No change threshold reached on fast poll. Switched to normal interval ({self.NORMAL_REFRESH_INTERVAL_MS}ms).")
            else: # Data changed on fast poll
                self.fast_poll_no_change_counter = 0 # Reset counter, stay fast
        else: # Connected and was on normal poll
            if data_changed_while_connected or connection_state_changed : # Switch to fast if data changed or just reconnected
                self.refresh_timer.setInterval(self.FAST_REFRESH_INTERVAL_MS)
                self.fast_poll_active = True
                self.fast_poll_no_change_counter = 0
                logger.debug(f"State change detected. Switched to fast refresh interval ({self.FAST_REFRESH_INTERVAL_MS}ms).")
        
        logger.debug("SystemTray: Refresh status complete.")


    def _set_sidetone_from_menu(self, level: int):
        logger.info(f"Setting sidetone to {level} via menu.")
        if self.headset_service.set_sidetone_level(level): # Checks connection internally
            self.config_manager.set_last_sidetone_level(level)
            self.showMessage("Success", f"Sidetone set.", QSystemTrayIcon.MessageIcon.Information, 1500)
            self.refresh_status() 
        else:
            self.showMessage("Error", "Failed to set sidetone. Headset connected?", QSystemTrayIcon.MessageIcon.Warning, 2000)
            self._update_menu_checks()

    def _set_inactive_timeout(self, minutes: int):
        logger.info(f"Setting inactive timeout to {minutes} minutes via menu.")
        if self.headset_service.set_inactive_timeout(minutes): # Checks connection internally
            self.config_manager.set_last_inactive_timeout(minutes)
            self.showMessage("Success", f"Inactive timeout set.", QSystemTrayIcon.MessageIcon.Information, 1500)
            self.refresh_status()
        else:
            self.showMessage("Error", "Failed to set inactive timeout. Headset connected?", QSystemTrayIcon.MessageIcon.Warning, 2000)
            self._update_menu_checks()

    def _apply_eq_from_menu(self, eq_data: Tuple[str, any]):
        eq_type, identifier = eq_data
        logger.info(f"Applying EQ from menu: Type={eq_type}, ID/Name='{identifier}'")

        if not self.headset_service.is_device_connected():
            self.showMessage("Error", "Cannot apply EQ. Headset not connected.", QSystemTrayIcon.MessageIcon.Warning, 2000)
            self._update_menu_checks() # Revert if user clicked something
            return

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
        
        self.refresh_status()


    def _open_settings_dialog(self):
        logger.debug("Open Settings dialog action triggered.")
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            self.settings_dialog = SettingsDialog(self.config_manager, self.headset_service)
            self.settings_dialog.eq_applied.connect(self._handle_settings_dialog_eq_applied)
            self.settings_dialog.settings_changed.connect(self.refresh_status)
            self.settings_dialog.finished.connect(self._on_settings_dialog_closed)
            self.settings_dialog.show()
        else:
            self.settings_dialog.equalizer_widget.refresh_view()
        self.settings_dialog.activateWindow()
        self.settings_dialog.raise_()

    @Slot(str)
    def _handle_settings_dialog_eq_applied(self, eq_identifier_signal_str: str):
        logger.info(f"SystemTray received eq_applied signal from SettingsDialog: '{eq_identifier_signal_str}'")
        self.refresh_status()

    def _on_settings_dialog_closed(self, result):
        logger.debug(f"Settings dialog closed with result: {result}")
        self.refresh_status()

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
            if not vals: 
                name = app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME
                vals = self.config_manager.get_custom_eq_curve(name) or app_config.DEFAULT_EQ_CURVES["Flat"]
                self.config_manager.set_last_custom_eq_curve_name(name) 
            self.headset_service.set_eq_values(vals)
        elif active_type == EQ_TYPE_HARDWARE:
            self.headset_service.set_eq_preset_id(self.config_manager.get_last_active_eq_preset_id())
        
        logger.info("Initial headset settings applied.")
        self.refresh_status()