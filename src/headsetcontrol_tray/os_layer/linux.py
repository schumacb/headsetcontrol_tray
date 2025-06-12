import logging
import os
from pathlib import Path
import subprocess
from typing import Any, Optional, Tuple

# Assuming 'hid' will be importable in the context where HIDManagerInterface is implemented.
# For now, using 'Any' as a placeholder for hid.Device.
HidDevice = Any

from .base import OSInterface, HIDManagerInterface
from .. import app_config # To get app name for paths, and later udev related constants
from ..udev_manager import UDEVManager # Will be used for needs_device_setup and perform_device_setup
from ..hid_manager import HIDConnectionManager # The concrete implementation of HIDManagerInterface
from ..exceptions import TrayAppInitializationError # For error handling in perform_device_setup

logger = logging.getLogger(f"{app_config.APP_NAME}.os_layer.linux")

# pkexec exit codes (copied from app.py)
PKEXEC_EXIT_SUCCESS = 0
PKEXEC_EXIT_USER_CANCELLED = 126 # User cancelled authentication
PKEXEC_EXIT_AUTH_FAILED = 127 # Authentication failed or other error (e.g. no agent)


class LinuxHIDManager(HIDManagerInterface):
    """Linux-specific HID Manager implementation."""
    def __init__(self):
        # Assuming HIDConnectionManager is the concrete class that will do the work.
        # It might be refactored later as per plan step 4.
        self._hid_connection_manager = HIDConnectionManager()

    def find_potential_hid_devices(self) -> list[dict[str, Any]]:
        return self._hid_connection_manager._find_potential_hid_devices()

    def sort_hid_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._hid_connection_manager._sort_hid_devices(devices)

    def connect_device(self) -> Tuple[Optional[HidDevice], Optional[dict[str, Any]]]:
        # HIDConnectionManager._connect_device returns a bool.
        # We need to adapt it or call a method that returns the device and info.
        # For now, let's assume a refactor or direct access.
        # This part will need alignment with Step 4 (Refactor HIDConnectionManager)
        if self._hid_connection_manager._connect_device():
            return self._hid_connection_manager.hid_device, self._hid_connection_manager.selected_device_info
        return None, None

    def ensure_connection(self) -> bool:
        return self._hid_connection_manager.ensure_connection()

    def get_hid_device(self) -> Optional[HidDevice]:
        return self._hid_connection_manager.get_hid_device()

    def get_selected_device_info(self) -> Optional[dict[str, Any]]:
        return self._hid_connection_manager.get_selected_device_info()

    def close(self) -> None:
        self._hid_connection_manager.close()


class LinuxImpl(OSInterface):
    """Linux-specific implementation of OSInterface."""

    def __init__(self):
        self._udev_manager = UDEVManager()
        self._hid_manager = LinuxHIDManager() # Or directly HIDConnectionManager if it fits the interface

    def get_config_dir(self) -> Path:
        config_home = os.getenv("XDG_CONFIG_HOME")
        if config_home:
            return Path(config_home) / app_config.APP_NAME.lower().replace(" ", "_")
        return Path.home() / ".config" / app_config.APP_NAME.lower().replace(" ", "_")

    def get_data_dir(self) -> Path:
        data_home = os.getenv("XDG_DATA_HOME")
        if data_home:
            return Path(data_home) / app_config.APP_NAME.lower().replace(" ", "_")
        return Path.home() / ".local" / "share" / app_config.APP_NAME.lower().replace(" ", "_")

    def get_os_name(self) -> str:
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
        # logger.warning("needs_device_setup: Current implementation is a placeholder. Relies on UDEVManager being refactored for an accurate check.")
        # Use the new method in UDEVManager
        return not self._udev_manager.are_rules_installed()


    def _execute_udev_helper_script(self, temp_file_path: str, final_file_path: str) -> subprocess.CompletedProcess:
        """
        Executes the udev helper script using pkexec. (Copied from app.py)
        """
        # Determine path to script relative to this file or a known location
        # Assuming this file is at src/headsetcontrol_tray/os_layer/linux.py
        current_script_dir = Path(__file__).parent
        # os_layer is inside headsetcontrol_tray, scripts is at repo root.
        # So, ../../scripts
        scripts_dir = (current_script_dir / ".." / ".." / "scripts").resolve()
        helper_script_path = scripts_dir / "install-udev-rules.sh"

        if not helper_script_path.is_file(): # Use is_file for better check
            logger.error("Helper script not found at %s", str(helper_script_path))
            # This exception type might need to be defined in a common place or use a generic one
            raise TrayAppInitializationError(f"Helper script not found at {helper_script_path}")

        cmd = ["pkexec", str(helper_script_path), temp_file_path, final_file_path]
        logger.info("Attempting to execute with pkexec: %s", " ".join(cmd))
        try:
            # Note: S603 will flag this if not careful. Ensure helper_script_path is trusted.
            # Since it's bundled with the app, it's considered trusted.
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False, # We check returncode manually
            )
        except FileNotFoundError:  # pkexec itself not found
            logger.exception("pkexec command not found. Ensure PolicyKit is installed.")
            raise TrayAppInitializationError("pkexec command not found.")
        except subprocess.SubprocessError as e:
            logger.exception("Subprocess error during pkexec execution: %s", e)
            raise TrayAppInitializationError(f"Subprocess error: {e}")


    def perform_device_setup(self, ui_parent: Any = None) -> Tuple[bool, Optional[subprocess.CompletedProcess], Optional[Exception]]:
        """
        Guides the user through installing udev rules for Linux.
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
                    logger.error("PySide6 not available for showing error dialog in perform_device_setup.")
            # Return structure: success, process_result, error
            return False, None, TrayAppInitializationError("Failed to prepare udev rule details.")

        udev_details = self._udev_manager.get_last_udev_setup_details()
        if not udev_details: # Should not happen if prepare_udev_rule_details succeeded
            logger.error("UDEVManager prepared rules but details are missing.")
            return False, None, TrayAppInitializationError("UDEVManager details missing after preparation.")

        temp_file = udev_details["temp_file_path"]
        final_file = udev_details["final_file_path"]

        logger.info(f"Executing udev helper script. Temp: {temp_file}, Final: {final_file}")

        execution_error: Optional[Exception] = None
        process_result: Optional[subprocess.CompletedProcess] = None
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
                logger.warning(f"pkexec helper script failed with code {process_result.returncode}.")
                # The error is implicitly in process_result, no separate exception here unless pkexec itself failed to run.

        except TrayAppInitializationError as e: # Errors from _execute_udev_helper_script itself
            logger.error(f"Device setup failed before or during pkexec execution: {e}")
            execution_error = e
        except Exception as e: # Catch any other unexpected error
            logger.exception(f"An unexpected error occurred during perform_device_setup: {e}")
            execution_error = e # General exception

        return success, process_result, execution_error


    def get_hid_manager(self) -> HIDManagerInterface:
        return self._hid_manager
