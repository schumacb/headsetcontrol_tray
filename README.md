# HeadsetControl Tray

A system tray application for controlling SteelSeries headsets (and potentially others) via direct HID communication. It aims to provide features similar to those found in tools like `headsetcontrol`.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.10 or higher
- `uv` (a fast Python package installer and resolver)

### System Dependencies (Linux)

In addition to the Python prerequisites, this application requires certain system libraries to function correctly, especially for direct HID access and GUI operation on Linux:

- **`libhidapi-hidraw0`**: For HIDAPI to communicate with USB HID devices.
  - Installation: `sudo apt-get install libhidapi-hidraw0` (Debian/Ubuntu)
- **XCB Libraries (for Qt GUI)**: Several XCB related libraries are needed for Qt to interface with the X server. Key libraries identified during testing include:
  - **`libxkbcommon-x11-0`**: For keyboard input handling with XCB.
    - Installation: `sudo apt-get install libxkbcommon-x11-0` (Debian/Ubuntu)
  - **`libxcb-cursor0`**: For XCB cursor support, mentioned by Qt.
    - Installation: `sudo apt-get install libxcb-cursor0` (Debian/Ubuntu)
  - A broader set of XCB libraries might be necessary for full functionality on all systems. Common runtime libraries include `libxcb-icccm4`, `libxcb-image0`, `libxcb-keysyms1`, `libxcb-randr0`, `libxcb-render-util0`, `libxcb-shape0`, `libxcb-xinerama0`. Installing `libxcb1-dev` (or its equivalent for your distribution) often pulls in many necessary development headers and runtime libraries, though development packages are not strictly needed for runtime.

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

## Code Quality and Analysis Tools

This project utilizes several tools to maintain code quality, enforce consistency, and identify potential issues:

*   **Ruff**: An extremely fast Python linter and formatter, written in Rust. Used for identifying code style issues, potential bugs, and for auto-formatting the code.
*   **MyPy**: A static type checker for Python. Used to enforce type hints and catch type-related errors.
*   **Radon**: A Python tool that computes various code metrics, including cyclomatic complexity and maintainability index. Used to identify overly complex code.
*   **Vulture**: A tool for finding unused code (dead code) in Python programs. Used to help keep the codebase clean.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details.