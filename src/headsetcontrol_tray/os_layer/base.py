import abc
from pathlib import Path
import subprocess
from typing import Any

# Forward declaration for hid module if not directly importing it yet,
# or assume it will be available in implementing classes.
# If 'hid' is a specific library like 'hidapi', ensure it's handled.
# For now, using 'Any' as a placeholder for hid.Device.
HidDevice = Any


class HIDManagerInterface(abc.ABC):
    """Abstract base class for HID device management operations."""

    @abc.abstractmethod
    def find_potential_hid_devices(self) -> list[dict[str, Any]]:
        """Enumerates potential HID devices based on predefined criteria (e.g., VID, PID)."""

    @abc.abstractmethod
    def sort_hid_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sorts a list of HID device information dictionaries by preference."""

    @abc.abstractmethod
    def connect_device(self) -> tuple[HidDevice | None, dict[str, Any] | None]:
        """
        Attempts to connect to a suitable HID device from the sorted list.
        Returns a tuple containing the hid.Device object and its info dictionary, or (None, None) if connection fails.
        """

    @abc.abstractmethod
    def ensure_connection(self) -> bool:
        """
        Ensures that a connection to a suitable HID device is active.
        Returns True if connected, False otherwise.
        """

    @abc.abstractmethod
    def get_hid_device(self) -> HidDevice | None:
        """Returns the active hid.Device object if connected, otherwise None."""

    @abc.abstractmethod
    def get_selected_device_info(self) -> dict[str, Any] | None:
        """Returns the device info dictionary of the selected HID device."""

    @abc.abstractmethod
    def close(self) -> None:
        """Closes the connection to the HID device."""


class OSInterface(abc.ABC):
    """Abstract base class for OS-specific operations."""

    @abc.abstractmethod
    def get_config_dir(self) -> Path:
        """Returns the OS-specific configuration directory path for the application."""

    @abc.abstractmethod
    def get_data_dir(self) -> Path:
        """
        Returns the OS-specific data directory path for the application
        (e.g., for icons, non-config data).
        """

    @abc.abstractmethod
    def get_os_name(self) -> str:
        """Returns a string identifying the operating system (e.g., 'linux', 'windows', 'macos')."""

    @abc.abstractmethod
    def needs_device_setup(self) -> bool:
        """
        Checks if any OS-specific device setup (e.g., udev rules on Linux, driver checks on Windows)
        is required for the application to function correctly.
        """

    @abc.abstractmethod
    def perform_device_setup(
        self, ui_parent: Any = None,
    ) -> tuple[bool, subprocess.CompletedProcess | None, Exception | None]:
        """
        Initiates the OS-specific device setup process.
        This might involve running scripts with elevated privileges or guiding the user.

        Args:
            ui_parent: Optional reference to a parent UI element for displaying dialogs.

        Returns:
            True if setup was attempted or completed successfully, False otherwise or if no action was taken.
        """

    @abc.abstractmethod
    def get_hid_manager(self) -> HIDManagerInterface:
        """
        Returns an instance of a class implementing HIDManagerInterface,
        configured for the current OS.
        """
