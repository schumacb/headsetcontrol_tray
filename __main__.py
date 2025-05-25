# steelseries_tray/main.py
import sys
import signal # To handle Ctrl+C in console

# Before importing PySide6, set XDG_SESSION_TYPE if it's Wayland, for hidapi
# This is a common workaround for hidapi issues under Wayland with some compositors
# import os
# if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
#    os.environ["QT_QPA_PLATFORM"] = "xcb" # Force X11 backend for Qt if hidapi has issues

from .app import SteelSeriesTrayApp

def main():
    # Graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    application = SteelSeriesTrayApp()
    sys.exit(application.run())

if __name__ == "__main__":
    main()