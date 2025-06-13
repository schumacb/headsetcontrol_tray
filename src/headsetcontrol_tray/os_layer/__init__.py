"""OS-specific layer for headsetcontrol_tray.

This module provides an abstraction layer to handle OS-specific functionalities,
such as HID device interaction and system integration. It dynamically determines
the operating system at runtime and loads the appropriate implementation.
"""
import platform

from .linux import LinuxImpl
from .macos import MacOSImpl
from .windows import WindowsImpl


def get_os_platform():
    """
    Detect the current operating system and return an appropriate OS-specific implementation.

    The function uses `platform.system()` to identify the OS and then instantiates
    and returns the corresponding class (`LinuxImpl`, `MacOSImpl`, or `WindowsImpl`).

    Returns:
        An instance of LinuxImpl, MacOSImpl, or WindowsImpl based on the detected OS.

    Raises:
        NotImplementedError: If the operating system is not Linux, Windows, or macOS (Darwin).
    """
    system = platform.system()
    if system == "Linux":
        return LinuxImpl()
    elif system == "Windows":
        return WindowsImpl()
    elif system == "Darwin":  # Darwin is the system name for macOS
        return MacOSImpl()
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")
