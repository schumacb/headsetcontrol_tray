import os
from pathlib import Path

# Application Details
APP_NAME = "SteelSeriesHeadsetTray"
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

# HID Report details (Placeholders - these need to be accurately determined for Arctis Nova 7)
# These are highly speculative and need verification via USB sniffing or documentation.
# Report ID for sending commands might be specific.
# Common report length for SteelSeries devices is 64 bytes or 32 bytes.
# Example:
# HID_REPORT_ID_COMMAND = 0x06 # Might be this or another value, or not used if using feature reports
# HID_CMD_GET_BATTERY = [0xBA, 0x77] # Example command bytes
# HID_CMD_GET_SIDETONE = [0x51, 0x00] # Example
# HID_CMD_GET_EQ = [0xEE, 0x00] # Example
# HID_CMD_GET_ACTIVE_PRESET = [0xEE, 0x01] # Example

# Update interval for tray data (milliseconds)
REFRESH_INTERVAL_MS = 30000  # 30 seconds for battery/status