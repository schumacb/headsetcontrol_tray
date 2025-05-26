import sys
import signal
import logging
import verboselogs

# Install verboselogs custom levels into the standard logging module
# This MUST be done before other application modules (that use logging) are imported.
verboselogs.install()

from .app import SteelSeriesTrayApp

def main():
    # Graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    application = SteelSeriesTrayApp()
    sys.exit(application.run())

if __name__ == "__main__":
    main()