#! /bin/sh

# This script is the definitive way to run pytest for this project.
# It includes xvfb-run for headless environments and standard pytest arguments.

# Enable Qt plugin debugging (can be removed later if tests are stable)
export QT_DEBUG_PLUGINS=1

# Ensure xvfb is installed right before it's potentially used
echo "Ensuring xvfb is installed for test execution..."
sudo apt-get update -y --allow-releaseinfo-change > /dev/null
sudo apt-get install -y xvfb > /dev/null
echo "xvfb installation check complete."

# Define the base pytest command with coverage and reporting
# Targeting the 'tests/' directory specifically.
PYTEST_CMD="uv run pytest --cov=src --cov-report=xml --cov-report=html --junitxml=build/reports/pytest.xml tests/"

# Check if DISPLAY is not set or is empty, common in CI/headless environments
if [ -z "$DISPLAY" ]; then
  echo "No display server found (DISPLAY is not set or empty)."
  echo "Running pytest under xvfb-run with QT_QPA_PLATFORM=offscreen."
  # Using offscreen platform plugin is generally more robust for headless Qt execution
  export QT_QPA_PLATFORM=offscreen
  # Execute pytest under xvfb-run, using full path for robustness
  /usr/bin/xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' $PYTEST_CMD
else
  echo "Display server found (DISPLAY=$DISPLAY). Running pytest directly."
  # If QT_QPA_PLATFORM was set by a previous CI step and is not 'offscreen',
  # it might be respected or could be explicitly unset if needed.
  # For now, assume if DISPLAY is set, direct execution is intended.
  $PYTEST_CMD
fi
