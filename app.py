# steelseries_tray/app.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from . import config_manager as cfg_mgr
from . import headset_service as hs_svc
from .ui import system_tray_icon as sti
from . import app_config

class SteelSeriesTrayApp:
    """Main application class for the SteelSeries Headset Tray Utility."""

    def __init__(self):
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
        
        if not self.headset_service.is_device_connected():
            # Show a message if device not found on startup.
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
        self.headset_service.close() # Clean up HID connection
        self.qt_app.quit()