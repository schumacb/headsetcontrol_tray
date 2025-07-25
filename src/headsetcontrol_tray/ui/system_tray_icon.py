"""Manages the system tray icon, its context menu, and status updates."""

from collections.abc import Callable  # Added Any # Moved import for linter
import logging
from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from headsetcontrol_tray import app_config
from headsetcontrol_tray import config_manager as cfg_mgr
from headsetcontrol_tray import headset_service as hs_svc

from .chatmix_manager import ChatMixManager

# Ensure EqualizerEditorWidget constants are accessible if needed,
# or rely on string parsing
from .equalizer_editor_widget import (
    EQ_TYPE_CUSTOM,
    EQ_TYPE_HARDWARE,
    HW_PRESET_DISPLAY_PREFIX,
)
from .settings_dialog import SettingsDialog

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# --- Constants for Magic Numbers ---
# Battery Icon Thresholds
BATTERY_LEVEL_HIGH = 70
BATTERY_LEVEL_MEDIUM_CRITICAL = 25  # Critical if below or equal to this
BATTERY_LEVEL_FULL = 100

# ChatMix Values for display logic
CHATMIX_VALUE_FULL_CHAT = 0
CHATMIX_VALUE_BALANCED = 64
CHATMIX_VALUE_FULL_GAME = 128  # Max value for normalization


class SystemTrayIcon(QSystemTrayIcon):
    """Manages the system tray icon and its context menu."""

    NORMAL_REFRESH_INTERVAL_MS = 1000
    FAST_REFRESH_INTERVAL_MS = 100
    FAST_POLL_NO_CHANGE_THRESHOLD = 3  # Number of fast polls with no change before reverting to normal
    ICON_DRAW_SIZE = 32  # The size we'll use for generating our pixmap

    def __init__(
        self,
        headset_service: hs_svc.HeadsetService,
        config_manager: cfg_mgr.ConfigManager,
        application_quit_fn: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """Initializes the SystemTrayIcon.

        Args:
            headset_service: The application's HeadsetService instance.
            config_manager: The application's ConfigManager instance.
            application_quit_fn: Function to call to quit the application.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        logger.debug("SystemTrayIcon initializing.")
        self.headset_service = headset_service
        self.config_manager = config_manager
        self.application_quit_fn = application_quit_fn

        self.chatmix_manager = ChatMixManager(self.config_manager)
        self.settings_dialog: SettingsDialog | None = None

        self._base_icon = QIcon.fromTheme(
            "audio-headset",
            QIcon.fromTheme("multimedia-audio-player"),
        )

        self.activated.connect(self._on_activated)

        # State for adaptive polling and change detection
        self.fast_poll_active = False
        self.fast_poll_no_change_counter = 0
        self.is_tray_view_connected = False  # Tracks connection state by the tray
        # For change detection

        # Variables to store current fetched values for tooltip/menu (updated in refresh_status)
        self.battery_level: int | None = None
        self.battery_status_text: str | None = None  # e.g. "BATTERY_CHARGING"
        self.chatmix_value: int | None = None
        self.current_custom_eq_name_for_tooltip: str | None = None
        self.current_hw_preset_name_for_tooltip: str | None = None
        self.active_eq_type_for_tooltip: str | None = None

        self.context_menu = QMenu()
        self.battery_action: QAction | None = None
        self.chatmix_action: QAction | None = None
        self.sidetone_action_group: list[QAction] = []
        self.timeout_action_group: list[QAction] = []
        self.unified_eq_action_group: list[QAction] = []

        self._populate_context_menu()
        self.setContextMenu(self.context_menu)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.setInterval(
            self.NORMAL_REFRESH_INTERVAL_MS,
        )  # Start with normal interval
        self.refresh_timer.start()
        logger.info(
            "Refresh timer started with initial interval %sms.",
            self.NORMAL_REFRESH_INTERVAL_MS,
        )

        self.refresh_status()

    def _create_status_icon(self) -> QIcon:
        # Base pixmap from the theme icon
        pixmap = self._base_icon.pixmap(self.ICON_DRAW_SIZE, self.ICON_DRAW_SIZE).copy()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.is_tray_view_connected:
            self._draw_disconnected_indicator(painter)
        else:
            battery_body_rect = self._draw_battery_indicator(painter)
            if battery_body_rect:  # Only draw charging/chatmix if battery was drawn
                self._draw_charging_indicator(painter, battery_body_rect)
                self._draw_chatmix_indicator(painter)

        painter.end()
        return QIcon(pixmap)

    def _draw_disconnected_indicator(self, painter: QPainter) -> None:
        """Draws a red '/' to indicate disconnected state."""
        pen = QPen(QColor(Qt.GlobalColor.red))
        pen.setWidth(self.ICON_DRAW_SIZE // 16 or 1)
        painter.setPen(pen)
        margin = self.ICON_DRAW_SIZE // 10
        painter.drawLine(
            self.ICON_DRAW_SIZE - margin,
            margin,
            margin,
            self.ICON_DRAW_SIZE - margin,
        )

    def _draw_battery_indicator(self, painter: QPainter) -> QRect | None:
        """Draws the battery body and fill level. Returns the battery body QRect."""
        battery_area_size_w = self.ICON_DRAW_SIZE // 2
        battery_area_size_h = self.ICON_DRAW_SIZE // 3
        battery_margin_x = 2
        battery_margin_y = 2
        battery_outer_rect_x = self.ICON_DRAW_SIZE - battery_area_size_w - battery_margin_x
        battery_outer_rect_y = self.ICON_DRAW_SIZE - battery_area_size_h - battery_margin_y
        battery_outer_rect = QRect(
            battery_outer_rect_x,
            battery_outer_rect_y,
            battery_area_size_w,
            battery_area_size_h,
        )
        body_width = int(battery_outer_rect.width() * 0.75)
        body_height = int(battery_outer_rect.height() * 0.70)
        body_x = battery_outer_rect.left() + (battery_outer_rect.width() - body_width) // 2
        body_y = battery_outer_rect.top() + (battery_outer_rect.height() - body_height) // 2
        battery_body_rect = QRect(body_x, body_y, body_width, body_height)

        cap_width = max(1, body_width // 8)
        cap_height = max(2, body_height // 2)
        cap_rect = QRect(
            battery_body_rect.right(),
            battery_body_rect.top() + (battery_body_rect.height() - cap_height) // 2,
            cap_width,
            cap_height,
        )

        painter.setPen(QColor(Qt.GlobalColor.black))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(battery_body_rect)
        painter.drawRect(cap_rect)

        if self.battery_level is not None:
            fill_color = QColor(Qt.GlobalColor.gray)
            if self.battery_level > BATTERY_LEVEL_HIGH:
                fill_color = QColor(Qt.GlobalColor.green)
            elif self.battery_level > BATTERY_LEVEL_MEDIUM_CRITICAL:
                fill_color = QColor(Qt.GlobalColor.yellow)
            else:
                fill_color = QColor(Qt.GlobalColor.red)

            border_thickness = 1
            fill_max_width = battery_body_rect.width() - (2 * border_thickness)
            if fill_max_width > 0:
                fill_width = max(
                    0,
                    int(
                        fill_max_width * (self.battery_level / float(BATTERY_LEVEL_FULL)),
                    ),
                )
                fill_rect = QRect(
                    battery_body_rect.left() + border_thickness,
                    battery_body_rect.top() + border_thickness,
                    fill_width,
                    battery_body_rect.height() - (2 * border_thickness),
                )
                painter.fillRect(fill_rect, fill_color)
        return battery_body_rect

    def _draw_charging_indicator(
        self,
        painter: QPainter,
        battery_body_rect: QRect,
    ) -> None:
        """Draws the charging bolt symbol if applicable."""
        if not (self.is_tray_view_connected and self.battery_status_text == "BATTERY_CHARGING"):
            return

        logger.debug(
            "_draw_charging_indicator: Status: %s, Level: %s",
            self.battery_status_text,
            self.battery_level,
        )
        bolt_pen_color = QColor(Qt.GlobalColor.black)
        bolt_fill_color = QColor(Qt.GlobalColor.yellow)
        painter.setPen(bolt_pen_color)
        painter.pen().setWidth(1)
        painter.setBrush(bolt_fill_color)

        bolt_path = QPainterPath()
        cx = battery_body_rect.center().x()
        cy = battery_body_rect.center().y()
        bolt_total_h = max(4, int(battery_body_rect.height() * 0.6))
        bolt_point_offset_x = max(1, int(battery_body_rect.width() * 0.20))

        bolt_path.moveTo(cx - bolt_point_offset_x, cy - bolt_total_h * 0.2)
        bolt_path.lineTo(cx + bolt_point_offset_x, cy - bolt_total_h * 0.1)
        bolt_path.lineTo(cx, cy + bolt_total_h * 0.5)
        bolt_path.lineTo(cx - bolt_point_offset_x / 2, cy - bolt_total_h * 0.15)
        bolt_path.closeSubpath()
        painter.drawPath(bolt_path)

    def _draw_chatmix_indicator(self, painter: QPainter) -> None:
        """Draws the chatmix dot indicator if applicable."""
        battery_is_not_critical_or_unknown = (
            self.battery_level is None or self.battery_level > BATTERY_LEVEL_MEDIUM_CRITICAL
        )
        chatmix_is_active = self.chatmix_value is not None and self.chatmix_value != CHATMIX_VALUE_BALANCED

        if battery_is_not_critical_or_unknown and chatmix_is_active:
            dot_radius = self.ICON_DRAW_SIZE // 10 or 2
            dot_margin = self.ICON_DRAW_SIZE // 10 or 2
            chatmix_indicator_color = (
                QColor(Qt.GlobalColor.cyan)
                if self.chatmix_value < CHATMIX_VALUE_BALANCED  # type: ignore[operator]
                else QColor(Qt.GlobalColor.green)
            )
            painter.setBrush(chatmix_indicator_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                self.ICON_DRAW_SIZE - (2 * dot_radius) - dot_margin,
                dot_margin,
                2 * dot_radius,
                2 * dot_radius,
            )

    def _get_chatmix_display_string_for_tray(self, chatmix_val: int | None) -> str:
        if chatmix_val is None:
            return "N/A"
        percentage = round((chatmix_val / float(CHATMIX_VALUE_FULL_GAME)) * 100)
        if chatmix_val == CHATMIX_VALUE_FULL_CHAT:
            return f"Chat ({percentage}%)"
        if chatmix_val == CHATMIX_VALUE_BALANCED:
            return f"Balanced ({percentage}%)"
        if chatmix_val == CHATMIX_VALUE_FULL_GAME:
            return f"Game ({percentage}%)"
        return f"{chatmix_val} ({percentage}%)"

    def _get_battery_tooltip(self) -> str:
        if self.battery_level is not None:
            level_text = f"{self.battery_level}%"
            if self.battery_status_text == "BATTERY_CHARGING":
                return f"Battery: {level_text} (Charging)"
            if self.battery_status_text == "BATTERY_FULL":
                return f"Battery: {level_text} (Full)"
            return f"Battery: {level_text}"  # BATTERY_AVAILABLE or other
        if self.battery_status_text == "BATTERY_UNAVAILABLE":
            return "Battery: Unavailable"
        return "Battery: N/A"

    def _get_chatmix_tooltip(self) -> str:
        chatmix_str = self._get_chatmix_display_string_for_tray(self.chatmix_value)
        return f"ChatMix: {chatmix_str}"

    def _get_eq_tooltip(self) -> str:
        if self.active_eq_type_for_tooltip == EQ_TYPE_CUSTOM:
            return f"EQ: {self.current_custom_eq_name_for_tooltip}"
        if self.active_eq_type_for_tooltip == EQ_TYPE_HARDWARE:
            return f"EQ: {self.current_hw_preset_name_for_tooltip}"
        return "EQ: Unknown"  # Should ideally not happen

    def _update_tooltip_and_icon(self) -> None:
        tooltip_parts = []
        if self.is_tray_view_connected:
            tooltip_parts.append(self._get_battery_tooltip())
            tooltip_parts.append(self._get_chatmix_tooltip())
            tooltip_parts.append(self._get_eq_tooltip())
        else:
            tooltip_parts.append("Headset disconnected")

        new_icon = self._create_status_icon()
        # Only update icon if it actually changed to avoid unnecessary redraws.
        current_icon_key = self.icon().cacheKey() if self.icon() else -1
        new_icon_key = new_icon.cacheKey() if new_icon else -1

        if current_icon_key != new_icon_key:
            self.setIcon(new_icon)

        final_tooltip = "\n".join(tooltip_parts)
        if self.toolTip() != final_tooltip:
            self.setToolTip(final_tooltip)

    def _create_status_actions(self) -> None:
        self.battery_action = QAction("Battery: Unknown", self.context_menu)
        self.battery_action.setEnabled(False)
        self.context_menu.addAction(self.battery_action)

        self.chatmix_action = QAction("ChatMix: Unknown", self.context_menu)
        self.chatmix_action.setEnabled(False)
        self.context_menu.addAction(self.chatmix_action)

    def _create_sidetone_menu(self) -> None:
        sidetone_menu = self.context_menu.addMenu("Sidetone")
        current_sidetone_val = self.config_manager.get_last_sidetone_level()
        for text, level in sorted(
            app_config.SIDETONE_OPTIONS.items(),
            key=lambda item: item[1],
        ):
            action = QAction(text, sidetone_menu, checkable=True)
            action.setData(level)
            action.setChecked(level == current_sidetone_val)
            action.triggered.connect(
                lambda _, lvl=level: self._set_sidetone_from_menu(lvl),
            )
            sidetone_menu.addAction(action)
            self.sidetone_action_group.append(action)

    def _create_timeout_menu(self) -> None:
        timeout_menu = self.context_menu.addMenu("Inactive Timeout")
        current_timeout_val = self.config_manager.get_last_inactive_timeout()
        for text, minutes in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
            action = QAction(text, timeout_menu, checkable=True)
            action.setData(minutes)
            action.setChecked(minutes == current_timeout_val)
            action.triggered.connect(lambda _, m=minutes: self._set_inactive_timeout(m))
            timeout_menu.addAction(action)
            self.timeout_action_group.append(action)

    def _create_eq_menu(self) -> None:
        eq_menu = self.context_menu.addMenu("Equalizer")
        active_eq_type = self.config_manager.get_active_eq_type()
        active_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        active_hw_id = self.config_manager.get_last_active_eq_preset_id()
        custom_curves = self.config_manager.get_all_custom_eq_curves()

        sorted_custom_names = sorted(
            custom_curves.keys(),
            key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()),
        )
        for name in sorted_custom_names:
            action = QAction(name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_CUSTOM, name))
            action.setChecked(
                active_eq_type == EQ_TYPE_CUSTOM and name == active_custom_name,
            )
            action.triggered.connect(
                lambda _, data=(EQ_TYPE_CUSTOM, name): self._apply_eq_from_menu(data),
            )
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)

        if custom_curves and app_config.HARDWARE_EQ_PRESET_NAMES:
            eq_menu.addSeparator()

        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            display_name = HW_PRESET_DISPLAY_PREFIX + name
            action = QAction(display_name, eq_menu, checkable=True)
            action.setData((EQ_TYPE_HARDWARE, preset_id))
            action.setChecked(
                active_eq_type == EQ_TYPE_HARDWARE and preset_id == active_hw_id,
            )
            action.triggered.connect(
                lambda _, data=(EQ_TYPE_HARDWARE, preset_id): self._apply_eq_from_menu(
                    data,
                ),
            )
            eq_menu.addAction(action)
            self.unified_eq_action_group.append(action)

    def _create_main_control_actions(self) -> None:
        open_settings_action = QAction("Settings...", self.context_menu)
        open_settings_action.triggered.connect(self._open_settings_dialog)
        self.context_menu.addAction(open_settings_action)

        self.context_menu.addSeparator()
        exit_action = QAction("Exit", self.context_menu)
        exit_action.triggered.connect(self.application_quit_fn)
        self.context_menu.addAction(exit_action)

    def _populate_context_menu(self) -> None:
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

    def _update_menu_checks(self) -> None:
        logger.debug("Updating menu checks based on ConfigManager.")
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
            if not action_data:
                continue
            eq_type, identifier = action_data
            if eq_type == EQ_TYPE_CUSTOM:
                action.setChecked(
                    active_eq_type == EQ_TYPE_CUSTOM and identifier == active_custom_name,
                )
            elif eq_type == EQ_TYPE_HARDWARE:
                action.setChecked(
                    active_eq_type == EQ_TYPE_HARDWARE and identifier == active_hw_id,
                )

    def _fetch_and_update_headset_data(
        self,
        *,
        current_is_connected: bool,
    ) -> tuple[str, str, bool]:
        """Fetches data from headset, updates internal state, returns menu texts and data_changed flag."""
        new_battery_text = "Battery: Disconnected"
        new_chatmix_text = "ChatMix: Disconnected"
        data_changed_while_connected = False

        if not current_is_connected:
            self.battery_level = None
            self.battery_status_text = None
            self.chatmix_value = None
        else:
            prev_battery_level = self.battery_level
            prev_battery_status_text = self.battery_status_text
            prev_chatmix_value = self.chatmix_value

            self.battery_level = self.headset_service.get_battery_level()
            is_charging = self.headset_service.is_charging()

            if is_charging:
                self.battery_status_text = "BATTERY_CHARGING"
            elif self.battery_level == BATTERY_LEVEL_FULL:
                self.battery_status_text = "BATTERY_FULL"
            elif self.battery_level is not None:
                self.battery_status_text = "BATTERY_AVAILABLE"
            else:
                self.battery_status_text = "BATTERY_UNAVAILABLE"

            self.chatmix_value = self.headset_service.get_chatmix_value()

            new_battery_text = self._get_battery_tooltip()  # Use existing helper
            new_chatmix_text = self._get_chatmix_tooltip()  # Use existing helper

            if (
                self.battery_level != prev_battery_level
                or self.battery_status_text != prev_battery_status_text
                or self.chatmix_value != prev_chatmix_value
            ):
                data_changed_while_connected = True

        return new_battery_text, new_chatmix_text, data_changed_while_connected

    def _update_ui_elements(self, new_battery_text: str, new_chatmix_text: str) -> None:
        """Updates UI elements like menu text, icons, and tooltips."""
        if self.battery_action and self.battery_action.text() != new_battery_text:
            self.battery_action.setText(new_battery_text)
        if self.chatmix_action and self.chatmix_action.text() != new_chatmix_text:
            self.chatmix_action.setText(new_chatmix_text)

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

    def _manage_polling_interval(
        self,
        *,
        current_is_connected: bool,
        data_changed_while_connected: bool,
        connection_state_changed: bool,
    ) -> None:
        """Manages the polling interval based on connection and data changes."""
        if not current_is_connected:
            if self.refresh_timer.interval() != self.NORMAL_REFRESH_INTERVAL_MS:
                self.refresh_timer.setInterval(self.NORMAL_REFRESH_INTERVAL_MS)
                logger.debug(
                    "Device disconnected. Switched to normal refresh interval (%sms).",
                    self.NORMAL_REFRESH_INTERVAL_MS,
                )
            self.fast_poll_active = False
            self.fast_poll_no_change_counter = 0
        elif self.fast_poll_active:
            if not data_changed_while_connected:
                self.fast_poll_no_change_counter += 1
                if self.fast_poll_no_change_counter >= self.FAST_POLL_NO_CHANGE_THRESHOLD:
                    self.refresh_timer.setInterval(self.NORMAL_REFRESH_INTERVAL_MS)
                    self.fast_poll_active = False
                    self.fast_poll_no_change_counter = 0
                    logger.debug(
                        "No change threshold reached on fast poll. Switched to normal interval (%sms).",
                        self.NORMAL_REFRESH_INTERVAL_MS,
                    )
            else:
                self.fast_poll_no_change_counter = 0
        elif data_changed_while_connected or connection_state_changed:
            self.refresh_timer.setInterval(self.FAST_REFRESH_INTERVAL_MS)
            self.fast_poll_active = True
            self.fast_poll_no_change_counter = 0
            logger.debug(
                "State change detected. Switched to fast refresh interval (%sms).",
                self.FAST_REFRESH_INTERVAL_MS,
            )

    @Slot()
    def refresh_status(self) -> None:
        """Refreshes headset status, updates tray icon, tooltip, and menu."""
        logger.debug(
            "SystemTray: Refreshing status (Interval: %sms)...",
            self.refresh_timer.interval(),
        )

        prev_connection_state = self.is_tray_view_connected
        current_is_connected = self.headset_service.is_device_connected()
        self.is_tray_view_connected = current_is_connected
        connection_state_changed = current_is_connected != prev_connection_state

        if connection_state_changed:
            logger.info(
                "SystemTray: Headset %s.",
                "connected" if current_is_connected else "disconnected",
            )

        new_battery_text, new_chatmix_text, data_changed = self._fetch_and_update_headset_data(
            current_is_connected=current_is_connected,
        )
        self._update_ui_elements(new_battery_text, new_chatmix_text)

        if current_is_connected and self.chatmix_value is not None:
            try:
                self.chatmix_manager.update_volumes(self.chatmix_value)
            except Exception:
                logger.exception("Error during chatmix_manager.update_volumes:")

        # Update last known state for next cycle's change detection
        # (after all processing)

        self._manage_polling_interval(
            current_is_connected=current_is_connected,
            data_changed_while_connected=data_changed,
            connection_state_changed=connection_state_changed,
        )
        logger.debug("SystemTray: Refresh status complete.")

    def _set_sidetone_from_menu(self, level: int) -> None:
        logger.info("Setting sidetone to %s via menu.", level)
        if self.headset_service.set_sidetone_level(
            level,
        ):  # Checks connection internally
            self.config_manager.set_last_sidetone_level(level)
            self.showMessage(
                "Success",
                "Sidetone set.",
                QSystemTrayIcon.MessageIcon.Information,
                1500,
            )
            self.refresh_status()
        else:
            self.showMessage(
                "Error",
                "Failed to set sidetone. Headset connected?",
                QSystemTrayIcon.MessageIcon.Warning,
                2000,
            )
            self._update_menu_checks()

    def _set_inactive_timeout(self, minutes: int) -> None:
        logger.info("Setting inactive timeout to %s minutes via menu.", minutes)
        if self.headset_service.set_inactive_timeout(
            minutes,
        ):  # Checks connection internally
            self.config_manager.set_last_inactive_timeout(minutes)
            self.showMessage(
                "Success",
                "Inactive timeout set.",
                QSystemTrayIcon.MessageIcon.Information,
                1500,
            )
            self.refresh_status()
        else:
            self.showMessage(
                "Error",
                "Failed to set inactive timeout. Headset connected?",
                QSystemTrayIcon.MessageIcon.Warning,
                2000,
            )
            self._update_menu_checks()

    def _apply_eq_from_menu(
        self,
        eq_data: tuple[str, Any],
    ) -> None:  # Changed any to Any
        eq_type, identifier = eq_data
        logger.info("Applying EQ from menu: Type=%s, ID/Name='%s'", eq_type, identifier)

        if not self.headset_service.is_device_connected():
            self.showMessage(
                "Error",
                "Cannot apply EQ. Headset not connected.",
                QSystemTrayIcon.MessageIcon.Warning,
                2000,
            )
            self._update_menu_checks()  # Revert if user clicked something
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
                else:  # headset_service.set_eq_values failed
                    message = f"Failed to apply custom EQ '{curve_name}' to headset."
            else:  # values is None or empty
                message = f"Custom EQ '{curve_name}' not found or has no values."

        elif eq_type == EQ_TYPE_HARDWARE:
            preset_id = int(identifier)
            if self.headset_service.set_eq_preset_id(preset_id):
                self.config_manager.set_last_active_eq_preset_id(preset_id)
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_HARDWARE)
                preset_display_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(
                    preset_id,
                    f"Preset {preset_id}",
                )
                message = f"Hardware EQ '{preset_display_name}' applied."
                success = True
            else:
                message = f"Failed to apply hardware EQ preset ID {preset_id}."

        if success:
            self.showMessage(
                "Success",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                1500,
            )
        else:
            self.showMessage(
                "Error",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                1500,
            )

        self.refresh_status()

    def _open_settings_dialog(self) -> None:
        logger.debug("Open Settings dialog action triggered.")
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            self.settings_dialog = SettingsDialog(
                self.config_manager,
                self.headset_service,
            )
            self.settings_dialog.eq_applied.connect(
                self._handle_settings_dialog_eq_applied,
            )
            self.settings_dialog.settings_changed.connect(self.refresh_status)
            self.settings_dialog.finished.connect(self._on_settings_dialog_closed)
            self.settings_dialog.show()
        else:
            self.settings_dialog.equalizer_widget.refresh_view()
        self.settings_dialog.activateWindow()
        self.settings_dialog.raise_()

    @Slot(str)
    def _handle_settings_dialog_eq_applied(self, eq_identifier_signal_str: str) -> None:
        logger.info(
            "SystemTray received eq_applied signal from SettingsDialog: '%s'",
            eq_identifier_signal_str,
        )
        self.refresh_status()

    def _on_settings_dialog_closed(self, result: int) -> None:
        logger.debug("Settings dialog closed with result: %s", result)
        self.refresh_status()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._open_settings_dialog()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.context_menu.popup(QCursor.pos())

    def set_initial_headset_settings(self) -> None:
        """Applies stored settings to the headset upon application startup."""
        logger.info("Attempting to apply initial headset settings.")
        if not self.headset_service.is_device_connected():
            logger.warning("Cannot apply initial settings, device not connected.")
            return

        self.headset_service.set_sidetone_level(
            self.config_manager.get_last_sidetone_level(),
        )
        self.headset_service.set_inactive_timeout(
            self.config_manager.get_last_inactive_timeout(),
        )

        active_type = self.config_manager.get_active_eq_type()
        if active_type == EQ_TYPE_CUSTOM:
            name = self.config_manager.get_last_custom_eq_curve_name()
            vals = self.config_manager.get_custom_eq_curve(name)
            if not vals:
                name = app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME
                default_flat = app_config.DEFAULT_EQ_CURVES["Flat"]
                vals = self.config_manager.get_custom_eq_curve(name) or default_flat
                self.config_manager.set_last_custom_eq_curve_name(name)

            float_vals = [float(v) for v in vals]  # Convert to list[float]
            self.headset_service.set_eq_values(float_vals)
        elif active_type == EQ_TYPE_HARDWARE:
            self.headset_service.set_eq_preset_id(
                self.config_manager.get_last_active_eq_preset_id(),
            )

        logger.info("Initial headset settings applied.")
        self.refresh_status()
