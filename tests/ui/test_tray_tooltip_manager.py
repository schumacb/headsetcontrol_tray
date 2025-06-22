"""Unit tests for the TrayTooltipManager class."""

import unittest
from unittest.mock import MagicMock

from headsetcontrol_tray.app_config import HARDWARE_EQ_PRESET_NAMES  # For checking EQ names
from headsetcontrol_tray.ui.equalizer_editor_widget import EQ_TYPE_CUSTOM, EQ_TYPE_HARDWARE
from headsetcontrol_tray.ui.tray_tooltip_manager import TrayTooltipManager


class TestTrayTooltipManager(unittest.TestCase):
    """Test suite for the TrayTooltipManager."""

    def setUp(self) -> None:
        self.mock_config_manager_getter = MagicMock()
        self.tooltip_manager = TrayTooltipManager(config_manager_getter=self.mock_config_manager_getter)

    def test_tooltip_disconnected(self) -> None:
        """Test tooltip when headset is disconnected."""
        tooltip = self.tooltip_manager.get_tooltip(
            is_connected=False,
            battery_level=None,
            battery_status_text=None,
            chatmix_value=None,
            active_eq_type=None,
            current_custom_eq_name=None,
            current_hw_preset_id=None,
        )
        assert tooltip == "Headset disconnected"

    def test_tooltip_connected_battery_charging(self) -> None:
        """Test tooltip for battery charging."""
        tooltip = self.tooltip_manager.get_tooltip(
            is_connected=True,
            battery_level=85,
            battery_status_text="BATTERY_CHARGING",
            chatmix_value=64,  # Balanced
            active_eq_type=EQ_TYPE_CUSTOM,
            current_custom_eq_name="MyCustomEQ",
            current_hw_preset_id=None,
        )
        assert "Battery: 85% (Charging)" in tooltip
        assert "ChatMix: Balanced (50%)" in tooltip
        assert "EQ: MyCustomEQ" in tooltip

    def test_tooltip_connected_battery_full(self) -> None:
        """Test tooltip for battery full."""
        tooltip = self.tooltip_manager.get_tooltip(
            is_connected=True,
            battery_level=100,
            battery_status_text="BATTERY_FULL",
            chatmix_value=0,  # Full Chat
            active_eq_type=EQ_TYPE_HARDWARE,
            current_custom_eq_name=None,
            current_hw_preset_id=1,  # Assuming ID 1 exists
        )
        expected_hw_eq_name = HARDWARE_EQ_PRESET_NAMES.get(1, "Preset 1")
        assert "Battery: 100% (Full)" in tooltip
        assert "ChatMix: Chat (0%)" in tooltip
        assert f"EQ: {expected_hw_eq_name}" in tooltip

    def test_tooltip_connected_battery_available(self) -> None:
        """Test tooltip for battery available (not charging, not full)."""
        tooltip = self.tooltip_manager.get_tooltip(
            is_connected=True,
            battery_level=50,
            battery_status_text="BATTERY_AVAILABLE",
            chatmix_value=128,  # Full Game
            active_eq_type=EQ_TYPE_CUSTOM,
            current_custom_eq_name="GameMode",
            current_hw_preset_id=None,
        )
        assert "Battery: 50%" in tooltip
        assert "(Charging)" not in tooltip
        assert "(Full)" not in tooltip
        assert "ChatMix: Game (100%)" in tooltip
        assert "EQ: GameMode" in tooltip

    def test_tooltip_battery_unavailable(self) -> None:
        """Test tooltip when battery level is None but status is BATTERY_UNAVAILABLE."""
        tooltip = self.tooltip_manager.get_tooltip(
            is_connected=True,
            battery_level=None,
            battery_status_text="BATTERY_UNAVAILABLE",
            chatmix_value=None,
            active_eq_type=None,
            current_custom_eq_name=None,
            current_hw_preset_id=None,
        )
        assert "Battery: Unavailable" in tooltip
        assert "ChatMix: N/A" in tooltip
        assert "EQ: Unknown" in tooltip

    def test_tooltip_battery_none_no_status(self) -> None:
        """Test tooltip when battery level and status are None."""
        tooltip = self.tooltip_manager.get_tooltip(
            is_connected=True,
            battery_level=None,
            battery_status_text=None,  # No specific status like UNAVAILABLE
            chatmix_value=None,
            active_eq_type=None,
            current_custom_eq_name=None,
            current_hw_preset_id=None,
        )
        assert "Battery: N/A" in tooltip

    def test_tooltip_chatmix_various_values(self) -> None:
        """Test chatmix display string for various values."""
        # Full Chat
        tooltip_chat = self.tooltip_manager.get_tooltip(is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=0, active_eq_type=None, current_custom_eq_name=None, current_hw_preset_id=None)
        assert "ChatMix: Chat (0%)" in tooltip_chat

        # Balanced
        tooltip_balanced = self.tooltip_manager.get_tooltip(is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=64, active_eq_type=None, current_custom_eq_name=None, current_hw_preset_id=None)
        assert "ChatMix: Balanced (50%)" in tooltip_balanced

        # Full Game
        tooltip_game = self.tooltip_manager.get_tooltip(is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=128, active_eq_type=None, current_custom_eq_name=None, current_hw_preset_id=None)
        assert "ChatMix: Game (100%)" in tooltip_game

        # Intermediate value (example: 32, which is 25%)
        tooltip_intermediate = self.tooltip_manager.get_tooltip(is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=32, active_eq_type=None, current_custom_eq_name=None, current_hw_preset_id=None)
        assert "ChatMix: 32 (25%)" in tooltip_intermediate

        # Chatmix None
        tooltip_none = self.tooltip_manager.get_tooltip(is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=None, active_eq_type=None, current_custom_eq_name=None, current_hw_preset_id=None)
        assert "ChatMix: N/A" in tooltip_none

    def test_tooltip_eq_types(self) -> None:
        """Test EQ display string for different EQ types."""
        # Custom EQ
        tooltip_custom_eq = self.tooltip_manager.get_tooltip(
            is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=64, active_eq_type=EQ_TYPE_CUSTOM, current_custom_eq_name="MyFavoriteEQ", current_hw_preset_id=None,
        )
        assert "EQ: MyFavoriteEQ" in tooltip_custom_eq

        # Hardware EQ - known ID
        hw_preset_id_known = next(iter(HARDWARE_EQ_PRESET_NAMES.keys()))  # Get a valid ID
        hw_preset_name_known = HARDWARE_EQ_PRESET_NAMES[hw_preset_id_known]
        tooltip_hw_eq_known = self.tooltip_manager.get_tooltip(
            is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=64, active_eq_type=EQ_TYPE_HARDWARE, current_custom_eq_name=None, current_hw_preset_id=hw_preset_id_known,
        )
        assert f"EQ: {hw_preset_name_known}" in tooltip_hw_eq_known

        # Hardware EQ - unknown ID
        hw_preset_id_unknown = 99
        tooltip_hw_eq_unknown = self.tooltip_manager.get_tooltip(
            is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=64, active_eq_type=EQ_TYPE_HARDWARE, current_custom_eq_name=None, current_hw_preset_id=hw_preset_id_unknown,
        )
        assert f"EQ: Preset {hw_preset_id_unknown}" in tooltip_hw_eq_unknown

        # EQ Type None
        tooltip_eq_none = self.tooltip_manager.get_tooltip(is_connected=True, battery_level=70, battery_status_text="BATTERY_AVAILABLE", chatmix_value=64, active_eq_type=None, current_custom_eq_name=None, current_hw_preset_id=None)
        assert "EQ: Unknown" in tooltip_eq_none


if __name__ == "__main__":
    unittest.main()
