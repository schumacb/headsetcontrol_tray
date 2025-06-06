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

## Visualizing the Architecture (C4 Model)

The architecture of this application is documented using the C4 model. The model is defined in the `architecture.dsl` file using the Structurizr DSL.

Structurizr is a lightweight, code-based approach to creating software architecture diagrams. The C4 model (Context, Containers, Components, and Code) provides a hierarchical way to describe software architecture at different levels of detail.

### Rendering the Diagrams

You can render these diagrams locally using Structurizr Lite, which can be run via Docker.

1.  **Export Diagrams (PlantUML & Mermaid):**
    The following commands will export the diagrams defined in `architecture.dsl` into PlantUML and Mermaid formats. The exported files will be placed in a `structurizr-exports` directory.
    ```bash
    # Export to PlantUML
    docker run -it --rm -v $(pwd):/usr/local/structurizr structurizr/lite export -format plantuml -workspace architecture.dsl
    # Export to Mermaid
    docker run -it --rm -v $(pwd):/usr/local/structurizr structurizr/lite export -format mermaid -workspace architecture.dsl
    ```

2.  **Render PlantUML to SVG:**
    After exporting, you can render the PlantUML files into SVG images. For example, to render the System Context diagram:
    ```bash
    docker run -it --rm -v $(pwd):/usr/local/structurizr structurizr/lite render -format plantuml -path architecture.dsl/structurizr-PlantUMLSystemContext-001.puml
    ```
    You'll need to adjust the path for other diagrams (e.g., `structurizr-PlantUMLContainerView-001.puml`, `structurizr-PlantUMLComponentView-001.puml`). The rendered SVG files will be placed in the same directory as the `.puml` files (i.e., within `architecture.dsl/`).

3.  **Using Structurizr Lite Web Interface:**
    Alternatively, you can run the Structurizr Lite web server to view and interact with the diagrams in your browser:
    ```bash
    docker run -it --rm -p 8080:8080 -v $(pwd):/usr/local/structurizr structurizr/lite
    ```
    Then, open `http://localhost:8080` in your web browser. The workspace should be automatically loaded from `architecture.dsl`.

This allows for easy visualization and exploration of the system's architecture at various levels of detail.

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
