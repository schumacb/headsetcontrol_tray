"""Main entry point for the HeadsetControl Tray application."""

import signal
import sys

import verboselogs

from headsetcontrol_tray.app import SteelSeriesTrayApp


# Install verboselogs custom levels into the standard logging module
# This MUST be done before other application modules (that use logging) are imported.
def main() -> None:
    """Runs the main application."""
    # Graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Install verboselogs custom levels. This must be done before SteelSeriesTrayApp is instantiated.
    verboselogs.install()
    application = SteelSeriesTrayApp()
    sys.exit(application.run())


if __name__ == "__main__":
    main()
