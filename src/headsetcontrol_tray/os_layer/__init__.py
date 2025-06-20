"""This package provides OS-specific abstractions for hardware interaction.

It defines a base `OSInterface` and `HIDManagerInterface`, along with concrete
implementations for different operating systems like Linux, Windows, and macOS.
This helps in managing OS-dependent tasks such as device discovery,
permission handling (e.g., udev rules on Linux), and path configurations.
"""
