import sys
import logging
import os
import subprocess # Added for pkexec
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from . import config_manager as cfg_mgr
from . import headset_service as hs_svc
from .ui import system_tray_icon as sti
from . import app_config

# Initialize logging
log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)] # Output to console
)
logger = logging.getLogger(app_config.APP_NAME)


class SteelSeriesTrayApp:
    """Main application class for the SteelSeries Headset Tray Utility."""

    def __init__(self):
        logger.info(f"Application starting with log level {logging.getLevelName(logger.getEffectiveLevel())}")
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False) # Important for tray apps

        # Set application name for potential QSettings usage or window titles
        self.qt_app.setApplicationName(app_config.APP_NAME)
        # self.qt_app.setOrganizationName(app_config.ORGANIZATION_NAME) # Optional

        # Attempt to set a generic application icon for dialogs etc.
        app_icon = QIcon.fromTheme("audio-headset", QIcon.fromTheme("preferences-desktop-multimedia"))
        if not app_icon.isNull():
            self.qt_app.setWindowIcon(app_icon)
        
        self.config_manager = cfg_mgr.ConfigManager()
        self.headset_service = hs_svc.HeadsetService()

        # Check if udev rule setup instructions were generated
        if self.headset_service.udev_setup_details:
            details = self.headset_service.udev_setup_details
            details = self.headset_service.udev_setup_details
            temp_file = details["temp_file_path"]
            final_file = details["final_file_path"]
            # rule_filename = details["rule_filename"] # Available if needed

            dialog = QMessageBox()
            dialog.setWindowTitle("Headset Permissions Setup Required")
            dialog.setIcon(QMessageBox.Information) # Or QMessageBox.Warning
            dialog.setText("Your SteelSeries headset may not work correctly without the proper udev rules.")

            informative_text_string = f"""A rule file has been prepared at: {temp_file}

You can install these rules automatically, or follow these manual steps in a terminal:
1. Copy the rule file:
   sudo cp "{temp_file}" "{final_file}"
2. Reload udev rules:
   sudo udevadm control --reload-rules && sudo udevadm trigger
3. Replug your headset.

Without these rules, the application might not be able to detect or control your headset.
"""
            dialog.setInformativeText(informative_text_string.strip())

            auto_button = dialog.addButton("Install Automatically", QMessageBox.AcceptRole)
            manual_button = dialog.addButton("Show Manual Instructions Only", QMessageBox.ActionRole)
            _ = dialog.addButton(QMessageBox.Close) # Standard close button, result not needed for this one

            dialog.setDefaultButton(auto_button)
            dialog.exec()

            clicked_button_role = dialog.clickedButton()
            if clicked_button_role == auto_button:
                logger.info("User chose to install udev rules automatically.")
                temp_file_path = details["temp_file_path"]
                final_file_path = details["final_file_path"]

                # Determine path to the helper script
                # __file__ is headsetcontrol_tray/app.py
                # We want scripts/install-udev-rules.sh from the repo root
                current_script_dir = os.path.dirname(__file__)
                repo_root = os.path.abspath(os.path.join(current_script_dir, ".."))
                helper_script_path = os.path.join(repo_root, "scripts", "install-udev-rules.sh")

                if not os.path.exists(helper_script_path):
                    logger.error(f"Helper script not found at {helper_script_path}")
                    # Fallback: show error to user, perhaps another QMessageBox
                    QMessageBox.critical(None, "Error", f"Installation script not found at:\n{helper_script_path}\n\nPlease report this issue.")
                else:
                    cmd = ["pkexec", helper_script_path, temp_file_path, final_file_path]
                    logger.info(f"Attempting to execute: {' '.join(cmd)}")
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, check=False) # check=False to inspect manually
                        logger.info(f"pkexec process completed. Return code: {result.returncode}")
                        if result.stdout:
                            logger.info(f"pkexec stdout:\n{result.stdout.strip()}")
                        if result.stderr:
                            # Stderr from pkexec itself might indicate auth failure,
                            # or stderr from the script if it failed.
                            logger.warning(f"pkexec stderr:\n{result.stderr.strip()}")

                        if result.returncode == 0:
                            logger.info("pkexec script executed successfully.")
                            feedback_dialog = QMessageBox()
                            feedback_dialog.setIcon(QMessageBox.Information)
                            feedback_dialog.setWindowTitle("Success")
                            feedback_dialog.setText("Udev rules installed successfully.")
                            feedback_dialog.setInformativeText("Please replug your headset for the changes to take effect.")
                            feedback_dialog.exec()
                        elif result.returncode == 126: # User cancelled pkexec authentication
                            logger.warning("User cancelled pkexec authentication.")
                            feedback_dialog = QMessageBox()
                            feedback_dialog.setIcon(QMessageBox.Warning)
                            feedback_dialog.setWindowTitle("Authentication Cancelled")
                            feedback_dialog.setText("Udev rule installation was cancelled.")
                            feedback_dialog.setInformativeText("Authentication was not provided. The udev rules have not been installed. You can try again or use the manual instructions.")
                            feedback_dialog.exec()
                        elif result.returncode == 127: # pkexec authorization failure
                            logger.error(f"pkexec authorization failed or error. stderr: {result.stderr.strip()}")
                            feedback_dialog = QMessageBox()
                            feedback_dialog.setIcon(QMessageBox.Critical)
                            feedback_dialog.setWindowTitle("Authorization Error")
                            feedback_dialog.setText("Failed to install udev rules due to an authorization error.")
                            feedback_dialog.setInformativeText(f"Details: {result.stderr.strip()}\n\nPlease ensure you have privileges or contact support. You can also try the manual instructions.")
                            feedback_dialog.exec()
                        else: # Other non-zero return codes from the helper script
                            logger.error(f"pkexec helper script failed with code {result.returncode}. stderr: {result.stderr.strip()}")
                            feedback_dialog = QMessageBox()
                            feedback_dialog.setIcon(QMessageBox.Critical)
                            feedback_dialog.setWindowTitle("Installation Failed")
                            feedback_dialog.setText("The udev rule installation script failed.")
                            feedback_dialog.setInformativeText(f"Error (code {result.returncode}): {result.stderr.strip()}\n\nPlease check the output and try the manual instructions, or contact support.")
                            feedback_dialog.exec()

                    except FileNotFoundError:
                        logger.error("pkexec command not found. Please ensure PolicyKit agent and pkexec are installed.")
                        # This specific error still uses a static call, which is fine for a critical app error.
                        QMessageBox.critical(None, "Error", "pkexec command not found.\nPlease ensure PolicyKit is correctly installed and configured.")
                    except Exception as e:
                        logger.error(f"An unexpected error occurred during pkexec execution: {e}")
                        # Also fine to use a static call for unexpected critical errors.
                        QMessageBox.critical(None, "Error", f"An unexpected error occurred while trying to run the helper script:\n{e}")

            elif clicked_button_role == manual_button:
                logger.info("User chose to view manual udev rules instructions.")
            else: # Includes clicking Close button or pressing Esc
                logger.info("User closed or cancelled the udev rules dialog.")
        
        if not self.headset_service.is_device_connected():
            logger.warning("Headset not detected on startup by HeadsetService.")
            # QSystemTrayIcon.supportsMessages() can check if backend supports this.
            # For now, tooltip will indicate disconnected state.
            # print("Warning: Headset not detected on startup.")
            pass

        self.tray_icon = sti.SystemTrayIcon(
            self.headset_service, 
            self.config_manager,
            self.quit_application
        )
        self.tray_icon.show()
        
        # Apply persisted settings on startup
        self.tray_icon.set_initial_headset_settings()


    def run(self):
        return self.qt_app.exec()

    def quit_application(self):
        logger.info("Application quitting.")
        self.headset_service.close() # Clean up HID connection
        self.qt_app.quit()