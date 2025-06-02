import sys

def main():
    all_successful = True
    error_messages = []

    # Test verboselogs
    try:
        import verboselogs
        print("Successfully imported verboselogs")
    except ImportError as e:
        print(f"Error importing verboselogs: {e}")
        error_messages.append(f"verboselogs: {e}")
        all_successful = False

    # Test PySide6.QtCore
    try:
        from PySide6 import QtCore
        print("Successfully imported PySide6.QtCore")
    except ImportError as e:
        print(f"Error importing PySide6.QtCore: {e}")
        error_messages.append(f"PySide6.QtCore: {e}")
        all_successful = False

    # Test hid (from hidapi)
    try:
        import hid
        print("Successfully imported hid (from hidapi)")
    except ImportError as e:
        print(f"Error importing hid (from hidapi): {e}")
        error_messages.append(f"hid: {e}")
        all_successful = False

    if all_successful:
        print("\nAll core dependencies imported successfully!")
        sys.exit(0)
    else:
        print("\nSome dependencies failed to import:")
        for msg in error_messages:
            print(f"- {msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
