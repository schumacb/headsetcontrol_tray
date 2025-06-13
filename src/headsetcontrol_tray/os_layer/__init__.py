import platform

from .linux import LinuxImpl
from .windows import WindowsImpl
from .macos import MacOSImpl


def get_os_platform():
  """Detects the OS and returns an instance of the appropriate OS-specific implementation."""
  system = platform.system()
  if system == "Linux":
    return LinuxImpl()
  elif system == "Windows":
    return WindowsImpl()
  elif system == "Darwin":
    return MacOSImpl()
  else:
    raise OSError(f"Unsupported OS: {system}")
