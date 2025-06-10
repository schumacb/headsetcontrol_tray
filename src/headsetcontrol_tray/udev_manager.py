import logging
import os
import tempfile

from . import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Format VID and PIDs as 4-digit lowercase hex strings
VID_HEX = f"{app_config.STEELSERIES_VID:04x}"
RULE_LINES: list[str] = [
    f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{VID_HEX}", ATTRS{{idProduct}}=="{pid:04x}", TAG+="uaccess"'
    for pid in app_config.TARGET_PIDS
]
UDEV_RULE_CONTENT: str = "\n".join(RULE_LINES)
UDEV_RULE_FILENAME: str = "99-steelseries-headsets.rules"


class UDEVManager:
    def __init__(self):
        self.last_udev_setup_details: dict[str, str] | None = None
        logger.debug("UDEVManager initialized.")

    def create_rules_interactive(self) -> bool:
        """Creates a temporary udev rule file and logs instructions for the user."""
        final_rules_path_str = os.path.join("/etc/udev/rules.d/", UDEV_RULE_FILENAME)
        logger.info(f"Attempting to guide user for udev rule creation for {final_rules_path_str}")

        self.last_udev_setup_details = None
        try:
            # Create a temporary file to write the rules to
            # delete=False means the file is not deleted when closed, so user can copy it.
            with tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="headsetcontrol_", suffix=".rules") as tmp_file:
                temp_file_name = tmp_file.name
                tmp_file.write(UDEV_RULE_CONTENT + "\n") # Ensure a newline at the end

            self.last_udev_setup_details = {
                "temp_file_path": temp_file_name,
                "final_file_path": final_rules_path_str,
                "rule_filename": UDEV_RULE_FILENAME,
                "rule_content": UDEV_RULE_CONTENT,
            }
            logger.info(f"Successfully wrote udev rule content to temporary file: {temp_file_name}")
            logger.info("--------------------------------------------------------------------------------")
            logger.info("ACTION REQUIRED: To complete headset setup, please run the following commands:")
            logger.info(f'1. Copy the rule file: sudo cp "{temp_file_name}" "{final_rules_path_str}"')
            logger.info("2. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger")
            logger.info("3. Replug your SteelSeries headset if it was connected.")
            logger.info(f"(The temporary file {temp_file_name} can be deleted after copying.)")
            logger.info("--------------------------------------------------------------------------------")
            return True
        except OSError as e:
            logger.error(f"Could not write temporary udev rule file: {e}")
            self.last_udev_setup_details = None
            return False
        except Exception as e_global: # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred during temporary udev rule file creation: {e_global}")
            self.last_udev_setup_details = None
            return False

    def get_last_udev_setup_details(self) -> dict[str, str] | None:
        """Returns details of the last udev setup attempt if one was made in this session."""
        return self.last_udev_setup_details
