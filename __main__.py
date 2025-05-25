#!/usr/bin/env python3

import sys
import subprocess
import re
import json
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QInputDialog, QMessageBox,
    QWidgetAction, QLabel, QHBoxLayout, QWidget, QSlider
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer, Qt, Slot

# --- Configuration ---
HEADSETCONTROL_CMD = "headsetcontrol"
# Update interval for battery check in milliseconds (e.g., 5 minutes)
BATTERY_CHECK_INTERVAL = 5 * 60 * 1000 # 5 minutes
# Icon names from your theme
ICON_BATTERY_LEVELS = {
    100: "battery-100",
    80: "battery-080",
    60: "battery-060",
    40: "battery-040",
    20: "battery-020",
    0: "battery-000",
    "charging": "battery-charging",
    "unknown": "battery-missing",
    "headset_default": "audio-headset"
}
# Device name for headsetcontrol commands, if needed.
# If your headset is the only one headsetcontrol manages, this might be optional.
# Check `headsetcontrol --list-devices`
HEADSET_DEVICE_NAME = "SteelSeries Arctis Nova 7"
# --- End Configuration ---

class HeadsetControlTray(QSystemTrayIcon):
    def __init__(self, icon, parent_app=None):
        super(HeadsetControlTray, self).__init__(icon, parent_app)
        self.app = parent_app

        self.current_battery_level = -1
        self.current_battery_status = "unknown" # "unknown", "charging", "discharging", "available"
        self.current_sidetone_level = -1 # Cannot be reliably read from JSON, will reflect last set value or default
        self.current_chatmix_level = -1 # Will be read from JSON
        self.current_eq_preset = -1 # -1: unknown, 0-3: presets, -2: custom. Cannot be reliably read from JSON.

        self._error_message_shown_recently = False
        self._initial_status_updated = False # Flag to ensure menu is correctly populated after first JSON read

        self.menu = QMenu()
        # Actions are created here, but menu is fully built after first status update
        self.create_actions()
        self.setContextMenu(self.menu) # Set empty menu initially, will be populated

        # Perform initial full status update. This will also build the menu for the first time.
        QTimer.singleShot(0, self.update_all_status_and_rebuild_menu)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_all_status) # Periodically update data
        self.timer.start(BATTERY_CHECK_INTERVAL)

        self.activated.connect(self.on_tray_activated)

    def run_command(self, args):
        try:
            # Always try to specify the device if we know its name
            cmd_list = [HEADSETCONTROL_CMD]
            if HEADSET_DEVICE_NAME and "--device" not in args : # Add device if not already specified by caller
                # check if -o json is already there, insert before it
                has_o_json = False
                try:
                    idx_o = args.index("-o")
                    if args[idx_o+1] == "json":
                        has_o_json = True
                except ValueError:
                    pass

                if has_o_json:
                     idx_o = args.index("-o")
                     cmd_list.extend(["--device", HEADSET_DEVICE_NAME])
                     cmd_list.extend(args[:idx_o])
                     cmd_list.extend(args[idx_o:])
                else:
                    cmd_list.extend(["--device", HEADSET_DEVICE_NAME])
                    cmd_list.extend(args)

            else: # if --device is already in args or no device name configured
                cmd_list.extend(args)

            # print(f"Running command: {' '.join(cmd_list)}") # For debugging
            process = subprocess.run(cmd_list, capture_output=True, text=True, check=False, timeout=10)

            if process.returncode != 0:
                error_message = f"Error with HeadsetControl:\nArgs: {' '.join(cmd_list)}\nStderr: {process.stderr.strip()}"
                # Check for common permission error hint
                if "Permission denied" in process.stderr and "/dev/hidraw" in process.stderr:
                    error_message += "\n\nHint: This looks like a permission issue. Ensure you have udev rules set up correctly for your headset."
                self.show_error_message(error_message)
                return None, process.stderr.strip()
            return process.stdout.strip(), None
        except FileNotFoundError:
            self.show_error_message(f"'{HEADSETCONTROL_CMD}' not found. Please ensure it's installed and in your PATH.")
            if self.app: self.app.quit()
            return None, "Command not found"
        except subprocess.TimeoutExpired:
            self.show_error_message(f"Command timed out: {HEADSETCONTROL_CMD} {' '.join(args)}")
            return None, "Command timed out"
        except Exception as e:
            self.show_error_message(f"An unexpected error occurred with command {' '.join(args)}: {e}")
            return None, str(e)

    def get_themed_icon(self, name_or_key):
        icon_name = ""
        if isinstance(name_or_key, int) and name_or_key in ICON_BATTERY_LEVELS: # if it's a level key like 100, 80
            icon_name = ICON_BATTERY_LEVELS[name_or_key]
        elif isinstance(name_or_key, str) and name_or_key in ICON_BATTERY_LEVELS: # if it's a status key "charging"
            icon_name = ICON_BATTERY_LEVELS[name_or_key]
        elif isinstance(name_or_key, str): # if it's a direct icon name (for charging-level specific icons)
            icon_name = name_or_key

        if icon_name and QIcon.hasThemeIcon(icon_name):
            return QIcon.fromTheme(icon_name)

        # Fallback logic
        print(f"Warning: Theme icon for '{name_or_key}' (resolved to '{icon_name}') not found.")
        fallback_theme_icon = "dialog-question"
        if name_or_key == "headset_default" or icon_name == ICON_BATTERY_LEVELS["headset_default"]:
             fallback_theme_icon = "audio-headphones"
        elif "battery" in icon_name or isinstance(name_or_key, int) : # if trying to get a battery icon
            fallback_theme_icon = ICON_BATTERY_LEVELS["unknown"] # "battery-missing"
            if QIcon.hasThemeIcon(fallback_theme_icon): return QIcon.fromTheme(fallback_theme_icon)
            return QIcon.fromTheme("battery-empty") # A more generic battery icon if "battery-missing" fails

        if QIcon.hasThemeIcon(fallback_theme_icon):
            return QIcon.fromTheme(fallback_theme_icon)
        return QIcon()

    @Slot()
    def update_all_status_and_rebuild_menu(self):
        """Called once at startup to fetch status and build the dynamic menu."""
        self.update_all_status(rebuild_menu=True)

    @Slot()
    def update_all_status(self, rebuild_menu=False):
        print("Updating all statuses from JSON...")
        # The --device arg is now added by run_command
        output, err = self.run_command(["-o", "json"])

        if err or not output:
            print(f"Failed to get JSON output. Error: {err}")
            # Potentially schedule a retry or notify user more persistently if this fails often
            self.update_battery_status_cli_fallback() # Minimal update
            if rebuild_menu or not self._initial_status_updated:
                self.create_menu() # Build menu with whatever data we have (likely defaults)
                self._initial_status_updated = True
            return

        try:
            data = json.loads(output)
            device_info = None
            if "devices" in data and isinstance(data["devices"], list) and len(data["devices"]) > 0:
                # Find our specific device if multiple are listed (though usually it's one)
                for dev in data["devices"]:
                    if dev.get("device") == HEADSET_DEVICE_NAME:
                        device_info = dev
                        break
                if not device_info: device_info = data["devices"][0] # Fallback to first if not found by name
            elif "name" in data and data["name"] == "HeadsetControl": # Possibly a single device output format
                 if "device" in data and data["device"] == HEADSET_DEVICE_NAME : # Check if this top-level object is our device
                      device_info = data
                 # This case might need adjustment based on single-device JSON structure if it differs from devices array

            if not device_info:
                print("Device info not found in JSON.")
                self.update_battery_status_cli_fallback()
                if rebuild_menu or not self._initial_status_updated:
                    self.create_menu()
                    self._initial_status_updated = True
                return

            # Battery
            if "battery" in device_info and isinstance(device_info["battery"], dict):
                self.current_battery_level = device_info["battery"].get("level", -1)
                raw_status = device_info["battery"].get("status", "BATTERY_STATUS_UNAVAILABLE").upper()
                if "CHARGING" in raw_status: # SteelSeries might use "BATTERY_STATUS_CHARGING"
                    self.current_battery_status = "charging"
                elif "AVAILABLE" in raw_status or "DISCHARGING" in raw_status: # "BATTERY_AVAILABLE" seems to be the normal state
                    self.current_battery_status = "discharging" # Treat "available" as discharging for icon purposes
                elif "FULL" in raw_status : # e.g. BATTERY_STATUS_FULL
                    self.current_battery_status = "discharging" # Fully charged but not plugged in is discharging
                    if self.current_battery_level == -1 : self.current_battery_level = 100
                else:
                    self.current_battery_status = "unknown"
            else:
                self.update_battery_status_cli_fallback(skip_ui_update=True)

            # ChatMix - directly an int value from your JSON
            if "chatmix" in device_info: # Your JSON shows "chatmix": 6
                self.current_chatmix_level = device_info["chatmix"]
            else:
                self.current_chatmix_level = -1 # Mark as unknown

            # Sidetone: NOT in your JSON output's current values.
            # self.current_sidetone_level remains the last set value by this app or -1.
            # No update from JSON possible.

            # Equalizer Preset: NOT in your JSON output's current values.
            # self.current_eq_preset remains the last set value by this app or -1.
            # No update from JSON possible.

            print(f"Status Parsed: Batt={self.current_battery_level}% ({self.current_battery_status}), "
                  f"ChatMix={self.current_chatmix_level} (Sidetone/EQ Preset not readable from JSON)")

        except json.JSONDecodeError:
            print("Error decoding JSON from headsetcontrol.")
            self.update_battery_status_cli_fallback()
        except Exception as e:
            print(f"Error processing JSON: {e}")
            self.update_battery_status_cli_fallback()

        if rebuild_menu or not self._initial_status_updated:
            self.create_menu() # Re/Build the menu with new (or old if error) values
            self._initial_status_updated = True
        else:
            self.update_tray_ui() # Just update existing UI elements


    @Slot()
    def update_battery_status_cli_fallback(self, skip_ui_update=False):
        print("Updating battery status (CLI fallback)...")
        output, err = self.run_command(["-b"]) # run_command will add --device
        if err or output is None:
            self.current_battery_level = -1
            self.current_battery_status = "unknown"
        else: # ... (rest of parsing as before)
            if "offline" in output.lower() or "unavailable" in output.lower():
                self.current_battery_level = -1; self.current_battery_status = "unknown"
            elif "charging" in output.lower():
                self.current_battery_status = "charging"
                match = re.search(r'\(?(\d+)%\)?', output); self.current_battery_level = int(match.group(1)) if match else -1
            else:
                self.current_battery_status = "discharging"
                match = re.search(r'(\d+)%', output); self.current_battery_level = int(match.group(1)) if match else -1
        print(f"Battery (CLI): {self.current_battery_level}%, Status: {self.current_battery_status}")
        if not skip_ui_update: self.update_tray_ui()


    def update_tray_ui(self):
        self.update_tray_icon()
        self.update_tray_tooltip()
        if self._initial_status_updated: # Only update menu labels if menu has been built
            self.update_menu_labels()


    def update_tray_icon(self):
        level = self.current_battery_level
        status = self.current_battery_status
        icon_key_to_use = "unknown" # Default to the key for unknown status

        if status == "charging":
            # Prefer charging specific icon, then level specific charging, then generic charging
            charging_icon_name = ICON_BATTERY_LEVELS.get("charging", "battery-empty-charging") # a specific icon name
            level_charging_icon_name = ""
            if level != -1:
                base_level_icon = ""
                if level >= 90: base_level_icon = ICON_BATTERY_LEVELS.get(100)
                elif level >= 70: base_level_icon = ICON_BATTERY_LEVELS.get(80)
                # ... other levels
                else: base_level_icon = ICON_BATTERY_LEVELS.get(0)
                if base_level_icon: level_charging_icon_name = f"{base_level_icon}-charging"

            if level_charging_icon_name and QIcon.hasThemeIcon(level_charging_icon_name):
                icon_key_to_use = level_charging_icon_name # This is a direct icon name string
            elif QIcon.hasThemeIcon(charging_icon_name):
                icon_key_to_use = charging_icon_name # This is a direct icon name string
            else: # Fallback to level if no distinct charging icon found
                status = "discharging" # Fallback to show level based icon

        if status == "discharging" and level != -1:
            if level >= 90: icon_key_to_use = 100
            elif level >= 70: icon_key_to_use = 80
            elif level >= 50: icon_key_to_use = 60
            elif level >= 30: icon_key_to_use = 40
            elif level >= 10: icon_key_to_use = 20
            else: icon_key_to_use = 0
        elif status != "charging": # If not charging and not discharging with known level (i.e. unknown)
            icon_key_to_use = "headset_default"

        self.setIcon(self.get_themed_icon(icon_key_to_use))


    def update_tray_tooltip(self):
        parts = []
        if self.current_battery_level != -1:
            status_str = f" ({self.current_battery_status.capitalize()})" if self.current_battery_status not in ["discharging", "unknown", "available"] else ""
            parts.append(f"Battery: {self.current_battery_level}%{status_str}")
        else: parts.append("Battery: Unknown")

        cm_label = self.chatmix_display_label(self.current_chatmix_level)
        if self.current_chatmix_level != -1: parts.append(f"ChatMix: {cm_label}")
        else: parts.append("ChatMix: Unknown")

        # Sidetone - display last set or "N/A" as it's not readable
        st_val = self.current_sidetone_level if self.current_sidetone_level != -1 else "N/A (Set only)"
        parts.append(f"Sidetone: {st_val}")

        # EQ Preset - display last set or "Unknown"
        eq_label = self.eq_preset_display_label(self.current_eq_preset)
        parts.append(f"EQ: {eq_label}")

        self.setToolTip("\n".join(parts) if parts else "Headset Status")

    def update_menu_labels(self):
        # This function assumes the actions (like self.battery_status_action) already exist.
        if not hasattr(self, 'battery_status_action'): return # Menu not fully built

        if self.current_battery_level != -1:
            status_text = f" ({self.current_battery_status.capitalize()})" if self.current_battery_status not in ["discharging", "unknown", "available"] else ""
            self.battery_status_action.setText(f"Battery: {self.current_battery_level}%{status_text}")
        else: self.battery_status_action.setText("Battery: Unknown")

        if hasattr(self, 'sidetone_value_label') and self.sidetone_value_label:
            s_val = self.current_sidetone_level if self.current_sidetone_level !=-1 else "N/A"
            self.sidetone_value_label.setText(f"Sidetone: {s_val}")
            if hasattr(self, 'sidetone_slider') and self.current_sidetone_level != -1:
                 # Only set if different to avoid loop & if slider exists
                if self.sidetone_slider.value() != self.current_sidetone_level:
                    self.sidetone_slider.setValue(self.current_sidetone_level)

        if hasattr(self, 'chatmix_value_label') and self.chatmix_value_label:
            cm_text = self.chatmix_display_label(self.current_chatmix_level)
            self.chatmix_value_label.setText(f"Mix: {cm_text}")
            if hasattr(self, 'chatmix_slider') and self.current_chatmix_level != -1:
                if self.chatmix_slider.value() != self.current_chatmix_level:
                    self.chatmix_slider.setValue(self.current_chatmix_level)

        if hasattr(self, 'eq_preset_current_action'):
            self.eq_preset_current_action.setText(f"Current EQ: {self.eq_preset_display_label(self.current_eq_preset)}")


    def create_actions(self):
        # These are just the non-dynamic actions. Dynamic ones go into create_menu.
        self.battery_status_action = QAction("Battery: Initializing...", self)
        self.battery_status_action.setEnabled(False)

        self.refresh_action = QAction(self.get_themed_icon("view-refresh"), "Refresh Status", self)
        self.refresh_action.triggered.connect(self.update_all_status) # Will use JSON

        self.quit_action = QAction(self.get_themed_icon("application-exit"), "Quit", self)
        if self.app: self.quit_action.triggered.connect(self.app.quit)

    # Slider creation logic
    def create_slider_widget_action(self, title_prefix, min_val, max_val, current_val_fn, callback_fn, display_fn=None, is_readable=True):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 2, 8, 2)

        current_val = current_val_fn()
        slider_pos = current_val if current_val != -1 and is_readable else (min_val + max_val) // 2
        # For non-readable, display_fn should handle current_val == -1 gracefully or show a default
        label_text_val = display_fn(current_val) if display_fn and (is_readable or current_val != -1) else \
                         (display_fn(slider_pos) if display_fn and not is_readable else slider_pos)
        if not is_readable and current_val == -1 : label_text_val = display_fn(slider_pos) if display_fn else f"{slider_pos} (Set only)"


        value_label = QLabel(f"{title_prefix}: {label_text_val}")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(slider_pos) # Set initial position
        slider.setMinimumWidth(100)

        # Store references for dynamic updates
        if title_prefix == "Sidetone": self.sidetone_slider, self.sidetone_value_label = slider, value_label
        elif title_prefix == "ChatMix": self.chatmix_slider, self.chatmix_value_label = slider, value_label

        def on_slider_release():
            value = slider.value()
            callback_fn(value)
            # Update label immediately for "set only" controls
            if not is_readable:
                 value_label.setText(f"{title_prefix}: {display_fn(value) if display_fn else value}")
            # For readable controls, update_all_status will refresh it.
            # QTimer.singleShot(600, self.update_all_status) # Refresh after command

        def on_slider_move(value): # Feedback while dragging
            value_label.setText(f"{title_prefix}: {display_fn(value) if display_fn else value}")

        slider.valueChanged.connect(on_slider_move)
        slider.sliderReleased.connect(on_slider_release)

        layout.addWidget(value_label, 1); layout.addWidget(slider, 2)
        widget.setLayout(layout)
        action = QWidgetAction(self); action.setDefaultWidget(widget)
        return action


    def create_menu(self):
        self.menu.clear() # Clear previous items

        self.menu.addAction(self.battery_status_action)
        self.menu.addAction(self.refresh_action)
        self.menu.addSeparator()

        # --- Sidetone --- (Not readable from your JSON)
        sidetone_action = self.create_slider_widget_action(
            "Sidetone", 0, 128, lambda: self.current_sidetone_level,
            self.set_sidetone, display_fn=lambda v: f"{v}" if v!=-1 else "N/A",
            is_readable=False # Critical: This tells the UI sidetone isn't read from device state
        )
        self.menu.addAction(sidetone_action)

        # --- ChatMix --- (Readable from your JSON)
        chatmix_action = self.create_slider_widget_action(
            "ChatMix", 0, 128, lambda: self.current_chatmix_level, # Min/Max might differ for Arctis Nova 7, check headsetcontrol -h
            self.set_chatmix, self.chatmix_display_label,
            is_readable=True
        )
        self.menu.addAction(chatmix_action)


        # --- Inactive Time ---
        inactive_menu = self.menu.addMenu("Inactive Time")
        # Current inactive time is not readable, so this is "set only"
        inactive_options = {"Disable": 0, "5 min": 5, "15 min": 15, "30 min": 30, "60 min": 60, "90 min": 90}
        for text, minutes in inactive_options.items():
            action = QAction(text, self)
            # Use a lambda that correctly captures the 'minutes' variable
            action.triggered.connect(lambda checked=False, m=minutes: self.set_inactive_time(m))
            inactive_menu.addAction(action)

        # --- Equalizer ---
        eq_menu = self.menu.addMenu("Equalizer")
        self.eq_preset_current_action = QAction(f"Current EQ: {self.eq_preset_display_label(self.current_eq_preset)}", self)
        self.eq_preset_current_action.setEnabled(False) # Display only, as it's not reliably readable
        eq_menu.addAction(self.eq_preset_current_action)

        eq_presets_submenu = eq_menu.addMenu("Set Preset")
        presets = {"Default": 0, "Preset 1": 1, "Preset 2": 2, "Preset 3": 3}
        for name, number in presets.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, n=number: self.set_equalizer_preset(n))
            eq_presets_submenu.addAction(action)

        set_custom_eq_action = QAction("Set Custom Curve...", self)
        set_custom_eq_action.triggered.connect(self.set_custom_equalizer_curve_dialog)
        eq_menu.addAction(set_custom_eq_action)

        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.update_menu_labels() # Ensure all labels are current after building

    @Slot(int)
    def set_sidetone(self, level):
        print(f"Setting sidetone to {level}")
        self.run_command(["-s", str(level)])
        self.current_sidetone_level = level # Optimistic update as it's not readable
        self.update_tray_ui() # Update tooltip and potentially menu label for sidetone

    def chatmix_display_label(self, level):
        if level == -1: return "N/A"
        # Your JSON showed "chatmix": 6. The range is 0-128 from help.
        # 6 seems very low. Double check headsetcontrol -h for Arctis Nova 7 chatmix range or interpretation.
        # Assuming 0-128 where <64 is game, >64 is chat.
        if level < 60: return f"Game ({level})"
        if level > 68: return f"Voice ({level})"
        return f"Balanced ({level})"

    @Slot(int)
    def set_chatmix(self, level):
        print(f"Setting ChatMix to {level}")
        self.run_command(["-m", str(level)])
        # We expect update_all_status to refresh this from JSON if successful
        QTimer.singleShot(600, self.update_all_status)

    @Slot(int)
    def set_inactive_time(self, minutes):
        print(f"Setting inactive time to {minutes} minutes")
        self.run_command(["-i", str(minutes)])
        # No direct readable feedback, user assumes it worked.

    def eq_preset_display_label(self, preset_num):
        if preset_num == -2: return "Custom"
        if preset_num == -1: return "N/A (Set only)" # Reflect that it's not read
        presets = {0: "Default", 1: "Preset 1", 2: "Preset 2", 3: "Preset 3"}
        return presets.get(preset_num, f"Preset {preset_num}")

    @Slot(int)
    def set_equalizer_preset(self, preset_number):
        print(f"Setting equalizer preset to {preset_number}")
        self.run_command(["-p", str(preset_number)])
        self.current_eq_preset = preset_number # Optimistic update
        self.update_tray_ui() # Update tooltip and menu label

    @Slot()
    def set_custom_equalizer_curve_dialog(self):
        text, ok = QInputDialog.getText(None, "Set Custom Equalizer Curve",
                                        "Enter space/comma/newline separated values (e.g., '0 2 -1 3'):")
        if ok and text:
            try:
                values_str = text.replace(',', ' ').replace('\n', ' ').strip()
                if not values_str: self.show_error_message("EQ curve empty."); return
                [float(v) for v in values_str.split()] # Validate
                self.run_command(["-e", values_str])
                self.current_eq_preset = -2 # Mark as custom
                self.update_tray_ui()
            except ValueError: self.show_error_message("Invalid EQ curve format.")
            except Exception as e: self.show_error_message(f"Error setting custom EQ: {e}")

    @Slot(QSystemTrayIcon.ActivationReason)
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: # Left click
            self.update_all_status()

    def show_error_message(self, message):
        if self._error_message_shown_recently: print(f"Suppressed error: {message}"); return
        print(f"Showing error: {message}")
        # Ensure self.parent() is valid or None if app is not fully up
        parent_widget = self.parent() if isinstance(self.parent(), QWidget) else None
        msg_box = QMessageBox(parent_widget)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(message); msg_box.setWindowTitle("HeadsetControl Tray Error")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok); msg_box.exec()
        self._error_message_shown_recently = True
        QTimer.singleShot(15000, self._reset_error_flag)

    @Slot()
    def _reset_error_flag(self): self._error_message_shown_recently = False


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    try:
        # Check if headsetcontrol can at least run and if udev rules might be an issue
        # We won't check for full JSON here to avoid sudo prompt if rules are not set yet.
        # The app will inform user if JSON parsing fails due to permissions later.
        result = subprocess.run([HEADSETCONTROL_CMD, "--version"], capture_output=True, text=True, check=True, timeout=3)
        print(f"HeadsetControl version: {result.stdout.strip() if result.stdout else 'Unknown (no version output)'}")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        QMessageBox.critical(None, "Fatal Error", f"'{HEADSETCONTROL_CMD}' not working or not found.\nDetails: {e}", QMessageBox.StandardButton.Ok)
        sys.exit(1)
    except Exception as e_gen:
        QMessageBox.critical(None, "Fatal Error", f"Unexpected error checking HeadsetControl: {e_gen}", QMessageBox.StandardButton.Ok)
        sys.exit(1)

    initial_icon = QIcon.fromTheme(ICON_BATTERY_LEVELS["headset_default"])
    if initial_icon.isNull(): initial_icon = QIcon.fromTheme("dialog-question")

    tray_icon = HeadsetControlTray(initial_icon, app)
    tray_icon.show()
    sys.exit(app.exec())