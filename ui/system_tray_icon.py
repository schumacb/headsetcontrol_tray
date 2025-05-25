# steelseries_tray/ui/system_tray_icon.py
import logging 
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QWidgetAction, QSlider, QLabel, QHBoxLayout, QWidget
)
from PySide6.QtGui import QIcon, QAction, QPainter, QPixmap, QColor, QCursor 
from PySide6.QtCore import Qt, QTimer, Slot
from typing import Optional, List 

from .. import headset_service as hs_svc
from .. import config_manager as cfg_mgr
from .. import app_config
from .equalizer_editor_dialog import EqualizerEditorDialog

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# SidetoneSliderAction class is no longer needed and will be removed.

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

        self.eq_editor_dialog: Optional[EqualizerEditorDialog] = None

        self._base_icon = QIcon.fromTheme("audio-headset", QIcon.fromTheme("multimedia-audio-player"))
        self.setIcon(self._base_icon)
        self.activated.connect(self._on_activated)

        self.battery_level: Optional[int] = None
        self.current_custom_eq: Optional[str] = self.config_manager.get_last_custom_eq_curve_name()
        self.current_hw_eq_preset: Optional[int] = self.config_manager.get_last_active_eq_preset_id()
        self.active_eq_type: str = self.config_manager.get_active_eq_type()
        logger.debug(f"Initial EQ state: type={self.active_eq_type}, custom='{self.current_custom_eq}', hw_preset={self.current_hw_eq_preset}")


        self.context_menu = QMenu()
        # Removed: self._sidetone_action: Optional[SidetoneSliderAction] = None
        self.sidetone_action_group: List[QAction] = [] # For checkable sidetone actions
        self._populate_context_menu()
        self.setContextMenu(self.context_menu)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(app_config.REFRESH_INTERVAL_MS) 
        logger.info(f"Refresh timer started with interval {app_config.REFRESH_INTERVAL_MS}ms.")

        self.refresh_status() # Initial refresh


    def _create_battery_icon(self, level: Optional[int]) -> QIcon:
        if level is None:
            pixmap = self._base_icon.pixmap(32, 32).copy()
            painter = QPainter(pixmap)
            painter.setPen(QColor(Qt.GlobalColor.red))
            painter.setFont(painter.font()) 
            rect = pixmap.rect()
            painter.drawText(rect.adjusted(rect.width()//2,0,0,0), Qt.AlignmentFlag.AlignCenter, "?")
            painter.end()
            return QIcon(pixmap)
        return self._base_icon 

    def _update_tooltip_and_icon(self):
        tooltip_parts = []
        is_connected = self.headset_service.is_device_connected()
        logger.debug(f"_update_tooltip_and_icon: device_connected={is_connected}, battery_level={self.battery_level}")

        if is_connected:
            if self.battery_level is not None:
                tooltip_parts.append(f"Battery: {self.battery_level}%")
                self.setIcon(self._create_battery_icon(self.battery_level))
            else:
                tooltip_parts.append("Battery: N/A (HID connected, battery not read)")
                self.setIcon(self._create_battery_icon(None)) 
            
            if self.active_eq_type == "custom":
                tooltip_parts.append(f"EQ: {self.current_custom_eq}")
            elif self.active_eq_type == "hardware":
                preset_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(self.current_hw_eq_preset, f"Preset {self.current_hw_eq_preset}")
                tooltip_parts.append(f"EQ: {preset_name}")
        else:
            tooltip_parts.append("Headset disconnected")
            self.setIcon(self._create_battery_icon(None)) 

        final_tooltip = "\n".join(tooltip_parts)
        self.setToolTip(final_tooltip)
        logger.debug(f"Tooltip set to: \"{final_tooltip.replace('\n', ' | ')}\"")
        

    def _populate_context_menu(self):
        logger.debug("Populating context menu.")
        self.context_menu.clear()
        self.sidetone_action_group.clear() # Clear previous sidetone actions

        # Battery Level
        self.battery_action = QAction("Battery: Unknown", self.context_menu)
        self.battery_action.setEnabled(False) 
        self.context_menu.addAction(self.battery_action)
        

        # Sidetone Submenu
        sidetone_menu = self.context_menu.addMenu("Sidetone")
        current_sidetone = self.config_manager.get_last_sidetone_level()
        
        # Ensure SIDETONE_OPTIONS are iterated in a sensible order, e.g., by value
        sorted_sidetone_options = sorted(app_config.SIDETONE_OPTIONS.items(), key=lambda item: item[1])

        for text, level in sorted_sidetone_options:
            action = QAction(text, sidetone_menu, checkable=True)
            action.setData(level) # Store the level in the action's data
            action.setChecked(level == current_sidetone)
            action.triggered.connect(lambda checked, l=level: self._set_sidetone_from_menu(l))
            sidetone_menu.addAction(action)
            self.sidetone_action_group.append(action)
        self.context_menu.addSeparator()


        # Inactive Timeout
        timeout_menu = self.context_menu.addMenu("Inactive Timeout")
        self.timeout_action_group: List[QAction] = [] # Ensure it's defined before use
        current_timeout = self.config_manager.get_last_inactive_timeout()
        for text, minutes in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
            action = QAction(text, timeout_menu, checkable=True)
            action.setData(minutes) # Store minutes in action's data
            action.setChecked(minutes == current_timeout)
            action.triggered.connect(lambda checked, m=minutes: self._set_inactive_timeout(m))
            timeout_menu.addAction(action)
            self.timeout_action_group.append(action)
        
        self.context_menu.addSeparator()

        # Equalizer Presets (Hardware)
        hw_eq_menu = self.context_menu.addMenu("Equalizer Presets (Hardware)")
        self.hw_eq_action_group: List[QAction] = []
        current_hw_preset_id = self.config_manager.get_last_active_eq_preset_id()
        active_is_hw = self.active_eq_type == "hardware" 

        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            action = QAction(name, hw_eq_menu, checkable=True)
            action.setData(preset_id) # Store preset_id in action's data
            action.setChecked(active_is_hw and preset_id == current_hw_preset_id)
            action.triggered.connect(lambda checked, p_id=preset_id: self._apply_hw_eq_preset(p_id))
            hw_eq_menu.addAction(action)
            self.hw_eq_action_group.append(action)

        # Tone Curves (Custom EQ)
        custom_eq_menu = self.context_menu.addMenu("Tone Curves (Custom EQ)")
        self.custom_eq_action_group: List[QAction] = []
        all_custom_curves = self.config_manager.get_all_custom_eq_curves()
        current_custom_curve_name = self.config_manager.get_last_custom_eq_curve_name()
        active_is_custom = self.active_eq_type == "custom"

        sorted_custom_names = sorted(all_custom_curves.keys(), key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()))
        for name in sorted_custom_names:
            action = QAction(name, custom_eq_menu, checkable=True)
            action.setChecked(active_is_custom and name == current_custom_curve_name)
            action.triggered.connect(lambda checked, n=name: self._apply_custom_eq_curve(n))
            custom_eq_menu.addAction(action)
            self.custom_eq_action_group.append(action)
        
        self.context_menu.addSeparator()

        # Open Equalizer Editor
        open_editor_action = QAction("Open Equalizer Editor...", self.context_menu)
        open_editor_action.triggered.connect(self._open_eq_editor)
        self.context_menu.addAction(open_editor_action)

        self.context_menu.addSeparator()

        # Refresh
        refresh_action = QAction("Refresh Status", self.context_menu)
        refresh_action.triggered.connect(self.refresh_status)
        self.context_menu.addAction(refresh_action)

        # Exit
        exit_action = QAction("Exit", self.context_menu)
        exit_action.triggered.connect(self.application_quit_fn)
        self.context_menu.addAction(exit_action)

        self._update_menu_checks()


    def _update_menu_checks(self):
        logger.debug("Updating menu checks.")
        
        # Update Sidetone checks
        current_sidetone = self.config_manager.get_last_sidetone_level()
        for action in self.sidetone_action_group:
            action.setChecked(action.data() == current_sidetone)

        # Update Inactive Timeout checks
        current_timeout = self.config_manager.get_last_inactive_timeout()
        for action in self.timeout_action_group:
            action.setChecked(action.data() == current_timeout)

        # Update HW EQ Preset checks
        current_hw_preset_id = self.config_manager.get_last_active_eq_preset_id()
        active_is_hw = self.active_eq_type == "hardware"
        for action in self.hw_eq_action_group:
            action.setChecked(active_is_hw and action.data() == current_hw_preset_id)

        # Update Custom EQ Curve checks
        current_custom_curve_name = self.config_manager.get_last_custom_eq_curve_name()
        active_is_custom = self.active_eq_type == "custom"
        for action in self.custom_eq_action_group:
            action.setChecked(active_is_custom and action.text() == current_custom_curve_name)

    @Slot()
    def refresh_status(self):
        logger.info("SystemTray: Refreshing status...")
        is_connected = self.headset_service.is_device_connected()
        if not is_connected:
            logger.warning("SystemTray: Device not connected during refresh.")
            self.battery_level = None
            self._update_tooltip_and_icon()
            if self.battery_action: self.battery_action.setText("Battery: Disconnected")
            return

        if self.battery_action: self.battery_action.setText("Battery: Updating...")
        self.battery_level = self.headset_service.get_battery_level()
        if self.battery_level is not None:
            logger.info(f"SystemTray: Battery level updated to {self.battery_level}%")
            if self.battery_action: self.battery_action.setText(f"Battery: {self.battery_level}%")
        else:
            logger.warning("SystemTray: Battery level is N/A after get_battery_level call.")
            if self.battery_action: self.battery_action.setText("Battery: N/A")

        # If HID get_sidetone_level were implemented, we could update from actual device state:
        # live_sidetone = self.headset_service.get_sidetone_level()
        # if live_sidetone is not None:
        #     logger.debug(f"SystemTray: Live sidetone {live_sidetone} obtained.")
        #     if live_sidetone != self.config_manager.get_last_sidetone_level():
        #         self.config_manager.set_last_sidetone_level(live_sidetone)
        
        self._update_tooltip_and_icon()
        self._update_menu_checks() # This will update sidetone check based on config_manager
        logger.info("SystemTray: Refresh status complete.")

    def _set_sidetone_from_menu(self, level: int):
        logger.info(f"Setting sidetone to {level} via menu.")
        if self.headset_service.set_sidetone_level(level):
            self.config_manager.set_last_sidetone_level(level)
            self.showMessage("Success", f"Sidetone set to {level}.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", "Failed to set sidetone.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks() # Update checks for all sidetone actions


    def _set_inactive_timeout(self, minutes: int):
        logger.info(f"Setting inactive timeout to {minutes} minutes via menu.")
        if self.headset_service.set_inactive_timeout(minutes):
            self.config_manager.set_last_inactive_timeout(minutes)
            self.showMessage("Success", f"Inactive timeout set to {minutes} minutes.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", "Failed to set inactive timeout.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks()

    def _apply_hw_eq_preset(self, preset_id: int):
        logger.info(f"Applying HW EQ preset ID {preset_id} via menu.")
        if self.headset_service.set_eq_preset_id(preset_id):
            self.config_manager.set_last_active_eq_preset_id(preset_id)
            self.active_eq_type = "hardware" 
            self.current_hw_eq_preset = preset_id
            self.config_manager.set_setting("active_eq_type", "hardware") 
            preset_display_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(preset_id, f"Preset {preset_id}")
            self.showMessage("Success", f"Hardware EQ Preset '{preset_display_name}' applied.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", "Failed to apply hardware EQ preset.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks()
        self._update_tooltip_and_icon()


    def _apply_custom_eq_curve(self, name: str):
        logger.info(f"Applying custom EQ curve '{name}' via menu.")
        values = self.config_manager.get_custom_eq_curve(name)
        if values and self.headset_service.set_eq_values(values):
            self.config_manager.set_last_custom_eq_curve_name(name)
            self.active_eq_type = "custom" 
            self.current_custom_eq = name
            self.config_manager.set_setting("active_eq_type", "custom") 
            self.showMessage("Success", f"Custom EQ curve '{name}' applied.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", f"Failed to apply custom EQ curve '{name}'.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks()
        self._update_tooltip_and_icon()

    def _open_eq_editor(self):
        logger.debug("Open EQ editor action triggered.")
        if self.eq_editor_dialog is None or not self.eq_editor_dialog.isVisible():
            self.eq_editor_dialog = EqualizerEditorDialog(self.config_manager, self.headset_service)
            self.eq_editor_dialog.eq_applied.connect(self._handle_eq_editor_apply_custom)
            self.eq_editor_dialog.finished.connect(self._on_eq_editor_closed)
            self.eq_editor_dialog.show()
            self.eq_editor_dialog.activateWindow()
            self.eq_editor_dialog.raise_()
        else:
            self.eq_editor_dialog.activateWindow()
            self.eq_editor_dialog.raise_()
            
    @Slot(str)
    def _handle_eq_editor_apply_custom(self, curve_name: str):
        """Handles when an EQ is applied from the editor (either selection or slider change)."""
        logger.info(f"SystemTray received eq_applied: '{curve_name}'")
        self.current_custom_eq = curve_name 
        
        # Ensure app state reflects that a custom EQ is now primary
        if self.active_eq_type != "custom" or self.config_manager.get_last_custom_eq_curve_name() != curve_name:
             self.active_eq_type = "custom"
             # The editor itself should be responsible for setting the 'last_custom_eq_curve_name'
             # and 'active_eq_type' in config_manager when a curve is applied or saved.
             # This handler primarily updates the tray's UI.
             # self.config_manager.set_last_custom_eq_curve_name(curve_name)
             # self.config_manager.set_setting("active_eq_type", "custom")

        self._update_menu_checks()
        self._update_tooltip_and_icon()


    def _on_eq_editor_closed(self, result):
        logger.debug(f"EQ editor closed with result: {result}")
        self._populate_context_menu() 
        self.refresh_status() 

    def _on_activated(self, reason):
        logger.debug(f"Tray icon activated, reason: {reason}")
        if reason == QSystemTrayIcon.ActivationReason.Trigger: 
            self.context_menu.popup(QCursor.pos()) 
        elif reason == QSystemTrayIcon.ActivationReason.Context: 
            pass


    def set_initial_headset_settings(self):
        """Applies persisted settings to the headset on startup."""
        logger.info("Attempting to apply initial headset settings.")
        if not self.headset_service.is_device_connected():
            logger.warning("Cannot apply initial settings, device not connected.")
            return

        sidetone = self.config_manager.get_last_sidetone_level()
        logger.debug(f"Setting initial sidetone: {sidetone}")
        self.headset_service.set_sidetone_level(sidetone)
        # Sidetone UI check will be updated via _update_menu_checks in refresh_status


        timeout = self.config_manager.get_last_inactive_timeout()
        logger.debug(f"Setting initial inactive timeout: {timeout}")
        self.headset_service.set_inactive_timeout(timeout)

        persisted_active_eq_type = self.config_manager.get_active_eq_type()
        self.active_eq_type = persisted_active_eq_type 
        logger.debug(f"Setting initial EQ. Type: {persisted_active_eq_type}")
        if persisted_active_eq_type == "custom":
            curve_name = self.config_manager.get_last_custom_eq_curve_name()
            self.current_custom_eq = curve_name 
            logger.debug(f"  Custom curve name: '{curve_name}'")
            values = self.config_manager.get_custom_eq_curve(curve_name)
            if values:
                self.headset_service.set_eq_values(values)
            else: 
                logger.warning(f"  Custom curve '{curve_name}' not found, applying Flat.")
                flat_values = app_config.DEFAULT_EQ_CURVES.get("Flat", [0]*10)
                self.headset_service.set_eq_values(flat_values)
                self.config_manager.set_last_custom_eq_curve_name("Flat")
                self.config_manager.set_setting("active_eq_type", "custom") 
                self.current_custom_eq = "Flat"
                self.active_eq_type = "custom"


        elif persisted_active_eq_type == "hardware":
            preset_id = self.config_manager.get_last_active_eq_preset_id()
            self.current_hw_eq_preset = preset_id 
            logger.debug(f"  Hardware preset ID: {preset_id}")
            self.headset_service.set_eq_preset_id(preset_id)
        
        logger.info("Initial headset settings applied.")
        self.refresh_status() 