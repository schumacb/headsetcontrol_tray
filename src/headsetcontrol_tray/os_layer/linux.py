"""Linux-specific implementation of the OSInterface.

This module provides the `LinuxImpl` class, which handles Linux-specific
operations such as determining configuration/data directories according to
XDG standards, managing udev rules for device permissions, and executing
helper scripts with elevated privileges using pkexec.
"""

import logging
import os
from pathlib import Path
import subprocess  # Already present, good.
from typing import Any

# First-party imports (application-specific)
from headsetcontrol_tray import app_config
from headsetcontrol_tray.exceptions import TrayAppInitializationError
from headsetcontrol_tray.hid_manager import HIDConnectionManager
from headsetcontrol_tray.udev_manager import UDEVManager

# Relative import for base interfaces within the same package is fine
from .base import HIDManagerInterface, OSInterface

# Assuming 'hid' will be importable in the context where HIDManagerInterface is implemented.
# For now, using 'Any' as a placeholder for hid.Device.
HidDevice = Any

logger = logging.getLogger(f"{app_config.APP_NAME}.os_layer.linux")

# pkexec exit codes (copied from app.py)
PKEXEC_EXIT_SUCCESS = 0
PKEXEC_EXIT_USER_CANCELLED = 126  # User cancelled authentication
PKEXEC_EXIT_AUTH_FAILED = 127  # Authentication failed or other error (e.g. no agent)


# LinuxHIDManager class removed


class LinuxImpl(OSInterface):
    """Linux-specific implementation of OSInterface."""

    def __init__(self) -> None:
        """Initializes the Linux OS interface implementation.

        This sets up instances of UDEVManager and HIDConnectionManager.
        """
        self._udev_manager = UDEVManager()
        self._hid_manager = HIDConnectionManager()  # Changed to HIDConnectionManager

    def get_config_dir(self) -> Path:
        """Gets the Linux-specific configuration directory for the application.

        Follows XDG Base Directory Specification: uses $XDG_CONFIG_HOME if set,
        otherwise defaults to ~/.config/. App name is appended.

        Returns:
            A Path object to the configuration directory.
        """
        config_home = os.getenv("XDG_CONFIG_HOME")
        if config_home:
            return Path(config_home) / app_config.APP_NAME.lower().replace(" ", "_")
        return Path.home() / ".config" / app_config.APP_NAME.lower().replace(" ", "_")

    def get_os_name(self) -> str:
        """Returns the identifier for the Linux operating system.

        Returns:
            The string "linux".
        """
        return "linux"

    def needs_device_setup(self) -> bool:
        """Checks if udev rules need to be installed."""
        # This is a simplified check. UDEVManager might need a more direct method.
        # For now, we assume if create_rules_interactive() is called and generates details,
        # it implies setup is needed or was just attempted.
        # A more robust check would be to see if the rule file exists and has correct content.
        # This logic will likely be refined when UDEVManager is refactored.

        # Placeholder: A real check would involve verifying system state (e.g. rule file presence)
        # For now, let's assume UDEVManager can tell us this.
        # This might require adding a method like `are_rules_installed()` to UDEVManager.
        # As a temporary measure, this might always trigger the setup details generation
        # if no device is found by HeadsetService, and app.py would then call perform_device_setup.
        # The UDEVManager.create_rules_interactive() itself doesn't check, it just creates.
        # Let's defer the exact check to the refactoring of UDEVManager.
        # For now, if a device isn't found by hid_manager, this could be True.
        # This is a complex dependency. A simpler approach for now:
        # Assume setup is needed if the udev rule file doesn't exist with our content.
        # This is a rough check and might need root access or sudo to check /etc/udev/rules.d
        # which this class shouldn't do directly.
        # The UDEVManager's current `create_rules_interactive` is about *generating* the rules
        # and instructions, not checking.
        # For the purpose of this step, we'll rely on a future refined UDEVManager.
        # Let's assume for now it's always potentially needed if a device isn't auto-detected.
        # The HeadsetService currently creates UDEVManager and calls create_rules_interactive
        # if it can't find a device. This detail is then passed to app.py.
        # So, `needs_device_setup` could be true if `get_last_udev_setup_details` is not None,
        # implying an attempt was made because it was likely needed.
        # This is still indirect.
        # A better approach for UDEVManager: add `are_rules_installed()`
        # Use the new method in UDEVManager
        return not self._udev_manager.are_rules_installed()

    def _execute_udev_helper_script(self, temp_file_path: str, final_file_path: str) -> subprocess.CompletedProcess:
        """Executes the udev helper script using pkexec. (Copied from app.py)"""
        # Determine path to script relative to this file or a known location
        # Assuming this file is at src/headsetcontrol_tray/os_layer/linux.py
        current_script_dir = Path(__file__).parent
        # os_layer is inside headsetcontrol_tray, scripts is at repo root.
        # So, ../../scripts
        scripts_dir = (current_script_dir / ".." / ".." / "scripts").resolve()
        helper_script_path = scripts_dir / "install-udev-rules.sh"

        if not helper_script_path.is_file():  # Use is_file for better check
            logger.error("Helper script not found at %s", str(helper_script_path))
            # This exception type might need to be defined in a common place or use a generic one
            raise TrayAppInitializationError  # Rely on default message

        cmd = ["pkexec", str(helper_script_path), temp_file_path, final_file_path]
        logger.info("Attempting to execute with pkexec: %s", " ".join(cmd))
        try:
            # Note: S603 will flag this if not careful. Ensure helper_script_path is trusted.
            # Since it's bundled with the app, it's considered trusted.
            return subprocess.run(  # noqa: S603 # Script path is constructed internally and considered trusted.
                cmd,
                capture_output=True,
                text=True,
                check=False,  # We check returncode manually
            )
        except FileNotFoundError as e_fnf:  # pkexec itself not found
            logger.exception("pkexec command not found. Ensure PolicyKit is installed.")
            raise TrayAppInitializationError from e_fnf
        except subprocess.SubprocessError as e:
            logger.exception("Subprocess error during pkexec execution:")
            msg = f"Subprocess error: {e}"
            raise TrayAppInitializationError(msg) from e

    def perform_device_setup(
        self,
        ui_parent: Any = None,
    ) -> tuple[bool, subprocess.CompletedProcess | None, Exception | None]:
        """Guides the user through installing udev rules for Linux.

        This adapts logic from app.py's _handle_udev_permissions_flow.
        Returns a tuple: (success: bool, process_result: Optional[CompletedProcess], error: Optional[Exception])
        Actual success of pkexec script is communicated via UI by app.py.
        The ui_parent is expected to be a QWidget or similar that can host QMessageBox.
        """
        logger.info("Initiating Linux device setup (udev rules).")

        # 1. Generate the temporary rule file using UDEVManager
        if not self._udev_manager.create_rules_interactive():
            logger.error("Failed to create temporary udev rule file via UDEVManager.")
            # Communicate this failure via ui_parent if available
            # This part of UI handling might be better in app.py based on the return from this method.
            # For now, keeping it here for immediate feedback if ui_parent is provided.
            if ui_parent:
                try:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.critical(
                        ui_parent,
                        "Device Setup Error",
                        "Could not prepare device configuration (udev rules). Please check logs.",
                    )
                except ImportError:
                    logger.exception("PySide6 not available for showing error dialog in perform_device_setup.")
            # Return structure: success, process_result, error
            return False, None, TrayAppInitializationError("Failed to prepare udev rule details.")

        udev_details = self._udev_manager.get_last_udev_setup_details()
        if not udev_details:  # Should not happen if prepare_udev_rule_details succeeded
            logger.error("UDEVManager prepared rules but details are missing.")
            return False, None, TrayAppInitializationError("UDEVManager details missing after preparation.")

        temp_file = udev_details["temp_file_path"]
        final_file = udev_details["final_file_path"]

        logger.info("Executing udev helper script. Temp: %s, Final: %s", temp_file, final_file)

        execution_error: Exception | None = None
        process_result: subprocess.CompletedProcess | None = None
        success = False
        try:
            process_result = self._execute_udev_helper_script(temp_file, final_file)

            logger.info("pkexec process completed. Return code: %s", process_result.returncode)
            if process_result.stdout:
                logger.info("pkexec stdout:\n%s", process_result.stdout.strip())
            if process_result.stderr:
                logger.warning("pkexec stderr:\n%s", process_result.stderr.strip())

            if process_result.returncode == PKEXEC_EXIT_SUCCESS:
                logger.info("Udev rules installed successfully via pkexec.")
                success = True
            else:
                logger.warning("pkexec helper script failed with code %s.", process_result.returncode)
                # The error is implicitly in process_result,
                # no separate exception here unless pkexec itself failed to run.

        except TrayAppInitializationError as e:  # Errors from _execute_udev_helper_script itself
            logger.exception("Device setup failed before or during pkexec execution:")
            execution_error = e
        except Exception as e:  # Catch any other unexpected error
            logger.exception("An unexpected error occurred during perform_device_setup:")
            execution_error = e  # General exception

        return success, process_result, execution_error

    def get_hid_manager(self) -> HIDManagerInterface:
        """Returns the HID manager instance for Linux.

        Returns:
            An instance of a class implementing HIDManagerInterface.
        """
        return self._hid_manager
