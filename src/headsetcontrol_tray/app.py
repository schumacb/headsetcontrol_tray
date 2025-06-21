"""Core application logic for the HeadsetControl Tray."""

import logging
import os  # Keep for os.environ
import platform  # To detect OS
import subprocess  # For type hint in _show_udev_feedback_dialog
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import app_config
from . import config_manager as cfg_mgr
from . import headset_service as hs_svc
from .exceptions import TrayAppInitializationError  # Keep for error handling
from .os_layer.base import OSInterface
from .os_layer.linux import LinuxImpl  # Needed for isinstance check and specific logic
from .os_layer.macos import MacOSImpl
from .os_layer.windows import WindowsImpl
from .ui import system_tray_icon as sti

# Initialize logging
log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# pkexec exit codes (still needed for interpreting results from LinuxImpl)
PKEXEC_EXIT_SUCCESS = 0
PKEXEC_EXIT_USER_CANCELLED = 126
PKEXEC_EXIT_AUTH_FAILED = 127

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
)
logger = logging.getLogger(app_config.APP_NAME)


class SteelSeriesTrayApp:
    """Main application class for the SteelSeries Headset Tray Utility."""

    qt_app: QApplication  # Class level type annotation

    def __init__(self) -> None:
        """Initializes the SteelSeriesTrayApp."""
        logger.info(
            "Application starting with log level %s",
            logging.getLevelName(logger.getEffectiveLevel()),
        )
        _q_instance = QApplication.instance()
        if _q_instance:
            create_new_qapp = False
            if isinstance(QApplication, type):
                if not isinstance(_q_instance, QApplication):
                    logger.warning(
                        (
                            "Existing Qt instance found (type: %s), but it's not a "
                            "QApplication. Creating new QApplication for GUI."
                        ),
                        _q_instance.__class__.__name__,
                    )
                    create_new_qapp = True
            else:
                pass

            if create_new_qapp:
                self.qt_app = QApplication([])
            else:
                self.qt_app = _q_instance  # type: ignore [assignment]
        else:
            self.qt_app = QApplication([])

        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setApplicationName(app_config.APP_NAME)

        app_icon = QIcon.fromTheme(
            "audio-headset",
            QIcon.fromTheme("preferences-desktop-multimedia"),
        )
        if not app_icon.isNull():
            self.qt_app.setWindowIcon(app_icon)

        self.os_interface = self._get_os_interface()
        logger.info("Initialized OS interface for: %s", self.os_interface.get_os_name())

        config_dir = self.os_interface.get_config_dir()
        logger.info("Using configuration directory: %s", config_dir)
        self.config_manager = cfg_mgr.ConfigManager(config_dir_path=config_dir)

        hid_manager_instance = self.os_interface.get_hid_manager()
        self.headset_service = hs_svc.HeadsetService(hid_manager=hid_manager_instance)

        if not self.headset_service.is_device_connected():
            logger.warning("Headset not detected on initial check by HeadsetService.")
            if self.os_interface.needs_device_setup():
                logger.info("OS interface reports that device setup is needed for %s.", self.os_interface.get_os_name())
                self._perform_os_specific_setup_flow()  # Call the new flow
            else:
                logger.info(
                    "OS interface reports no specific device setup is needed for %s or it's already done.",
                    self.os_interface.get_os_name(),
                )

        if not self.headset_service.is_device_connected():
            logger.warning("Headset still not detected after initial checks and potential setup prompts.")

        self.tray_icon = sti.SystemTrayIcon(
            self.headset_service,
            self.config_manager,
            self.quit_application,
        )
        # Pass self.tray_icon as a QWidget parent for dialogs if needed by tray_icon methods
        # For example, if tray_icon itself needs to show dialogs directly.
        self.tray_icon.show()
        self.tray_icon.set_initial_headset_settings()

    def _get_os_interface(self) -> OSInterface:
        os_name_lower = platform.system().lower()
        if os_name_lower == "linux":
            logger.info("Detected Linux OS.")
            return LinuxImpl()
        if os_name_lower == "windows":
            logger.info("Detected Windows OS.")
            return WindowsImpl()
        if os_name_lower == "darwin":  # macOS
            logger.info("Detected macOS.")
            return MacOSImpl()
        logger.warning("Unsupported OS '%s'. Falling back to Linux implementation as a default.", platform.system())
        return LinuxImpl()

    def _show_udev_feedback_dialog(  # noqa: C901, PLR0912, PLR0915
        self,
        *,
        success: bool,
        proc_result: subprocess.CompletedProcess | None,
        exec_error: Exception | None,
    ) -> None:
        """Shows feedback dialog after attempting udev rules setup."""
        feedback_dialog = QMessageBox(None)
        feedback_dialog.setModal(True)

        if exec_error:
            logger.exception("Error during udev script execution phase: %s", exec_error)
            feedback_dialog.setIcon(QMessageBox.Icon.Critical)
            feedback_dialog.setWindowTitle("Setup Error")
            if isinstance(exec_error, TrayAppInitializationError):
                if "Helper script not found" in str(exec_error):
                    feedback_dialog.setText("Installation script not found. Please report this issue.")
                elif "pkexec command not found" in str(exec_error):
                    feedback_dialog.setText(
                        "pkexec command not found. Please ensure PolicyKit is correctly installed.",
                    )
                else:
                    feedback_dialog.setText(f"A setup error occurred: {exec_error}")
            else:
                feedback_dialog.setText(f"An unexpected error occurred: {exec_error}")
        elif proc_result is None and not success:
            logger.error("No process result from setup and no explicit error. This is unexpected.")
            feedback_dialog.setIcon(QMessageBox.Icon.Critical)
            feedback_dialog.setWindowTitle("Unknown Error")
            feedback_dialog.setText("An unknown error occurred during the installation process.")
        elif proc_result:
            logger.info("pkexec process completed. Return code: %s", proc_result.returncode)
            if proc_result.stdout:
                logger.info("pkexec stdout:\n%s", proc_result.stdout.strip())
            if proc_result.stderr:
                logger.warning("pkexec stderr:\n%s", proc_result.stderr.strip())

            if success:
                feedback_dialog.setIcon(QMessageBox.Icon.Information)
                feedback_dialog.setWindowTitle("Success")
                feedback_dialog.setText("Udev rules installed successfully.")
                feedback_dialog.setInformativeText(
                    "Please replug your headset for the changes to take effect, then restart the application.",
                )
            elif proc_result.returncode == PKEXEC_EXIT_USER_CANCELLED:
                feedback_dialog.setIcon(QMessageBox.Icon.Warning)
                feedback_dialog.setWindowTitle("Authentication Cancelled")
                feedback_dialog.setText("Udev rule installation was cancelled by user.")
            elif proc_result.returncode == PKEXEC_EXIT_AUTH_FAILED:
                feedback_dialog.setIcon(QMessageBox.Icon.Critical)
                feedback_dialog.setWindowTitle("Authorization Error")
                feedback_dialog.setText("Failed to install udev rules due to an authorization error.")
                feedback_dialog.setInformativeText(f"Details: {proc_result.stderr.strip()}")
            else:
                feedback_dialog.setIcon(QMessageBox.Icon.Critical)
                feedback_dialog.setWindowTitle("Installation Failed")
                feedback_dialog.setText("The udev rule installation script failed.")
                feedback_dialog.setInformativeText(
                    f"Error (code {proc_result.returncode}): {proc_result.stderr.strip()}",
                )
        else:
            feedback_dialog.setIcon(QMessageBox.Icon.Warning)
            feedback_dialog.setWindowTitle("Setup Incomplete")
            feedback_dialog.setText("Device setup process finished with an undetermined state.")

        feedback_dialog.exec()

    def _perform_os_specific_setup_flow(self) -> None:
        """Handles the UI flow for OS-specific device setup if indicated by the OSInterface.

        This may involve showing dialogs and triggering the setup process via OSInterface.
        """
        os_name = self.os_interface.get_os_name()
        logger.info("Starting OS-specific setup flow for %s.", os_name)

        if os_name == "linux":
            dialog = QMessageBox(None)
            dialog.setWindowTitle("Headset Permissions Setup (Linux)")
            dialog.setIcon(QMessageBox.Icon.Information)
            dialog.setText(
                "Your SteelSeries headset might need additional permissions (udev rules) to be fully functional.",
            )
            dialog.setInformativeText(
                "Do you want to attempt to install these rules automatically?\n"
                "This will require administrator privileges (via pkexec).",
            )
            auto_button = dialog.addButton("Install Automatically", QMessageBox.ButtonRole.AcceptRole)
            manual_button = dialog.addButton("Show Manual Instructions", QMessageBox.ButtonRole.ActionRole)
            dialog.addButton(QMessageBox.StandardButton.Close)
            dialog.setDefaultButton(auto_button)
            dialog.exec()

            if dialog.clickedButton() == auto_button:
                logger.info("User chose to install udev rules automatically via OSInterface.")
                success, proc_result, exec_error = self.os_interface.perform_device_setup(ui_parent=self.tray_icon)
                self._show_udev_feedback_dialog(success=success, proc_result=proc_result, exec_error=exec_error)

            elif dialog.clickedButton() == manual_button:
                manual_instructions_dialog = QMessageBox(None)
                manual_instructions_dialog.setWindowTitle("Manual Udev Setup Instructions")
                manual_instructions_dialog.setIcon(QMessageBox.Icon.Information)
                manual_instructions_dialog.setText(
                    "The udev rules and manual installation steps have been logged to the console/terminal "
                    "from which this application was started.",
                )
                manual_instructions_dialog.setInformativeText(
                    "Please check the console output for details on how to copy the rule file "
                    "and reload udev. You might need to restart the application after completing these steps.",
                )
                manual_instructions_dialog.exec()

                if (
                    isinstance(self.os_interface, LinuxImpl)
                    and not self.os_interface._udev_manager.get_last_udev_setup_details()  # noqa: SLF001 # Accessing internal state for conditional logic
                ):
                    # TODO: Refactor LinuxImpl to have a method like ensure_udev_details_prepared()
                    # to avoid direct _udev_manager access from app.py. This SLF001 is acknowledged pending that.
                    self.os_interface._udev_manager.create_rules_interactive()  # noqa: SLF001
            else:
                logger.info("User closed or cancelled the udev rules setup dialog.")

        elif os_name in ["windows", "macos"]:
            self.os_interface.perform_device_setup(ui_parent=self.tray_icon)
        else:
            logger.info("No specific setup flow implemented for OS: %s", os_name)

    def run(self) -> int:
        """Starts the Qt application event loop."""
        return self.qt_app.exec()

    def quit_application(self) -> None:
        """Closes headset resources and quits the Qt application."""
        logger.info("Application quitting.")
        self.headset_service.close()
        self.qt_app.quit()
