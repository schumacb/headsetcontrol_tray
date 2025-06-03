import sys
import logging
import os
from PySide6.QtWidgets import QApplication, QMessageBox # Added QMessageBox
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
            temp_file = details["temp_file_path"]
            final_file = details["final_file_path"]
            # rule_filename = details["rule_filename"] # Available if needed

            message_title = "Headset Permissions Setup Required"
            message_string = f"""
Headset Permissions Setup Required

The necessary udev rules for your SteelSeries headset are missing or incorrect.
A rule file has been prepared for you at:
{temp_file}

Please perform the following steps in a terminal:
1. Copy the rule file:
   sudo cp "{temp_file}" "{final_file}"
2. Reload udev rules:
   sudo udevadm control --reload-rules && sudo udevadm trigger
3. Replug your headset.

Without these rules, the application might not be able to detect or control your headset.
            """.strip()
            QMessageBox.information(None, message_title, message_string)
        
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