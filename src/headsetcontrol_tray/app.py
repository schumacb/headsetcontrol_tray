"""Core application logic for the HeadsetControl Tray."""

import logging
import os  # Keep for os.environ
from pathlib import Path  # Added
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

# pkexec exit codes
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
                    # This means _q_instance might be QCoreApplication
                    # or some other non-QApplication type.
                    logger.warning(
                        (
                            "Existing Qt instance found (type: %s), but it's not a "
                            "QApplication. Creating new QApplication for GUI."
                        ),
                        _q_instance.__class__.__name__,
                    )
                    create_new_qapp = True
                # If it is already a QApplication, we use it (create_new_qapp remains False).
            else:
                # QApplication is mocked (e.g., in a test environment).
                # We assume _q_instance (likely from a mocked
                # QApplication.instance()) is the mock object the test environment
                # wants to use. The original check's purpose (differentiating
                # QCoreApplication from QApplication) is less relevant here, or
                # should be handled by the mock's configuration. So, we don't
                # force creating a new QApplication([]), which might interfere
                # with the mock.
                pass  # Use existing mock instance. create_new_qapp remains False.

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

    def _execute_udev_helper_script(
        self,
        temp_file_path: str,
        final_file_path: str,
    ) -> subprocess.CompletedProcess:
        """
        Executes the udev helper script using pkexec.

        Args:
            temp_file_path: Path to the temporary udev rule file.
            final_file_path: The final destination path for the udev rule file.

        Returns:
            The CompletedProcess object from subprocess.run.

        Raises:
            FileNotFoundError: If the helper script or pkexec is not found.
            subprocess.SubprocessError: For other subprocess execution issues.
        """
        current_script_dir = Path(__file__).parent
        repo_root = (current_script_dir / "..").resolve()
        helper_script_path = repo_root / "scripts" / "install-udev-rules.sh"

        if not helper_script_path.exists():
            logger.error("Helper script not found at %s", str(helper_script_path))
            raise FileNotFoundError("Helper script missing.")

        # Ensure all parts of cmd are strings for subprocess.run
        cmd = ["pkexec", str(helper_script_path), temp_file_path, final_file_path]
        logger.info("Attempting to execute: %s", " ".join(cmd))
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # We check returncode manually
            )  # nosec B603 # nosemgrep S603 # helper_script_path is internally defined,
        # temp_file_path and final_file_path are file paths, not direct commands.
        except FileNotFoundError:  # pkexec itself not found
            logger.exception("pkexec command not found.")
            raise  # Re-raise to be caught by the caller
        except subprocess.SubprocessError:  # Catch other potential subprocess errors
            logger.exception("Subprocess error during pkexec execution:")
            raise  # Re-raise

    def _show_udev_feedback_dialog(
        self,
        parent_dialog: QMessageBox,
        result: subprocess.CompletedProcess | None,
        error: Exception | None = None,
    ) -> None:
        """Displays a feedback dialog based on the outcome of the udev helper script
        execution.

        """
        feedback_dialog = QMessageBox(parent_dialog)
        feedback_dialog.setModal(True)  # Ensure modality

        if error:
            self._handle_udev_initial_error_feedback(feedback_dialog, error)
            return

        if result is None:
            logger.error(
                "No result from pkexec and no explicit error. This is unexpected.",
            )
            feedback_dialog.setIcon(QMessageBox.Icon.Critical)
            feedback_dialog.setWindowTitle("Error")
            feedback_dialog.setText(
                "An unknown error occurred during the installation process.",
            )
            feedback_dialog.exec()
            return

        logger.info("pkexec process completed. Return code: %s", result.returncode)
        if result.stdout:
            logger.info("pkexec stdout:\n%s", result.stdout.strip())
        if result.stderr:
            logger.warning("pkexec stderr:\n%s", result.stderr.strip())

        if result.returncode == PKEXEC_EXIT_SUCCESS:
            self._handle_udev_success_feedback(feedback_dialog)
        elif result.returncode in (PKEXEC_EXIT_USER_CANCELLED, PKEXEC_EXIT_AUTH_FAILED):
            self._handle_udev_pkexec_error_feedback(feedback_dialog, result)
        else:
            self._handle_udev_other_error_feedback(feedback_dialog, result)
        feedback_dialog.exec()

    def _handle_udev_initial_error_feedback(
        self,
        dialog: QMessageBox,
        error: Exception,
    ) -> None:
        """Handles feedback for initial errors before pkexec result processing."""
        logger.exception("Error during udev script execution phase:")
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("Error")
        if isinstance(error, FileNotFoundError):
            if "Helper script missing" in str(error):  # Check updated message
                dialog.setText(
                    "Installation script not found.\nPlease report this issue.",
                )
            else:  # pkexec not found
                dialog.setText(
                    "pkexec command not found.\nPlease ensure PolicyKit is correctly installed and configured.",
                )
        else:  # General subprocess error or other unexpected error
            dialog.setText(
                f"An unexpected error occurred while trying to run the helper script:\n{error}",
            )
        dialog.exec()

    def _handle_udev_success_feedback(self, dialog: QMessageBox) -> None:
        """Handles feedback for successful udev rule installation."""
        logger.info("pkexec script executed successfully.")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle("Success")
        dialog.setText("Udev rules installed successfully.")
        dialog.setInformativeText(
            "Please replug your headset for the changes to take effect.",
        )

    def _handle_udev_pkexec_error_feedback(
        self,
        dialog: QMessageBox,
        result: subprocess.CompletedProcess,
    ) -> None:
        """Handles feedback for pkexec specific errors (cancel, auth fail)."""
        if result.returncode == PKEXEC_EXIT_USER_CANCELLED:
            logger.warning("User cancelled pkexec authentication.")
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setWindowTitle("Authentication Cancelled")
            dialog.setText("Udev rule installation was cancelled.")
            dialog.setInformativeText(
                "Authentication was not provided. The udev rules have not been "
                "installed. You can try again or use the manual instructions.",
            )
        elif result.returncode == PKEXEC_EXIT_AUTH_FAILED:
            logger.error(
                "pkexec authorization failed or error. stderr: %s",
                result.stderr.strip(),
            )
            dialog.setIcon(QMessageBox.Icon.Critical)
            dialog.setWindowTitle("Authorization Error")
            dialog.setText(
                "Failed to install udev rules due to an authorization error.",
            )
            dialog.setInformativeText(
                f"Details: {result.stderr.strip()}\n\nPlease ensure you have "
                "privileges or contact support. You can also try the manual "
                "instructions.",
            )

    def _handle_udev_other_error_feedback(
        self,
        dialog: QMessageBox,
        result: subprocess.CompletedProcess,
    ) -> None:
        """Handles feedback for other udev helper script errors."""
        logger.error(
            "pkexec helper script failed with code %s. stderr: %s",
            result.returncode,
            result.stderr.strip(),
        )
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("Installation Failed")
        dialog.setText("The udev rule installation script failed.")
        dialog.setInformativeText(
            f"Error (code {result.returncode}): {result.stderr.strip()}\n\n"
            "Please check the output and try the manual instructions, or contact "
            "support.",
        )

    def _handle_udev_permissions_flow(self, udev_details: dict) -> None:
        """Handles the dialog flow for udev permissions and pkexec."""
        temp_file = udev_details["temp_file_path"]
        final_file = udev_details["final_file_path"]

        dialog = QMessageBox()
        dialog.setWindowTitle("Headset Permissions Setup Required")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(
            "Could not connect to your SteelSeries headset. This may be due to missing udev permissions (udev rules).",
        )

        informative_text_string = (
            f"A rule file has been prepared at: {temp_file}\n\n"
            "To resolve this, you can use the 'Install Automatically' button, or "
            "follow these manual steps in a terminal:\n"
            f'1. Copy the rule file:\n   sudo cp "{temp_file}" "{final_file}"\n'
            "2. Reload udev rules:\n"
            "   sudo udevadm control --reload-rules && sudo udevadm trigger\n"
            "3. Replug your headset.\n\n"
            "Without these rules, the application might not be able to detect or "
            "control your headset."
        )
        dialog.setInformativeText(informative_text_string)

        auto_button = dialog.addButton(
            "Install Automatically",
            QMessageBox.ButtonRole.AcceptRole,
        )
        _ = dialog.addButton(QMessageBox.StandardButton.Close)
        dialog.setDefaultButton(auto_button)
        dialog.exec()

        if dialog.clickedButton() == auto_button:
            logger.info("User chose to install udev rules automatically.")
            process_result: subprocess.CompletedProcess | None = None
            execution_error: Exception | None = None
            try:
                process_result = self._execute_udev_helper_script(temp_file, final_file)
            except FileNotFoundError as e:  # Helper script or pkexec not found
                execution_error = e
            except subprocess.SubprocessError as e:  # Other subprocess errors
                execution_error = e
            except OSError as e:  # More specific exception for OS related errors
                logger.exception(
                    "OS error during _execute_udev_helper_script: %s",
                    e,
                )
                execution_error = e

            self._show_udev_feedback_dialog(dialog, process_result, execution_error)
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
