import sys
import signal

from .app import SteelSeriesTrayApp

def main():
    # Graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    application = SteelSeriesTrayApp()
    sys.exit(application.run())

if __name__ == "__main__":
    main()