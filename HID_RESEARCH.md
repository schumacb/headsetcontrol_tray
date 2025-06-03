# HID Report Details for SteelSeries Arctis Nova 7

This document summarizes HID report information for the SteelSeries Arctis Nova 7,
derived from the source code of [HeadsetControl by Sapd](https://github.com/Sapd/HeadsetControl),
specifically the `src/devices/steelseries_arctis_nova_7.c` file.

## General Configuration

-   **Vendor ID:** `0x1038` (SteelSeries)
-   **Product IDs (Arctis Nova 7 Variants):**
    -   `0x2202` (Arctis Nova 7 - matches `ARCTIS_NOVA_7_USER_PID`)
    -   `0x2206` (Arctis Nova 7X)
    -   `0x2258` (Arctis Nova 7X v2)
    -   `0x220a` (Arctis Nova 7P)
    -   `0x223a` (Arctis Nova 7 Diablo IV Edition)
-   **Interface Details (for all below features):**
    -   Usage Page: `0xffc0`
    -   Usage ID: `0x0001` (Note: `headsetcontrol` uses `0x1` for usageid, which is equivalent)
    -   Interface Number: `3`
-   **Report Size:** Most reports are padded to `64 bytes`.
-   **Report ID Byte:** Many command reports sent via `hid_write` start with `0x00`. This could be:
    -   A specific report ID used on this interface.
    -   An indication that the interface uses unnumbered reports, and `0x00` is a conventional first byte for some commands or padding.
    For `python-hid`, if the device expects a Report ID, it should be the first byte of the buffer. If it's an unnumbered report, the Report ID byte is omitted. This needs to be tested during implementation. The `HeadsetService` `_write_hid_report` and `_read_hid_report` will need to correctly handle this (e.g. by having `report_id=0x00` if that's indeed the ID, or by passing data that starts with the actual command if `0x00` is not a report ID itself).

## Feature-Specific HID Reports

All reports are 64 bytes unless specified. The first byte listed is often `0x00`.

### 1. Sidetone

-   **Command:** `arctis_nova_7_send_sidetone`
-   **HID Report (Output):** `{ 0x00, 0x39, level_value, 0x00, ..., 0x00 }`
-   **`level_value` Mapping:**
    -   Input `0-25`  -> `0x00`
    -   Input `26-50` -> `0x01`
    -   Input `51-75` -> `0x02`
    -   Input `>75`   -> `0x03`

### 2. Inactive Time (Auto Shutdown)

-   **Command:** `arctis_nova_7_send_inactive_time`
-   **HID Report (Output):** `{ 0x00, 0xa3, minutes, 0x00, ..., 0x00 }`
    -   `minutes`: Desired timeout in minutes.

### 3. Battery Status & ChatMix (Shared Read Command)

-   **Read Trigger Command:** `arctis_nova_7_read_device_status` sends an Output report:
    -   `{ 0x00, 0xb0, 0x00, ..., 0x00 }` (report is 2 bytes payload, padded to 64 for sending)
-   **Response (Input Report):** Reads `8 bytes`. Let's call this `data_read`.
    -   **Battery Level:**
        -   `data_read[2]`: Raw battery value (`0x00` to `0x04`).
            -   Mapped: `0` -> 0%, `1` -> 25%, `2` -> 50%, `3` -> 75%, `4` -> 100% (approx. by HeadsetControl's `map` function)
        -   `data_read[3]`: Status
            -   `0x00`: Offline / Not connected properly
            -   `0x01`: Charging
            -   Other values (e.g., `0x02` or higher observed on some devices): Discharging / Available
    -   **ChatMix:**
        -   `data_read[4]`: Game volume component (0-100 decimal).
        -   `data_read[5]`: Chat volume component (0-100 decimal).
        -   HeadsetControl maps these: `game_mapped = map(data_read[4], 0, 100, 0, 64)` and `chat_mapped = map(data_read[5], 0, 100, 0, -64)`. Final value: `64 - (chat_mapped + game_mapped)`. This results in a 0-128 scale where <64 is more game, >64 is more chat.

### 4. Equalizer Presets

-   **Command:** `arctis_nova_7_send_equalizer_preset`
-   This function ultimately calls `arctis_nova_7_send_equalizer` with predefined band values.
-   **Presets (0-3):** Flat, Bass Boost, Focus, Smiley (custom definitions in the C file).

### 5. Equalizer Bands (Custom)

-   **Command:** `arctis_nova_7_send_equalizer`
-   **HID Report (Output):** `{ 0x00, 0x33, band1_val, band2_val, ..., band10_val, 0x00, 0x00, ..., 0x00 }`
    -   There are 10 bands.
    -   `bandX_val`: Calculated as `0x14 + float_value`.
        -   `float_value` is from -10.0 to +10.0 (e.g. if `float_value` is 0, byte is `0x14`; if -10, byte is `0x14 - 10 = 0x0A`; if +10, byte is `0x14 + 10 = 0x1E`).
    -   The report seems to be `{ 0x00, 0x33, 10_bytes_for_bands, 0x00 (at index 12), ...padding }`. The C code is `data[i+2]` for bands and `data[settings->size + 3] = 0x0;` which is `data[10+3] = data[13] = 0x0;`. This seems off by one, it should likely be `data[settings->size+2]` or the byte at index 12 is `band10_val` and byte at index 2 is `band1_val`.
        Re-checking: `data[i+2]` means `data[2]` is band 0, `data[11]` is band 9. So `data[settings->size + 2]` i.e. `data[10+2] = data[12]` is the one set to `0x00`.

### 6. Bluetooth When Powered On

-   **Command:** `arctis_nova_7_bluetooth_when_powered_on`
-   **HID Report (Output):** `{ 0x00, 0xb2, status, 0x00, ..., 0x00 }`
    -   `status`: `0x00` (Off) or `0x01` (On).
-   **Follow-up Command (Save):** `{ 0x06, 0x09, 0x00, ..., 0x00 }`
    -   This report ID `0x06` is different.

### 7. Bluetooth Call Volume Configuration

-   **Command:** `arctis_nova_7_bluetooth_call_volume`
-   **HID Report (Output):** `{ 0x00, 0xb3, level, 0x00, ..., 0x00 }`
    -   `level`:
        -   `0x00`: Do nothing
        -   `0x01`: Lower game volume by 12dB during call
        -   `0x02`: Mute game volume during call

### 8. Microphone Mute LED Brightness

-   **Command:** `arctis_nova_7_mic_light`
-   **HID Report (Output):** `{ 0x00, 0xae, brightness, 0x00, ..., 0x00 }`
    -   `brightness`: `0x00` (Off) to `0x03` (Max).

### 9. Microphone Volume

-   **Command:** `arctis_nova_7_mic_volume`
-   **HID Report (Output):** `{ 0x00, 0x37, level, 0x00, ..., 0x00 }`
    -   `level`: Input (0-128) is mapped to `0x00` (Off) to `0x07` (Max).
        -   Mapping: `input_level / 16`, capped at `0x07`.

### 10. Volume Limiter

-   **Command:** `arctis_nova_7_volume_limiter`
-   **HID Report (Output):** `{ 0x00, 0x3a, status, 0x00, ..., 0x00 }`
    -   `status`: `0x00` (Off) or `0x01` (On).

---
This information should be sufficient to start populating `app_config.py` and
begin planning the implementation of direct HID control functions.
