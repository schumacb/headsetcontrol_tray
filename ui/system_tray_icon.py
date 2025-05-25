# steelseries_tray/ui/system_tray_icon.py
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QWidgetAction, QSlider, QLabel, QHBoxLayout, QWidget
)
from PySide6.QtGui import QIcon, QAction, QPainter, QPixmap, QColor
from PySide6.QtCore import Qt, QTimer, Slot
from typing import Optional, List # Added Optional and List

from .. import headset_service as hs_svc
from .. import config_manager as cfg_mgr
from .. import app_config
from .equalizer_editor_dialog import EqualizerEditorDialog

class SidetoneSliderAction(QWidgetAction):
    """Custom QWidgetAction for a sidetone slider in the menu."""
    def __init__(self, parent, headset_service: hs_svc.HeadsetService, config_manager: cfg_mgr.ConfigManager):
        super().__init__(parent)
        self.headset_service = headset_service
        self.config_manager = config_manager
        
        self.widget = QWidget()
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(5,2,5,2) # Smaller margins

        self.label = QLabel("Sidetone:")
        layout.addWidget(self.label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 128)
        self.slider.setTickInterval(16)
        self.slider.setMinimumWidth(100) # Ensure slider is usable
        
        # Get initial sidetone value
        initial_sidetone = config_manager.get_last_sidetone_level()
        # Try to get live value if possible (and if headset_service supports it quickly)
        live_sidetone = self.headset_service.get_sidetone_level() # This is a placeholder
        if live_sidetone is not None:
            initial_sidetone = live_sidetone
        self.slider.setValue(initial_sidetone)
        
        self.slider.valueChanged.connect(self._slider_value_changed_live)
        self.slider.sliderReleased.connect(self._slider_released) # Persist on release
        layout.addWidget(self.slider)

        self.value_label = QLabel(str(initial_sidetone))
        self.value_label.setMinimumWidth(25) # Space for 3 digits
        layout.addWidget(self.value_label)
        
        self.widget.setLayout(layout)
        self.setDefaultWidget(self.widget)

    def _slider_value_changed_live(self, value):
        # Optional: Apply live changes as slider moves
        # self.headset_service.set_sidetone_level(value)
        self.value_label.setText(str(value))

    def _slider_released(self):
        value = self.slider.value()
        self.headset_service.set_sidetone_level(value)
        self.config_manager.set_last_sidetone_level(value)
        self.value_label.setText(str(value)) # Ensure label is correct

    def update_slider_value(self, value: int):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.value_label.setText(str(value))
        self.slider.blockSignals(False)


class SystemTrayIcon(QSystemTrayIcon):
    """Manages the system tray icon and its context menu."""

    def __init__(self, headset_service: hs_svc.HeadsetService, 
                 config_manager: cfg_mgr.ConfigManager, 
                 application_quit_fn, parent=None):
        super().__init__(parent)
        self.headset_service = headset_service
        self.config_manager = config_manager
        self.application_quit_fn = application_quit_fn

        self.eq_editor_dialog: Optional[EqualizerEditorDialog] = None

        self._base_icon = QIcon.fromTheme("audio-headset", QIcon.fromTheme("multimedia-audio-player"))
        self.setIcon(self._base_icon)
        self.activated.connect(self._on_activated)

        self.battery_level: Optional[int] = None
        # Initialize these attributes before calling _populate_context_menu
        self.current_custom_eq: Optional[str] = self.config_manager.get_last_custom_eq_curve_name()
        self.current_hw_eq_preset: Optional[int] = self.config_manager.get_last_active_eq_preset_id()
        self.active_eq_type: str = self.config_manager.get_active_eq_type()

        self.context_menu = QMenu()
        self._sidetone_action: Optional[SidetoneSliderAction] = None
        self._populate_context_menu() # Now active_eq_type is available
        self.setContextMenu(self.context_menu)


        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(app_config.REFRESH_INTERVAL_MS) # e.g., 30 seconds

        self.refresh_status() # Initial refresh


    def _create_battery_icon(self, level: Optional[int]) -> QIcon:
        if level is None:
            # Return base icon with a question mark or disconnected symbol
            pixmap = self._base_icon.pixmap(32, 32).copy()
            painter = QPainter(pixmap)
            painter.setPen(QColor(Qt.GlobalColor.red))
            painter.setFont(painter.font()) # Adjust font size if needed
            rect = pixmap.rect()
            painter.drawText(rect.adjusted(rect.width()//2,0,0,0), Qt.AlignmentFlag.AlignCenter, "?")
            painter.end()
            return QIcon(pixmap)

        # Simple icon: use theme battery icons if available, or draw custom one
        # For now, just modify tooltip and keep base icon, or use text.
        # A more advanced version would overlay a battery symbol.
        # For simplicity, we use one base icon and change text in tooltip.
        # If you want to change icon based on level:
        # if level > 75: icon_name = "battery-100"
        # elif level > 50: icon_name = "battery-080"
        # ... etc.
        # return QIcon.fromTheme(icon_name, self._base_icon)
        return self._base_icon # Keeping it simple for now

    def _update_tooltip_and_icon(self):
        tooltip_parts = []
        if self.headset_service.is_device_connected():
            if self.battery_level is not None:
                tooltip_parts.append(f"Battery: {self.battery_level}%")
                self.setIcon(self._create_battery_icon(self.battery_level))
            else:
                tooltip_parts.append("Battery: N/A")
                self.setIcon(self._create_battery_icon(None))
            
            # Add current EQ to tooltip
            if self.active_eq_type == "custom":
                tooltip_parts.append(f"EQ: {self.current_custom_eq}")
            elif self.active_eq_type == "hardware":
                preset_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(self.current_hw_eq_preset, f"Preset {self.current_hw_eq_preset}")
                tooltip_parts.append(f"EQ: {preset_name}")

        else:
            tooltip_parts.append("Headset disconnected")
            self.setIcon(self._create_battery_icon(None)) # Show disconnected state

        self.setToolTip("\n".join(tooltip_parts))
        

    def _populate_context_menu(self):
        self.context_menu.clear()

        # Battery Level
        self.battery_action = QAction("Battery: Unknown", self.context_menu)
        self.battery_action.setEnabled(False) # Just for display
        self.context_menu.addAction(self.battery_action)
        self.context_menu.addSeparator()

        # Sidetone
        self._sidetone_action = SidetoneSliderAction(self.context_menu, self.headset_service, self.config_manager)
        self.context_menu.addAction(self._sidetone_action)

        # Inactive Timeout
        timeout_menu = self.context_menu.addMenu("Inactive Timeout")
        self.timeout_action_group = [] # Using list instead of QActionGroup for manual check management
        current_timeout = self.config_manager.get_last_inactive_timeout()
        for text, minutes in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
            action = QAction(text, timeout_menu, checkable=True)
            action.setChecked(minutes == current_timeout)
            action.triggered.connect(lambda checked, m=minutes: self._set_inactive_timeout(m))
            timeout_menu.addAction(action)
            self.timeout_action_group.append(action)
        
        self.context_menu.addSeparator()

        # Equalizer Presets (Hardware)
        hw_eq_menu = self.context_menu.addMenu("Equalizer Presets (Hardware)")
        self.hw_eq_action_group = []
        current_hw_preset_id = self.config_manager.get_last_active_eq_preset_id()
        active_is_hw = self.active_eq_type == "hardware" # This line should now work

        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            action = QAction(name, hw_eq_menu, checkable=True)
            action.setChecked(active_is_hw and preset_id == current_hw_preset_id)
            action.triggered.connect(lambda checked, p_id=preset_id: self._apply_hw_eq_preset(p_id))
            hw_eq_menu.addAction(action)
            self.hw_eq_action_group.append(action)

        # Tone Curves (Custom EQ)
        custom_eq_menu = self.context_menu.addMenu("Tone Curves (Custom EQ)")
        self.custom_eq_action_group = []
        all_custom_curves = self.config_manager.get_all_custom_eq_curves()
        current_custom_curve_name = self.config_manager.get_last_custom_eq_curve_name()
        active_is_custom = self.active_eq_type == "custom"

        sorted_custom_names = sorted(all_custom_curves.keys())
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
        # Update Inactive Timeout checks
        current_timeout = self.config_manager.get_last_inactive_timeout()
        for action in self.timeout_action_group:
            # Find the minutes value corresponding to the action's text
            action_minutes = None
            for text, minutes_val in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
                if text == action.text():
                    action_minutes = minutes_val
                    break
            if action_minutes is not None:
                 action.setChecked(action_minutes == current_timeout)


        # Update HW EQ Preset checks
        current_hw_preset_id = self.config_manager.get_last_active_eq_preset_id()
        active_is_hw = self.active_eq_type == "hardware"
        for action in self.hw_eq_action_group:
            action_preset_id = None
            for pid, name_val in app_config.HARDWARE_EQ_PRESET_NAMES.items(): # Corrected variable name
                if name_val == action.text():
                    action_preset_id = pid
                    break
            if action_preset_id is not None:
                 action.setChecked(active_is_hw and action_preset_id == current_hw_preset_id)


        # Update Custom EQ Curve checks
        current_custom_curve_name = self.config_manager.get_last_custom_eq_curve_name()
        active_is_custom = self.active_eq_type == "custom"
        for action in self.custom_eq_action_group:
            action.setChecked(active_is_custom and action.text() == current_custom_curve_name)

    @Slot()
    def refresh_status(self):
        # print("Refreshing status...")
        if not self.headset_service.is_device_connected():
            # print("Device not connected during refresh.")
            self.battery_level = None
            self._update_tooltip_and_icon()
            self.battery_action.setText("Battery: Disconnected")
            # Potentially disable most controls if device is gone
            # self.context_menu.setEnabled(False) # Too aggressive, exit should work
            return

        # self.context_menu.setEnabled(True)
        self.battery_level = self.headset_service.get_battery_level()
        if self.battery_level is not None:
            self.battery_action.setText(f"Battery: {self.battery_level}%")
        else:
            self.battery_action.setText("Battery: N/A")

        # Update Sidetone (if HID get is implemented)
        live_sidetone = self.headset_service.get_sidetone_level()
        if live_sidetone is not None and self._sidetone_action:
            self._sidetone_action.update_slider_value(live_sidetone)
            self.config_manager.set_last_sidetone_level(live_sidetone) # Update stored if read from device
        
        # Update active EQ (if HID get is implemented)
        # live_eq_values = self.headset_service.get_current_eq_values()
        # live_preset_id = self.headset_service.get_current_eq_preset_id()
        # if live_preset_id is not None:
        #    self.config_manager.set_last_active_eq_preset_id(live_preset_id)
        #    self.config_manager.set_setting("active_eq_type", "hardware")
        #    self.active_eq_type = "hardware"
        #    self.current_hw_eq_preset = live_preset_id
        # elif live_eq_values is not None:
            # Try to match live_eq_values to a known custom curve
            # matched_curve_name = None
            # for name, values in self.config_manager.get_all_custom_eq_curves().items():
            #    if values == live_eq_values:
            #        matched_curve_name = name
            #        break
            # if matched_curve_name:
            #    self.config_manager.set_last_custom_eq_curve_name(matched_curve_name)
            #    self.config_manager.set_setting("active_eq_type", "custom")
            #    self.active_eq_type = "custom"
            #    self.current_custom_eq = matched_curve_name
            # else:
                # EQ values are custom but not saved, or a HW preset was modified
                # print("Live EQ values do not match any saved custom curve.")
                # Could save as "Live Unsaved" or similar
                # For now, we rely on what was last set through app if HID read is partial.

        self._update_tooltip_and_icon()
        self._update_menu_checks()


    def _set_inactive_timeout(self, minutes: int):
        if self.headset_service.set_inactive_timeout(minutes):
            self.config_manager.set_last_inactive_timeout(minutes)
            self.showMessage("Success", f"Inactive timeout set to {minutes} minutes.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", "Failed to set inactive timeout.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks()

    def _apply_hw_eq_preset(self, preset_id: int):
        if self.headset_service.set_eq_preset_id(preset_id):
            self.config_manager.set_last_active_eq_preset_id(preset_id)
            self.active_eq_type = "hardware" # Explicitly set type
            self.current_hw_eq_preset = preset_id
            self.config_manager.set_setting("active_eq_type", "hardware") # Persist type
            self.showMessage("Success", f"Hardware EQ Preset {preset_id} applied.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", "Failed to apply hardware EQ preset.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks()
        self._update_tooltip_and_icon()


    def _apply_custom_eq_curve(self, name: str):
        values = self.config_manager.get_custom_eq_curve(name)
        if values and self.headset_service.set_eq_values(values):
            self.config_manager.set_last_custom_eq_curve_name(name)
            self.active_eq_type = "custom" # Explicitly set type
            self.current_custom_eq = name
            self.config_manager.set_setting("active_eq_type", "custom") # Persist type
            self.showMessage("Success", f"Custom EQ curve '{name}' applied.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.showMessage("Error", f"Failed to apply custom EQ curve '{name}'.", QSystemTrayIcon.MessageIcon.Warning, 1500)
        self._update_menu_checks()
        self._update_tooltip_and_icon()

    def _open_eq_editor(self):
        if self.eq_editor_dialog is None or not self.eq_editor_dialog.isVisible():
            self.eq_editor_dialog = EqualizerEditorDialog(self.config_manager, self.headset_service)
            self.eq_editor_dialog.eq_applied.connect(self._handle_eq_editor_apply_custom)
            # self.eq_editor_dialog.hardware_preset_applied.connect(self._handle_eq_editor_apply_hw) # If editor can do this
            self.eq_editor_dialog.finished.connect(self._on_eq_editor_closed)
            self.eq_editor_dialog.show()
            self.eq_editor_dialog.activateWindow()
            self.eq_editor_dialog.raise_()
        else:
            self.eq_editor_dialog.activateWindow()
            self.eq_editor_dialog.raise_()
            
    @Slot(str)
    def _handle_eq_editor_apply_custom(self, curve_name: str):
        self.current_custom_eq = curve_name
        self.active_eq_type = "custom"
        # The editor already called config_manager.set_last_custom_eq_curve_name
        # and headset_service.set_eq_values. We just need to update tray state.
        self._update_menu_checks()
        self._update_tooltip_and_icon()
        # Refresh the custom EQ menu list in case curves were added/deleted
        self._populate_context_menu() 


    def _on_eq_editor_closed(self, result):
        # Potentially refresh list of custom EQs in main menu if names changed
        self._populate_context_menu() # Rebuild to reflect any new/deleted curves
        self.refresh_status() # Ensure status consistency

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: # Left click
            # Could open a small status window, or just show menu
            # For consistency with many tray apps, show context menu on left click too
            self.context_menu.popup(self.geometry().center())
        elif reason == QSystemTrayIcon.ActivationReason.Context: # Right click
            # Menu is already set via setContextMenu, but explicit popup can ensure it appears where cursor is.
            # self.context_menu.popup(QCursor.pos()) # if you want it at cursor
            pass


    def set_initial_headset_settings(self):
        """Applies persisted settings to the headset on startup."""
        if not self.headset_service.is_device_connected():
            # print("Cannot apply initial settings, device not connected.")
            return

        # Sidetone
        sidetone = self.config_manager.get_last_sidetone_level()
        self.headset_service.set_sidetone_level(sidetone)
        if self._sidetone_action:
             self._sidetone_action.update_slider_value(sidetone)


        # Inactive Timeout
        timeout = self.config_manager.get_last_inactive_timeout()
        self.headset_service.set_inactive_timeout(timeout)

        # EQ (Custom or Hardware)
        active_eq_type = self.config_manager.get_active_eq_type()
        self.active_eq_type = active_eq_type # Ensure self.active_eq_type is current
        if active_eq_type == "custom":
            curve_name = self.config_manager.get_last_custom_eq_curve_name()
            self.current_custom_eq = curve_name # Ensure self.current_custom_eq is current
            values = self.config_manager.get_custom_eq_curve(curve_name)
            if values:
                self.headset_service.set_eq_values(values)
            else: # Fallback if curve is somehow missing, apply default Flat
                flat_values = app_config.DEFAULT_EQ_CURVES.get("Flat", [0]*10)
                self.headset_service.set_eq_values(flat_values)
                self.config_manager.set_last_custom_eq_curve_name("Flat")
                self.current_custom_eq = "Flat"


        elif active_eq_type == "hardware":
            preset_id = self.config_manager.get_last_active_eq_preset_id()
            self.current_hw_eq_preset = preset_id # Ensure self.current_hw_eq_preset is current
            self.headset_service.set_eq_preset_id(preset_id)
        
        # print("Initial headset settings applied.")
        self.refresh_status() # Update UI based on these settings