"""Custom exceptions for the HeadsetControl Tray application."""


class HeadsetControlTrayError(Exception):
    """Base exception for headsetcontrol_tray application errors."""

    def __init__(self, message: str | None = None, *args: object) -> None:
        """Initialize the HeadsetControlTrayError."""
        if message is not None:
            super().__init__(message, *args)
        else:
            # This allows subclasses to define a message if none is provided
            default_msg = "An unspecified error occurred."
            if hasattr(self, "default_message"):
                default_msg = self.default_message
            super().__init__(default_msg, *args)


class TrayAppInitializationError(HeadsetControlTrayError):
    """Custom error for application initialization failures."""

    default_message = "Helper script missing."  # Specific to the known TRY003 case


class ConfigError(HeadsetControlTrayError):
    """Custom error for configuration related issues."""

    # This default can be for "Invalid EQ values"
    default_message = "Invalid EQ values."

    def __init__(self, message: str | None = None, filepath: str | None = None) -> None:
        """Initialize the ConfigError."""
        if filepath is not None:
            # This handles the "Configuration file not found" case specifically
            message = f"Configuration file not found at {filepath}"
        # If message is still None (filepath was None, and no message passed),
        # it will use default_message from the class via super().__init__
        super().__init__(message)


class HIDCommunicationError(HeadsetControlTrayError):
    """Custom error for HID communication failures."""

    default_message = "Invalid HID device."  # Specific to the known TRY003 case
