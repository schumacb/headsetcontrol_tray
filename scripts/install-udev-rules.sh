#!/bin/sh
set -e

TEMP_RULE_FILE="$1"
FINAL_RULE_FILE="$2"

if [ -z "$TEMP_RULE_FILE" ] || [ -z "$FINAL_RULE_FILE" ]; then
  echo "Error: Missing arguments. Usage: $0 <temp_rule_file> <final_rule_file>" >&2
  exit 1
fi

if [ ! -f "$TEMP_RULE_FILE" ]; then
  echo "Error: Temporary rule file '$TEMP_RULE_FILE' not found." >&2
  exit 2
fi

DEST_DIR=$(dirname "$FINAL_RULE_FILE")
# Use sudo -u to ensure the directory is created with appropriate ownership if needed,
# though pkexec runs the whole script as root, so direct mkdir is fine.
mkdir -p "$DEST_DIR" || {
  echo "Error: Could not create destination directory '$DEST_DIR'." >&2
  exit 3
}

cp "$TEMP_RULE_FILE" "$FINAL_RULE_FILE" || {
  echo "Error: Failed to copy '$TEMP_RULE_FILE' to '$FINAL_RULE_FILE'." >&2
  exit 4
}
echo "Helper: Successfully copied udev rule to '$FINAL_RULE_FILE'."

udevadm control --reload-rules || {
  echo "Error: 'udevadm control --reload-rules' failed." >&2
  exit 5
}
echo "Helper: Successfully reloaded udev rules."

udevadm trigger || {
  echo "Error: 'udevadm trigger' failed." >&2
  exit 6
}
echo "Helper: Successfully triggered udev."

echo "Helper: Udev rules installed and reloaded successfully."
exit 0
