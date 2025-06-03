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

# HID Report Details (Placeholders - REQUIRES DISCOVERY AND VERIFICATION)
# --------------------------------------------------------------------------
# The following constants are placeholders for direct HID communication with the
# SteelSeries Arctis Nova 7. These values are UNKNOWN and MUST be determined by
# analyzing USB HID reports, as outlined in the README.md section
# '## Discovering HID Report Details for Direct Communication'.
#
# Direct HID communication can allow for features not available through
# `headsetcontrol` or reduce reliance on it.
#
# Common properties of HID reports for headsets:
# - Report ID: Often the first byte of the report. Can be 0 if not used.
# - Command Bytes: Specific byte sequences that trigger an action or request data.
# - Data Payload: Bytes following the command that carry parameters or returned values.
# - Report Length: Total length of the report in bytes (e.g., 32, 64). This can
#                  sometimes vary depending on the report or interface.

# Example: (These are purely illustrative and NOT real values for Arctis Nova 7)
# REPORT_ID_FEATURE_OUTPUT = 0x06 # Example: Report ID for sending (Output) Feature reports
# REPORT_ID_FEATURE_INPUT = 0x07  # Example: Report ID for receiving (Input) Feature reports
# REPORT_LENGTH_FEATURE = 64      # Example: Length in bytes for feature reports

# --- Placeholders for Arctis Nova 7 ---

# Output Report ID (Host to Device) for sending commands.
# Might be a specific value (e.g., 0x01 - 0xFF) or 0x00 if not using numbered reports
# for the primary command interface.
HID_REPORT_ID_COMMAND_OUTPUT = 0x00 # Placeholder: e.g., 0x06 or specific SteelSeries command report ID

# Input Report ID (Device to Host) for receiving status/data.
# Often different from the output report ID.
HID_REPORT_ID_DATA_INPUT = 0x00 # Placeholder: e.g., 0x07 or specific SteelSeries data report ID

# General length in bytes for command/data reports.
# SteelSeries devices often use 32 or 64 bytes. This might need to be specific
# per command or report ID.
HID_REPORT_LENGTH = 64 # Placeholder: Common length, verify per report.

# Specific command sequences (byte arrays).
# These would be sent as part of the data payload, possibly after the Report ID.

# Example: Get Battery Status
# This command would be sent to the device.
HID_CMD_GET_BATTERY = [0xBA, 0x77] # Placeholder: Entirely speculative command bytes
# Expected response format for battery:
# - Might be in a specific byte of the input report.
# - Might include report ID, command echo, level, charging status.
# HID_RESPONSE_BATTERY_BYTE_INDEX = 2 # Placeholder: e.g., byte index for battery level
# HID_RESPONSE_BATTERY_CHARGING_BIT = 0x80 # Placeholder: e.g., a bit indicating charging

# Example: Get Sidetone Status
HID_CMD_GET_SIDETONE = [0x51, 0x00] # Placeholder
# Expected response format for sidetone:
# HID_RESPONSE_SIDETONE_BYTE_INDEX = 3 # Placeholder

# Example: Set Sidetone Level
# This would likely include the sidetone level as a parameter.
# e.g., [0x51, 0x01, level_byte]
HID_CMD_SET_SIDETONE_PREFIX = [0x51, 0x01] # Placeholder: Command prefix, level to be appended

# Example: Get EQ settings
HID_CMD_GET_EQ = [0xEE, 0x00] # Placeholder

# Example: Get Active EQ Preset ID
HID_CMD_GET_ACTIVE_PRESET = [0xEE, 0x01] # Placeholder

# Note: Some features might use standard HID Usages (e.g., Telephony page for mute)
# rather than custom vendor-defined reports. This also needs investigation.

# REFRESH_INTERVAL_MS is no longer used by SystemTrayIcon directly for its main timer.
# Kept for potential other uses or if a fixed interval is ever needed again.
REFRESH_INTERVAL_MS = 1000 

DEFAULT_CHAT_APP_IDENTIFIERS = ["Discord"]