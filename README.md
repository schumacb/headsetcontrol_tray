# HeadsetControl Tray

A system tray application for controlling headsets, particularly those compatible with `headsetcontrol`.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.10 or higher
- `uv` (a fast Python package installer and resolver)

### Installing `uv`

You can install `uv` using pip:

```bash
pip install uv
```

Alternatively, you can use the official installer script:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Make sure to add `uv` to your PATH if it's not already. If you installed with `pip` as a user, this might be `~/.local/bin`.

### Development Setup

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Initialize the project and create a virtual environment:**
    If you are setting up the project for the first time using `uv`, it can initialize the project structure. However, since you've cloned an existing project, you'll primarily use `uv` to manage the environment and dependencies.

    Create a virtual environment:
    ```bash
    uv venv
    ```
    This will create a `.venv` directory in the project root.

3.  **Activate the virtual environment:**
    On macOS and Linux:
    ```bash
    source .venv/bin/activate
    ```
    On Windows:
    ```bash
    .venv\Scripts\activate
    ```

4.  **Install dependencies:**
    The project dependencies are defined in `pyproject.toml`. To install them using `uv`:
    ```bash
    uv pip sync
    ```
    If the project uses extras, you might use:
    ```bash
    uv pip sync --all-extras
    ```

5.  **Adding new dependencies:**
    To add a new runtime dependency:
    ```bash
    uv add <package-name>
    ```
    To add a new development dependency:
    ```bash
    uv add --dev <package-name>
    ```
    This will update your `pyproject.toml` and install the package.

### Running the Application

To run the application:

```bash
python -m headsetcontrol_tray
```

Alternatively, you can use `uv` to run scripts defined in `pyproject.toml` (if any) or execute commands within the managed environment:

```bash
uv run python -m headsetcontrol_tray
```

## Features and Limitations

**Interacting with Your Headset**

This application interacts directly with your SteelSeries headset using HID commands.

**Supported Readable Information:**
*   Battery Level: You can view the current battery percentage.
*   Charging Status: Indicates if the headset is currently charging.
*   ChatMix Value: Shows the current ChatMix balance.

**Supported Controllable Settings (Write-Only for Some Aspects):**
You can control and set the following features on your headset:
*   Sidetone Level
*   Inactive Timeout (Auto-shutdown)
*   Equalizer (EQ) Band Values
*   Equalizer (EQ) Presets

**Current Limitations on Reading Settings:**
*   While you can *set* the Sidetone Level, Inactive Timeout, EQ Band Values, and EQ Presets, the application currently cannot *read back* their current values from the headset after they have been set or changed externally.
*   Reason: Direct HID commands for reading these specific current states (Sidetone, Inactive Timeout, EQ configuration) are not implemented in this version of the application. The application will log a warning if an attempt is made to fetch these values, and the UI may not display them.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details.

## Discovering HID Report Details for Direct Communication
To enable direct HID communication with the SteelSeries Arctis Nova 7 headset, specific HID report details (report IDs, command structures, data formats) must be identified. This information is hardware-specific and not typically published by manufacturers. Here's a general approach to discovering these details:

### 1. USB Sniffing
This is the most common method for reverse-engineering USB protocols.
- **Tools for Windows:**
    - Wireshark (with USBPcap): A powerful network protocol analyzer that can also capture USB traffic. USBPcap is a driver that allows Wireshark to capture USB packets.
    - USBlyzer: A commercial USB protocol analyzer with a free trial.
- **Tools for Linux:**
    - `usbmon`: A kernel module for capturing USB traffic. You can use Wireshark to view the captured data.
    - `lsusb` and `usbhid-dump`: Useful for getting basic information about USB HID devices.
- **Process:**
    1. Start capturing USB traffic on the port where the headset is connected.
    2. Use the official SteelSeries GG software (or any software that controls the headset features you're interested in) to change settings (e.g., sidetone, EQ, check battery).
    3. Stop the capture and analyze the USB packets exchanged between the software and the headset. Look for patterns, specific byte sequences that change with different settings, and potential report IDs.
    4. Focus on `HID` class-specific requests, particularly `SET_REPORT` and `GET_REPORT` (or `Interrupt OUT` and `Interrupt IN` transfers for HID devices).

### 2. Analyzing `headsetcontrol`
The `headsetcontrol` utility (which this application currently uses) might already contain some of the necessary HID information or clues.
- **Source Code:** Explore the source code of `headsetcontrol`: [https://github.com/Sapd/HeadsetControl](https://github.com/Sapd/HeadsetControl)
- **Debugging:** Run `headsetcontrol` with verbose or debug flags if available, or use tools like `strace` (on Linux) or a debugger to observe its interactions with the HID device at a lower level.

### 3. Community Resources and Similar Projects
- Search online forums (e.g., Reddit, hardware hacking forums) for discussions related to SteelSeries headsets or HID reverse-engineering.
- Look for other open-source projects that aim to control SteelSeries devices. They might have already done some of this work. For example, the `rivalcfg` project for SteelSeries mice, while for different devices, might offer insights into how SteelSeries HID protocols can be structured.

### 4. SteelSeries GG Software
While unlikely to provide direct HID details, observing the behavior of the SteelSeries GG software itself (e.g., configuration files it creates, logs it generates in debug mode) might provide subtle hints.

**Important Considerations:**
- **HID Interfaces:** Headsets often expose multiple HID interfaces. You'll need to identify the correct interface for sending control commands and receiving status updates. The `HeadsetService.py` already has logic to enumerate and select interfaces.
- **Report IDs:** HID reports can be numbered (using a report ID byte) or unnumbered. This needs to be determined for each command/feature.
- **Data Structure:** The payload of each report needs to be decoded. This includes understanding the meaning of each byte, byte order (endianness), and data types.

Discovering these details is an iterative process and can be time-consuming. Good luck!
