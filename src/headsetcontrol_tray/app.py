"""Core application logic for the HeadsetControl Tray."""

import logging
import os
import subprocess  # Added for pkexec
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import app_config
from . import config_manager as cfg_mgr
from . import headset_service as hs_svc
from .ui import system_tray_icon as sti

# Initialize logging
log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

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
        # Use existing QApplication instance if available (e.g., from pytest-qt),
        # else create a new one.
        _q_instance = QApplication.instance()
        if _q_instance:
            create_new_qapp = False
            # Check if the imported QApplication is a real type (not a mock)
            if isinstance(QApplication, type):
                # QApplication is a real type, so _q_instance is a real Qt object.
                # We need to ensure it's a full QApplication, not just QCoreApplication.
                if not isinstance(_q_instance, QApplication):
                    # This means _q_instance might be QCoreApplication or some other non-QApplication type.
                    logger.warning(
                        "Existing Qt instance found (type: %s), but it's not a QApplication. Creating new QApplication for GUI.",
                        _q_instance.__class__.__name__,
                    )
                    create_new_qapp = True
                # If it is already a QApplication, we use it (create_new_qapp remains False).
            else:
                # QApplication is mocked (e.g., in a test environment).
                # We assume _q_instance (likely from a mocked QApplication.instance())
                # is the mock object the test environment wants to use.
                # The original check's purpose (differentiating QCoreApplication from QApplication)
                # is less relevant here, or should be handled by the mock's configuration.
                # So, we don't force creating a new QApplication([]), which might interfere with the mock.
                pass  # create_new_qapp remains False, and we'll use _q_instance.

            if create_new_qapp:
                self.qt_app = QApplication([])
            else:
                self.qt_app = _q_instance  # type: ignore [assignment]
        else:  # No pre-existing instance
            self.qt_app = QApplication([])

        self.qt_app.setQuitOnLastWindowClosed(False)  # Important for tray apps

        # Set application name for potential QSettings usage or window titles
        self.qt_app.setApplicationName(app_config.APP_NAME)

        # Attempt to set a generic application icon for dialogs etc.
        app_icon = QIcon.fromTheme(
            "audio-headset",
            QIcon.fromTheme("preferences-desktop-multimedia"),
        )
        if not app_icon.isNull():
            self.qt_app.setWindowIcon(app_icon)

        self.config_manager = cfg_mgr.ConfigManager()
        self.headset_service = hs_svc.HeadsetService()

        # Check if udev rule setup instructions were generated
        if self.headset_service.udev_setup_details:
            self._handle_udev_permissions_flow(self.headset_service.udev_setup_details)

        if not self.headset_service.is_device_connected():
            logger.warning("Headset not detected on startup by HeadsetService.")
            # QSystemTrayIcon.supportsMessages() can check if backend supports this.
            # For now, tooltip will indicate disconnected state.

        self.tray_icon = sti.SystemTrayIcon(
            self.headset_service,
            self.config_manager,
            self.quit_application,
        )
        self.tray_icon.show()

        # Apply persisted settings on startup
        self.tray_icon.set_initial_headset_settings()

    def _handle_udev_permissions_flow(self, udev_details: dict) -> None:
        """Handles the dialog flow for udev permissions and pkexec."""
        temp_file = udev_details["temp_file_path"]
        final_file = udev_details["final_file_path"]

        dialog = QMessageBox()
        dialog.setWindowTitle("Headset Permissions Setup Required")
        dialog.setIcon(QMessageBox.Icon.Information)  # Or QMessageBox.Warning
        dialog.setText(
            "Could not connect to your SteelSeries headset. This may be due to missing udev permissions (udev rules).",
        )

        informative_text_string = f"""A rule file has been prepared at: {temp_file}

To resolve this, you can use the 'Install Automatically' button, or follow these manual steps in a terminal:
1. Copy the rule file:
   sudo cp "{temp_file}" "{final_file}"
2. Reload udev rules:
   sudo udevadm control --reload-rules && sudo udevadm trigger
3. Replug your headset.

Without these rules, the application might not be able to detect or control your headset.
"""
        dialog.setInformativeText(informative_text_string.strip())

        auto_button = dialog.addButton(
            "Install Automatically",
            QMessageBox.ButtonRole.AcceptRole,
        )
        _ = dialog.addButton(QMessageBox.StandardButton.Close)  # Standard close button

        dialog.setDefaultButton(auto_button)
        dialog.exec()

        clicked_button_role = dialog.clickedButton()
        if clicked_button_role == auto_button:
            logger.info("User chose to install udev rules automatically.")
            temp_file_path = udev_details[
                "temp_file_path"
            ]  # Use udev_details consistently
            final_file_path = udev_details[
                "final_file_path"
            ]  # Use udev_details consistently

            current_script_dir = os.path.dirname(__file__)
            repo_root = os.path.abspath(os.path.join(current_script_dir, ".."))
            helper_script_path = os.path.join(
                repo_root,
                "scripts",
                "install-udev-rules.sh",
            )

            if not os.path.exists(helper_script_path):
                logger.error("Helper script not found at %s", helper_script_path)
                QMessageBox.critical(
                    dialog,
                    "Error",
                    f"Installation script not found at:\n{helper_script_path}\n\nPlease report this issue.",
                )
            else:
                cmd = ["pkexec", helper_script_path, temp_file_path, final_file_path]
                logger.info("Attempting to execute: %s", " ".join(cmd))
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    logger.info(
                        "pkexec process completed. Return code: %s",
                        result.returncode,
                    )
                    if result.stdout:
                        logger.info("pkexec stdout:\n%s", result.stdout.strip())
                    if result.stderr:
                        logger.warning("pkexec stderr:\n%s", result.stderr.strip())

                    if result.returncode == 0:
                        logger.info("pkexec script executed successfully.")
                        feedback_dialog = QMessageBox()
                        feedback_dialog.setIcon(QMessageBox.Icon.Information)
                        feedback_dialog.setWindowTitle("Success")
                        feedback_dialog.setText("Udev rules installed successfully.")
                        feedback_dialog.setInformativeText(
                            "Please replug your headset for the changes to take effect.",
                        )
                        feedback_dialog.exec()
                    elif result.returncode == 126:
                        logger.warning("User cancelled pkexec authentication.")
                        feedback_dialog = QMessageBox()
                        feedback_dialog.setIcon(QMessageBox.Icon.Warning)
                        feedback_dialog.setWindowTitle("Authentication Cancelled")
                        feedback_dialog.setText("Udev rule installation was cancelled.")
                        feedback_dialog.setInformativeText(
                            "Authentication was not provided. The udev rules have not been installed. You can try again or use the manual instructions.",
                        )
                        feedback_dialog.exec()
                    elif result.returncode == 127:
                        logger.error(
                            "pkexec authorization failed or error. stderr: %s",
                            result.stderr.strip(),
                        )
                        feedback_dialog = QMessageBox()
                        feedback_dialog.setIcon(QMessageBox.Icon.Critical)
                        feedback_dialog.setWindowTitle("Authorization Error")
                        feedback_dialog.setText(
                            "Failed to install udev rules due to an authorization error.",
                        )
                        feedback_dialog.setInformativeText(
                            f"Details: {result.stderr.strip()}\n\nPlease ensure you have privileges or contact support. You can also try the manual instructions.",
                        )
                        feedback_dialog.exec()
                    else:
                        logger.error(
                            "pkexec helper script failed with code %s. stderr: %s",
                            result.returncode,
                            result.stderr.strip(),
                        )
                        feedback_dialog = QMessageBox()
                        feedback_dialog.setIcon(QMessageBox.Icon.Critical)
                        feedback_dialog.setWindowTitle("Installation Failed")
                        feedback_dialog.setText(
                            "The udev rule installation script failed.",
                        )
                        feedback_dialog.setInformativeText(
                            f"Error (code {result.returncode}): {result.stderr.strip()}\n\nPlease check the output and try the manual instructions, or contact support.",
                        )
                        feedback_dialog.exec()
                except FileNotFoundError:
                    logger.error(
                        "pkexec command not found. Please ensure PolicyKit agent and pkexec are installed.",
                    )
                    QMessageBox.critical(
                        dialog,
                        "Error",
                        "pkexec command not found.\nPlease ensure PolicyKit is correctly installed and configured.",
                    )
                except Exception as e:
                    logger.error(
                        "An unexpected error occurred during pkexec execution: %s",
                        e,
                    )
                    QMessageBox.critical(
                        dialog,
                        "Error",
                        f"An unexpected error occurred while trying to run the helper script:\n{e}",
                    )
        else:
            logger.info(
                "User closed or cancelled the udev rules dialog, or did not choose automatic install.",
            )

    def run(self) -> int:
        """Starts the Qt application event loop."""
        return self.qt_app.exec()

    def quit_application(self) -> None:
        """Closes headset resources and quits the Qt application."""
        logger.info("Application quitting.")
        self.headset_service.close()  # Clean up HID connection
        self.qt_app.quit()
