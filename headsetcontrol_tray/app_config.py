import os
from pathlib import Path

# Application Details
APP_NAME = "SteelSeries Arctis Nova 7"
ORGANIZATION_NAME = "YourOrganization" # Optional: For QSettings

# Headset USB Identifiers
STEELSERIES_VID = 0x1038

# Product IDs for Arctis Nova 7 variants
ARCTIS_NOVA_7_USER_PID = 0x2202 # From user's udev rule and logs
ARCTIS_NOVA_7_WIRELESS_PID = 0x12dd # Generic wireless version
ARCTIS_NOVA_7X_WIRELESS_PID = 0x12da # Xbox variant
ARCTIS_NOVA_7P_WIRELESS_PID = 0x12db # PlayStation variant


# List of PIDs to try connecting to, user's PID prioritized
TARGET_PIDS = [
    ARCTIS_NOVA_7_USER_PID,        # This is 0x2202 (decimal 8706)
    ARCTIS_NOVA_7_WIRELESS_PID,    # This is 0x12dd (decimal 4829)
    ARCTIS_NOVA_7X_WIRELESS_PID,   # This is 0x12da (decimal 4826)
    ARCTIS_NOVA_7P_WIRELESS_PID,   # This is 0x12db (decimal 4827)
]

# Configuration File
CONFIG_DIR = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / ".config")) / "steelseries_tray"
CONFIG_FILE = CONFIG_DIR / "settings.json"
CUSTOM_EQ_CURVES_FILE = CONFIG_DIR / "custom_eq_curves.json"

# Default settings
DEFAULT_SIDETONE_LEVEL = 64  # Mid-range
DEFAULT_INACTIVE_TIMEOUT = 15  # minutes
DEFAULT_EQ_PRESET_ID = 0 # Usually 'Flat' or first hardware preset
DEFAULT_CUSTOM_EQ_CURVE_NAME = "Flat"

# Default EQ Curves (Name: [10 band values from -10 to 10])
# Frequencies (approximate for reference): 31Hz, 62Hz, 125Hz, 250Hz, 500Hz, 1kHz, 2kHz, 4kHz, 8kHz, 16kHz
DEFAULT_EQ_CURVES = {
    "Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Bass Boost": [6, 5, 4, 2, 1, 0, 0, 0, 0, 0],
    "Treble Boost": [0, 0, 0, 0, 0, 1, 2, 3, 4, 5],
    "Vocal Clarity": [-2, -1, 0, 2, 3, 3, 2, 1, 0, -1],
    "Focus (FPS)": [-3, -2, -1, 0, 1, 2, 3, 4, 2, 1] # Example for footsteps & clarity
}

# Sidetone levels (0-128, example steps for menu)
SIDETONE_OPTIONS = {
    "Off": 0,
    "Low": 32,
    "Medium": 64,
    "High": 96,
    "Max": 128
}
# Sidetone can also be a slider from 0-128. Using a slider action.

# Inactive timeout options (0-90 minutes)
INACTIVE_TIMEOUT_OPTIONS = {
    "Disabled": 0,
    "15 minutes": 15,
    "30 minutes": 30,
    "45 minutes": 45,
    "60 minutes": 60,
    "90 minutes": 90
}

# Hardware EQ Preset Names (Assuming 4 presets, names might vary)
HARDWARE_EQ_PRESET_NAMES = {
    0: "Preset 1 (Default)",
    1: "Preset 2",
    2: "Preset 3",
    3: "Preset 4"
}

# HID Report Details (Derived from HeadsetControl source code - See HID_RESEARCH.md)
# ------------------------------------------------------------------------------------
# The following constants are based on analysis of Sapd/HeadsetControl for
# SteelSeries Arctis Nova 7 (and variants).
#
# General HID Configuration for Arctis Nova 7 Features:
# - Vendor ID: 0x1038 (STEELSERIES_VID)
# - Product IDs: See TARGET_PIDS (e.g., 0x2202 for Arctis Nova 7)
# - Interface: 3
# - Usage Page: 0xffc0
# - Usage ID: 0x0001
# - Report Size: 64 bytes (reports are typically padded to this length)

# --- Primary HID Interface Characteristics ---
# Most commands use this configuration.
# The first byte of the output report is often 0x00. This might be:
#   a) A specific Report ID for this interface/usage page.
#   b) A conventional first byte if the interface uses unnumbered reports for these commands.
#   This needs to be handled correctly by the HID writing function.
#   If it's a Report ID, python-hid's device.write() expects it as the first byte.
#   If it's not a Report ID (i.e., unnumbered reports), it should be omitted if the library handles that,
#   or it's part of the actual command data sent after a (potentially zero) report ID.
#   For simplicity, we'll define it as part of the command if it's fixed for many commands.
#   HeadsetControl's C code writes these bytes directly, often starting with 0x00.

HID_REPORT_INTERFACE = 3
HID_REPORT_USAGE_PAGE = 0xffc0
HID_REPORT_USAGE_ID = 0x0001 # Equivalent to 0x1 in headsetcontrol
HID_REPORT_FIXED_FIRST_BYTE = 0x00 # Common first byte for many commands

# --- Commands (Payloads typically follow the HID_REPORT_FIXED_FIRST_BYTE) ---

# Get Battery Status & ChatMix (Shared command and response)
# Command to trigger status read:
HID_CMD_GET_STATUS = [HID_REPORT_FIXED_FIRST_BYTE, 0xb0] # Results in an 8-byte input report
# Response parsing (byte indices in the 8-byte input report):
HID_RES_STATUS_BATTERY_LEVEL_BYTE = 2    # Raw value 0x00-0x04
HID_RES_STATUS_BATTERY_STATUS_BYTE = 3   # 0x00=offline, 0x01=charging
HID_RES_STATUS_CHATMIX_GAME_BYTE = 4     # Game component (0-100)
HID_RES_STATUS_CHATMIX_CHAT_BYTE = 5     # Chat component (0-100)
HID_INPUT_REPORT_LENGTH_STATUS = 8

# Sidetone
HID_CMD_SET_SIDETONE_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0x39] # Append mapped level_value
# level_value mapping: 0-25->0x00, 26-50->0x01, 51-75->0x02, >75->0x03

# Inactive Time (Auto Shutdown)
HID_CMD_SET_INACTIVE_TIME_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0xa3] # Append minutes

# Equalizer Bands (Custom)
HID_CMD_SET_EQ_BANDS_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0x33] # Append 10 band_values, then 0x00
# Each band_value = 0x14 + float_value (-10 to +10)

# Bluetooth When Powered On
HID_CMD_SET_BT_POWER_ON_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0xb2] # Append status (0x00 or 0x01)
HID_CMD_SAVE_SETTINGS = [0x06, 0x09] # Separate command, different first byte (potential Report ID 0x06)

# Bluetooth Call Volume Configuration
HID_CMD_SET_BT_CALL_VOLUME_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0xb3] # Append level (0x00-0x02)

# Microphone Mute LED Brightness
HID_CMD_SET_MIC_LED_BRIGHTNESS_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0xae] # Append brightness (0x00-0x03)

# Microphone Volume
HID_CMD_SET_MIC_VOLUME_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0x37] # Append mapped level (0x00-0x07)

# Volume Limiter
HID_CMD_SET_VOLUME_LIMITER_PREFIX = [HID_REPORT_FIXED_FIRST_BYTE, 0x3a] # Append status (0x00 or 0x01)

# --- Old Placeholders (Commented out for reference, to be removed later) ---
# # HID_REPORT_ID_COMMAND = 0x06 # Might be this or another value, or not used if using feature reports
# # HID_CMD_GET_BATTERY = [0xBA, 0x77] # Example command bytes
# # HID_CMD_GET_SIDETONE = [0x51, 0x00] # Example
# # HID_CMD_GET_EQ = [0xEE, 0x00] # Example
# # HID_CMD_GET_ACTIVE_PRESET = [0xEE, 0x01] # Example

# REFRESH_INTERVAL_MS is no longer used by SystemTrayIcon directly for its main timer.
# Kept for potential other uses or if a fixed interval is ever needed again.
REFRESH_INTERVAL_MS = 1000 

DEFAULT_CHAT_APP_IDENTIFIERS = ["Discord"]