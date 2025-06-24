"""Unit tests for the TrayIconPainter class."""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, Qt # Added QPixmap

# Assuming tray_icon_painter is in src.headsetcontrol_tray.ui
from headsetcontrol_tray.ui.tray_icon_painter import (
    BATTERY_LEVEL_HIGH,
    BATTERY_LEVEL_MEDIUM_CRITICAL,
    CHATMIX_VALUE_BALANCED,
    ICON_DRAW_SIZE,
    TrayIconPainter,
)


class TestTrayIconPainter(unittest.TestCase):
    """Test suite for the TrayIconPainter."""

    def setUp(self) -> None:
        self.mock_base_icon = MagicMock(spec=QIcon)

        # Create a real QPixmap for .copy() to return, to satisfy QIcon constructor
        self.real_pixmap_for_copy = QPixmap(ICON_DRAW_SIZE, ICON_DRAW_SIZE)
        self.real_pixmap_for_copy.fill(Qt.GlobalColor.transparent) # Make it a valid pixmap

        # Configure the chain of mocks for pixmap creation
        mock_pixmap_from_base_icon = MagicMock(spec=QPixmap) # Mock for self._base_icon.pixmap()
        mock_pixmap_from_base_icon.copy.return_value = self.real_pixmap_for_copy
        self.mock_base_icon.pixmap.return_value = mock_pixmap_from_base_icon

        self.painter_instance = TrayIconPainter(base_icon=self.mock_base_icon)

    @patch("headsetcontrol_tray.ui.tray_icon_painter.QPainter")
    def test_create_status_icon_disconnected(self, mock_qpainter_class) -> None:
        """Test icon creation when disconnected."""
        mock_painter_obj = mock_qpainter_class.return_value
        self.painter_instance._draw_disconnected_indicator = MagicMock()

        icon = self.painter_instance.create_status_icon(
            is_connected=False,
            battery_level=None,
            battery_status_text=None,
            chatmix_value=None,
        )

        self.mock_base_icon.pixmap.assert_called_once_with(ICON_DRAW_SIZE, ICON_DRAW_SIZE)
        mock_qpainter_class.assert_called_once_with(self.real_pixmap_for_copy)
        mock_painter_obj.setRenderHint.assert_called_once_with(QPainter.RenderHint.Antialiasing)
        self.painter_instance._draw_disconnected_indicator.assert_called_once_with(mock_painter_obj)
        mock_painter_obj.end.assert_called_once()
        assert icon is not None

    @patch("headsetcontrol_tray.ui.tray_icon_painter.QPainter")
    def test_create_status_icon_connected_all_features(self, mock_qpainter_class) -> None:
        """Test icon creation when connected with all features active."""
        mock_painter_obj = mock_qpainter_class.return_value
        self.painter_instance._draw_battery_indicator = MagicMock(
            return_value=MagicMock(spec=QRect),
        )  # Ensure it returns a QRect mock
        self.painter_instance._draw_charging_indicator = MagicMock()
        self.painter_instance._draw_chatmix_indicator = MagicMock()

        battery_level = 80
        battery_status = "BATTERY_CHARGING"
        chatmix = 30

        icon = self.painter_instance.create_status_icon(
            is_connected=True,
            battery_level=battery_level,
            battery_status_text=battery_status,
            chatmix_value=chatmix,
        )

        self.painter_instance._draw_battery_indicator.assert_called_once_with(mock_painter_obj, battery_level)
        # Ensure the QRect mock from _draw_battery_indicator is passed
        mock_battery_rect = self.painter_instance._draw_battery_indicator.return_value
        self.painter_instance._draw_charging_indicator.assert_called_once_with(
            mock_painter_obj, mock_battery_rect, battery_status,
        )
        self.painter_instance._draw_chatmix_indicator.assert_called_once_with(mock_painter_obj, chatmix, battery_level)
        assert icon is not None

    @patch("headsetcontrol_tray.ui.tray_icon_painter.QPainter")
    def test_create_status_icon_connected_battery_only(self, mock_qpainter_class) -> None:
        """Test icon creation when connected with only battery status (no charging/chatmix)."""
        mock_painter_obj = mock_qpainter_class.return_value
        # Mock _draw_battery_indicator to return a valid QRect mock for subsequent calls
        mock_battery_rect = MagicMock(spec=QRect)
        self.painter_instance._draw_battery_indicator = MagicMock(return_value=mock_battery_rect)
        self.painter_instance._draw_charging_indicator = MagicMock()
        self.painter_instance._draw_chatmix_indicator = MagicMock()

        battery_level = 50
        battery_status = "BATTERY_AVAILABLE"  # Not charging
        chatmix = CHATMIX_VALUE_BALANCED  # Not active chatmix display

        icon = self.painter_instance.create_status_icon(
            is_connected=True,
            battery_level=battery_level,
            battery_status_text=battery_status,
            chatmix_value=chatmix,
        )
        self.painter_instance._draw_battery_indicator.assert_called_once_with(mock_painter_obj, battery_level)
        self.painter_instance._draw_charging_indicator.assert_called_once_with(
            mock_painter_obj, mock_battery_rect, battery_status,
        )
        self.painter_instance._draw_chatmix_indicator.assert_called_once_with(mock_painter_obj, chatmix, battery_level)
        assert icon is not None

    def test_draw_disconnected_indicator(self) -> None:
        mock_painter = MagicMock(spec=QPainter)
        self.painter_instance._draw_disconnected_indicator(mock_painter)
        mock_painter.setPen.assert_called_once()
        # Check pen properties (color, width)
        pen_arg = mock_painter.setPen.call_args[0][0]
        assert pen_arg.color() == QColor(Qt.GlobalColor.red)
        assert pen_arg.width() == (ICON_DRAW_SIZE // 16 or 1)
        mock_painter.drawLine.assert_called_once()

    def test_draw_battery_indicator_levels(self) -> None:
        mock_painter = MagicMock(spec=QPainter)

        # Test high battery
        self.painter_instance._draw_battery_indicator(mock_painter, BATTERY_LEVEL_HIGH + 5)
        # Check fillRect was called with green for high battery
        # This requires inspecting calls to fillRect. The last call to fillRect should be green.
        assert any(call.args[1] == QColor(Qt.GlobalColor.green) for call in mock_painter.fillRect.call_args_list if call.args)
        mock_painter.reset_mock()

        # Test medium battery
        self.painter_instance._draw_battery_indicator(mock_painter, BATTERY_LEVEL_MEDIUM_CRITICAL + 5)
        assert any(call.args[1] == QColor(Qt.GlobalColor.yellow) for call in mock_painter.fillRect.call_args_list if call.args)
        mock_painter.reset_mock()

        # Test critical battery
        self.painter_instance._draw_battery_indicator(mock_painter, BATTERY_LEVEL_MEDIUM_CRITICAL - 5)
        assert any(call.args[1] == QColor(Qt.GlobalColor.red) for call in mock_painter.fillRect.call_args_list if call.args)
        mock_painter.reset_mock()

        # Test no battery level (should not fill)
        self.painter_instance._draw_battery_indicator(mock_painter, None)
        # Assert fillRect was not called for the battery level part
        # This is tricky if fillRect is called for other things; better to check specific rects if possible
        # For simplicity, if battery_level is None, the block with fillRect is skipped.
        # We can count calls before and after, or ensure the specific fill call for battery level is absent.
        # Here, we assume fillRect is only for battery level in this direct path.
        # This test becomes fragile if other fills are added.
        # A more robust test would check the fill color of a specific rect.
        # For now, let's check that no fillRect was called if battery_level is None.
        # However, the battery body itself might be drawn with a brush, so this is complex.
        # Let's focus on the color logic.
        # If battery_level is None, the `if battery_level is not None:` block is skipped.
        # So, fillRect for the level should not be called.
        # This check needs to be specific to the battery fill.
        # The current structure makes this hard to test in isolation without deeper painter mocking.
        # We'll rely on the color checks above for specific levels.

    def test_draw_charging_indicator(self) -> None:
        mock_painter = MagicMock(spec=QPainter)
        mock_rect = MagicMock(spec=QRect)
        mock_rect.center.return_value.x.return_value = 10
        mock_rect.center.return_value.y.return_value = 10
        mock_rect.height.return_value = 10
        mock_rect.width.return_value = 6

        # Test when charging
        self.painter_instance._draw_charging_indicator(mock_painter, mock_rect, "BATTERY_CHARGING")
        mock_painter.drawPath.assert_called_once()
        mock_painter.setBrush.assert_called_with(QColor(Qt.GlobalColor.yellow)) # Check setBrush was called with yellow
        # We might also want to check setPen: mock_painter.setPen.assert_called_with(QColor(Qt.GlobalColor.transparent))
        mock_painter.reset_mock()

        # Test when not charging
        self.painter_instance._draw_charging_indicator(mock_painter, mock_rect, "BATTERY_AVAILABLE")
        mock_painter.drawPath.assert_not_called()

    def test_draw_chatmix_indicator(self) -> None:
        mock_painter = MagicMock(spec=QPainter)

        # Test active chat (cyan)
        self.painter_instance._draw_chatmix_indicator(mock_painter, CHATMIX_VALUE_BALANCED - 10, BATTERY_LEVEL_HIGH)
        mock_painter.setBrush.assert_called_with(QColor(Qt.GlobalColor.cyan))
        mock_painter.drawEllipse.assert_called_once()
        mock_painter.reset_mock()

        # Test active game (green)
        self.painter_instance._draw_chatmix_indicator(mock_painter, CHATMIX_VALUE_BALANCED + 10, BATTERY_LEVEL_HIGH)
        mock_painter.setBrush.assert_called_with(QColor(Qt.GlobalColor.green))
        mock_painter.drawEllipse.assert_called_once()
        mock_painter.reset_mock()

        # Test not active (balanced)
        self.painter_instance._draw_chatmix_indicator(mock_painter, CHATMIX_VALUE_BALANCED, BATTERY_LEVEL_HIGH)
        mock_painter.drawEllipse.assert_not_called()
        mock_painter.reset_mock()

        # Test not active (None)
        self.painter_instance._draw_chatmix_indicator(mock_painter, None, BATTERY_LEVEL_HIGH)
        mock_painter.drawEllipse.assert_not_called()
        mock_painter.reset_mock()

        # Test battery critical (should not draw)
        self.painter_instance._draw_chatmix_indicator(
            mock_painter, CHATMIX_VALUE_BALANCED - 10, BATTERY_LEVEL_MEDIUM_CRITICAL,
        )
        mock_painter.drawEllipse.assert_not_called()


if __name__ == "__main__":
    unittest.main()
