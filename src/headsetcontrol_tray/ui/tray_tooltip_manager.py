"""Manages the generation of tooltip strings for the system tray icon."""

from headsetcontrol_tray import app_config

from .equalizer_editor_widget import EQ_TYPE_CUSTOM, EQ_TYPE_HARDWARE

# ChatMix Values for display logic (could be moved to a shared constants area)
CHATMIX_VALUE_FULL_CHAT = 0
CHATMIX_VALUE_BALANCED = 64
CHATMIX_VALUE_FULL_GAME = 128  # Max value for normalization


class TrayTooltipManager:
    """Generates tooltip strings for the system tray icon."""

    def __init__(self) -> None:
        """Initializes the TrayTooltipManager."""
        # The config_manager_getter argument was removed as it was unused.
        # All necessary data is passed directly to get_tooltip method.

    def _get_chatmix_display_string(self, chatmix_val: int | None) -> str:
        """Helper to format chatmix value for display."""
        if chatmix_val is None:
            return "N/A"
        percentage = round((chatmix_val / float(CHATMIX_VALUE_FULL_GAME)) * 100)
        if chatmix_val == CHATMIX_VALUE_FULL_CHAT:
            return f"Chat ({percentage}%)"
        if chatmix_val == CHATMIX_VALUE_BALANCED:
            return f"Balanced ({percentage}%)"
        if chatmix_val == CHATMIX_VALUE_FULL_GAME:
            return f"Game ({percentage}%)"
        # For values between the main points
        return f"{chatmix_val} ({percentage}%)"

    def get_tooltip(
        self,
        *, # Make subsequent arguments keyword-only
        is_connected: bool,
        battery_level: int | None,
        battery_status_text: str | None,  # e.g. "BATTERY_CHARGING", "BATTERY_FULL", "BATTERY_AVAILABLE"
        chatmix_value: int | None,
        active_eq_type: str | None,  # From ConfigManager: "custom" or "hardware"
        current_custom_eq_name: str | None,  # From ConfigManager
        current_hw_preset_id: int | None,  # From ConfigManager
    ) -> str:
        """
        Generates the tooltip string based on the provided headset and EQ status.

        Args:
            is_connected: True if the headset is connected.
            battery_level: Current battery level (0-100) or None.
            battery_status_text: String indicating battery status.
            chatmix_value: Current chatmix value or None.
            active_eq_type: The type of EQ currently active ('custom' or 'hardware').
            current_custom_eq_name: Name of the active custom EQ curve.
            current_hw_preset_id: ID of the active hardware EQ preset.

        Returns:
            A string formatted for use as a tooltip.
        """
        tooltip_parts = []

        if not is_connected:
            tooltip_parts.append("Headset disconnected")
        else:
            # Battery Tooltip Part
            if battery_level is not None:
                level_text = f"{battery_level}%"
                if battery_status_text == "BATTERY_CHARGING":
                    tooltip_parts.append(f"Battery: {level_text} (Charging)")
                elif battery_status_text == "BATTERY_FULL":  # Assuming "BATTERY_FULL" is a possible status
                    tooltip_parts.append(f"Battery: {level_text} (Full)")
                else:  # BATTERY_AVAILABLE or other
                    tooltip_parts.append(f"Battery: {level_text}")
            elif (
                battery_status_text == "BATTERY_UNAVAILABLE"
            ):  # A distinct status if level is None but known unavailable
                tooltip_parts.append("Battery: Unavailable")
            else:  # General fallback if no specific status but level is None
                tooltip_parts.append("Battery: N/A")

            # ChatMix Tooltip Part
            chatmix_str = self._get_chatmix_display_string(chatmix_value)
            tooltip_parts.append(f"ChatMix: {chatmix_str}")

            # EQ Tooltip Part
            eq_tooltip_text = "EQ: Unknown"
            if active_eq_type == EQ_TYPE_CUSTOM and current_custom_eq_name:
                eq_tooltip_text = f"EQ: {current_custom_eq_name}"
            elif active_eq_type == EQ_TYPE_HARDWARE and current_hw_preset_id is not None:
                # Fetching name from app_config.HARDWARE_EQ_PRESET_NAMES
                hw_preset_name = app_config.HARDWARE_EQ_PRESET_NAMES.get(
                    current_hw_preset_id, f"Preset {current_hw_preset_id}",
                )
                eq_tooltip_text = f"EQ: {hw_preset_name}"
            tooltip_parts.append(eq_tooltip_text)

        return "\n".join(tooltip_parts)
