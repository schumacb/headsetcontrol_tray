"""
Handles the generation of dynamic QIcon objects for the system tray
based on headset status.
"""

import logging

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen

from headsetcontrol_tray import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Constants for Icon Drawing (mirrored from SystemTrayIcon for now)
ICON_DRAW_SIZE = 32
BATTERY_LEVEL_HIGH = 70
BATTERY_LEVEL_MEDIUM_CRITICAL = 25  # Critical if below or equal to this
BATTERY_LEVEL_FULL = 100
CHATMIX_VALUE_BALANCED = 64


class TrayIconPainter:
    """Generates QIcon objects for the system tray."""

    def __init__(self, base_icon: QIcon) -> None:
        """
        Initializes the TrayIconPainter.

        Args:
            base_icon: The base QIcon to draw upon.
        """
        self._base_icon = base_icon
        self._icon_draw_size = ICON_DRAW_SIZE

    def create_status_icon(
        self,
        *, # Make subsequent arguments keyword-only
        is_connected: bool,
        battery_level: int | None,
        battery_status_text: str | None,  # e.g., "BATTERY_CHARGING", "BATTERY_FULL"
        chatmix_value: int | None,
    ) -> QIcon:
        """
        Creates a status icon based on the provided headset state.

        Args:
            is_connected: True if the headset is connected, False otherwise.
            battery_level: Current battery level (0-100) or None.
            battery_status_text: String indicating battery status (e.g., "BATTERY_CHARGING").
            chatmix_value: Current chatmix value or None.

        Returns:
            A QIcon representing the current status.
        """
        # Base pixmap from the theme icon
        pixmap = self._base_icon.pixmap(self._icon_draw_size, self._icon_draw_size).copy()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not is_connected:
            self._draw_disconnected_indicator(painter)
        else:
            battery_body_rect = self._draw_battery_indicator(painter, battery_level)
            if battery_body_rect:  # Only draw charging/chatmix if battery was drawn
                self._draw_charging_indicator(painter, battery_body_rect, battery_status_text)
                self._draw_chatmix_indicator(painter, chatmix_value, battery_level)

        painter.end()
        return QIcon(pixmap)

    def _draw_disconnected_indicator(self, painter: QPainter) -> None:
        """Draws a red '/' to indicate disconnected state."""
        pen = QPen(QColor(Qt.GlobalColor.red))
        pen.setWidth(self._icon_draw_size // 16 or 1)
        painter.setPen(pen)
        margin = self._icon_draw_size // 10
        painter.drawLine(
            self._icon_draw_size - margin,
            margin,
            margin,
            self._icon_draw_size - margin,
        )

    def _draw_battery_indicator(self, painter: QPainter, battery_level: int | None) -> QRect | None:
        """Draws the battery body and fill level. Returns the battery body QRect."""
        battery_area_size_w = self._icon_draw_size // 2
        battery_area_size_h = self._icon_draw_size // 3
        battery_margin_x = 2
        battery_margin_y = 2
        battery_outer_rect_x = self._icon_draw_size - battery_area_size_w - battery_margin_x
        battery_outer_rect_y = self._icon_draw_size - battery_area_size_h - battery_margin_y
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

        if battery_level is not None:
            fill_color = QColor(Qt.GlobalColor.gray)
            if battery_level > BATTERY_LEVEL_HIGH:
                fill_color = QColor(Qt.GlobalColor.green)
            elif battery_level > BATTERY_LEVEL_MEDIUM_CRITICAL:
                fill_color = QColor(Qt.GlobalColor.yellow)
            else:
                fill_color = QColor(Qt.GlobalColor.red)

            border_thickness = 1
            fill_max_width = battery_body_rect.width() - (2 * border_thickness)
            if fill_max_width > 0:
                fill_width = max(
                    0,
                    int(
                        fill_max_width * (battery_level / float(BATTERY_LEVEL_FULL)),
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
        battery_status_text: str | None,
    ) -> None:
        """Draws the charging bolt symbol if applicable."""
        if battery_status_text != "BATTERY_CHARGING":
            return

        logger.debug("_draw_charging_indicator: Drawing charging bolt.")
        bolt_pen_color = QColor(Qt.GlobalColor.black)
        bolt_fill_color = QColor(Qt.GlobalColor.yellow)  # Standard charging color
        painter.setPen(bolt_pen_color)
        painter.pen().setWidth(1)
        painter.setBrush(bolt_fill_color)

        bolt_path = QPainterPath()
        # Simplified bolt shape within the battery body rect
        cx = battery_body_rect.center().x()
        cy = battery_body_rect.center().y()
        bolt_h = battery_body_rect.height() * 0.7
        bolt_w_top = battery_body_rect.width() * 0.3
        bolt_w_bottom = battery_body_rect.width() * 0.3

        # Define points for a simple zigzag bolt
        # Top point
        bolt_path.moveTo(cx + bolt_w_top / 2, cy - bolt_h / 2)
        # Middle-left point
        bolt_path.lineTo(cx - bolt_w_bottom / 2, cy)
        # Bottom point
        bolt_path.lineTo(cx - bolt_w_top / 2, cy + bolt_h / 2)
        # Middle-right point (to make it look like a filled shape)
        bolt_path.lineTo(cx + bolt_w_bottom / 2, cy)
        bolt_path.closeSubpath()

        painter.drawPath(bolt_path)

    def _draw_chatmix_indicator(
        self,
        painter: QPainter,
        chatmix_value: int | None,
        battery_level: int | None,
    ) -> None:
        """Draws the chatmix dot indicator if applicable."""
        battery_is_not_critical_or_unknown = battery_level is None or battery_level > BATTERY_LEVEL_MEDIUM_CRITICAL
        chatmix_is_active = chatmix_value is not None and chatmix_value != CHATMIX_VALUE_BALANCED

        if battery_is_not_critical_or_unknown and chatmix_is_active:
            dot_radius = self._icon_draw_size // 10 or 2
            dot_margin = self._icon_draw_size // 10 or 2
            chatmix_indicator_color = (
                QColor(Qt.GlobalColor.cyan)
                if chatmix_value < CHATMIX_VALUE_BALANCED  # type: ignore[operator]
                else QColor(Qt.GlobalColor.green)
            )
            painter.setBrush(chatmix_indicator_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                self._icon_draw_size - (2 * dot_radius) - dot_margin,
                dot_margin,
                2 * dot_radius,
                2 * dot_radius,
            )
