"""Manages Linux udev rules for SteelSeries headset device permissions.

This module provides the `UDEVManager` class, responsible for generating
the content of udev rules, defining their target installation path,
and checking if the rules seem to be installed. It also handles the
creation of temporary rule files for manual or scripted installation.
"""
import logging
from pathlib import Path
import tempfile

from . import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Format VID and PIDs as 4-digit lowercase hex strings
VID_HEX = f"{app_config.STEELSERIES_VID:04x}"
RULE_LINES: list[str] = [
    (f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{VID_HEX}", ATTRS{{idProduct}}=="{pid:04x}", TAG+="uaccess"')
    for pid in app_config.TARGET_PIDS
]
UDEV_RULE_CONTENT: str = "\n".join(RULE_LINES) + "\n"  # Ensure trailing newline
UDEV_RULE_FILENAME: str = "99-steelseries-headsets.rules"
UDEV_RULES_DIR: Path = Path("/etc/udev/rules.d/")


class UDEVManager:
    """Handles the generation and status checking of udev rules for SteelSeries headsets."""

    def __init__(self) -> None:
        """Initializes the UDEVManager."""
        self.last_udev_setup_details: dict[str, str] | None = None
        logger.debug("UDEVManager initialized.")

    def get_rule_content(self) -> str:
        """Returns the generated udev rule content."""
        return UDEV_RULE_CONTENT

    def get_rule_filename(self) -> str:
        """Returns the target filename for the udev rules."""
        return UDEV_RULE_FILENAME

    def get_final_rules_path(self) -> Path:
        """Returns the final absolute path for the udev rule file."""
        return UDEV_RULES_DIR / UDEV_RULE_FILENAME

    def create_rules_interactive(self) -> bool:  # Renamed from prepare_udev_rule_details
        """Creates a temporary udev rule file and stores its details.

        This method is intended to be called when setup is needed.
        It also logs manual installation instructions to the console.
        Returns True if details were prepared successfully, False otherwise.
        """
        final_rules_path = self.get_final_rules_path()
        logger.info(
            "Preparing udev rule details for potential installation to %s",
            str(final_rules_path),
        )

        self.last_udev_setup_details = None  # Reset previous details
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,  # File is not deleted when closed, so it can be copied
                prefix="headsetcontrol_tray_",  # Add app name for clarity
                suffix=".rules",
                dir=tempfile.gettempdir(),  # Use system temp dir
            ) as tmp_file:
                temp_file_name = tmp_file.name
                tmp_file.write(self.get_rule_content())

            self.last_udev_setup_details = {
                "temp_file_path": temp_file_name,
                "final_file_path": str(final_rules_path),
                "rule_filename": self.get_rule_filename(),
                "rule_content": self.get_rule_content(),
            }
            logger.info(
                "Successfully wrote udev rule content to temporary file: %s",
                temp_file_name,
            )
            # Log manual instructions for fallback or if automatic setup fails
            logger.info("--------------------------------------------------------------------------------")
            logger.info("MANUAL UDEV SETUP (if automatic setup is not used or fails):")
            logger.info(' 1. Copy the rule file: sudo cp "%s" "%s"', temp_file_name, str(final_rules_path))
            logger.info(" 2. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger")
            logger.info(" 3. Replug your SteelSeries headset if it was connected.")
            logger.info(" (The temporary file %s can be deleted after copying.)", temp_file_name)
            logger.info("--------------------------------------------------------------------------------")
        except OSError:
            logger.exception("Could not write temporary udev rule file")
            self.last_udev_setup_details = None
            return False
        except Exception:  # Catch any other unexpected error
            logger.exception("An unexpected error occurred during temporary udev rule file creation")
            self.last_udev_setup_details = None
            return False
        else:
            return True

    def get_last_udev_setup_details(self) -> dict[str, str] | None:
        """Returns details of the last udev setup preparation attempt made in this session.

        This includes paths to temporary and final rule files, and the rule content.
        """
        return self.last_udev_setup_details

    def are_rules_installed(self) -> bool:
        """Checks if the udev rule file appears to be installed.

        Note: This is a basic check for file existence. It does not verify
        content or full functionality without appropriate permissions.
        """
        final_rules_path = self.get_final_rules_path()
        if not final_rules_path.exists():
            logger.info("Udev rule file %s does not exist.", str(final_rules_path))
            return False

        # Content check is difficult without root.
        # A simple existence check is often sufficient to gate interactive setup.
        # If the file exists but is incorrect, that's a harder problem for auto-detection.
        logger.info("Udev rule file %s exists. Assuming rules are installed.", str(final_rules_path))
        # Further checks could be:
        # 1. Read content if permissions allow (unlikely for /etc/udev/rules.d).
        # 2. Check device node permissions (e.g., /dev/hidraw*) if a device is connected.
        #    This is more complex and device-specific.
        # For now, existence is the primary check.
        return True
