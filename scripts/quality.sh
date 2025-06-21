#! /bin/bash
# set -e # Exit immediately if a command exits with a non-zero status.

echo ===== running pytest =====

# Define the base pytest command. Note: The example in prompt had more options like --cov.
# Using the simpler one from the original script for now.
PYTEST_BASE_CMD="uv run pytest --cov=src --cov-report=xml --cov-report=html --junitxml=build/reports/pytest.xml tests/"
PYTEST_FINAL_CMD="$PYTEST_BASE_CMD"

# Check if DISPLAY is not set or is empty
if [ -z "$DISPLAY" ]; then
  echo "No display server found (DISPLAY is not set or empty), running pytest under xvfb-run."
  export QT_QPA_PLATFORM=offscreen
  PYTEST_FINAL_CMD="xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' $PYTEST_BASE_CMD"
else
  echo "Display server found (DISPLAY=$DISPLAY), running pytest directly."
  # If QT_QPA_PLATFORM was set globally and is not desired for direct display,
  # it could be unset here: unset QT_QPA_PLATFORM
  # For now, we assume if DISPLAY is set, QT_QPA_PLATFORM (if set by user) is respected or not harmful.
fi

echo "Executing: $PYTEST_FINAL_CMD"
eval $PYTEST_FINAL_CMD # Use eval to correctly execute the command string with arguments

echo ===== running mypy =====
uv run mypy src tests
echo ===== running ruff check src =====
uv run ruff check src
echo ===== running ruff check tests =====
uv run ruff check tests
echo ===== running vulture =====
uv run vulture src tests vulture_whitelist.py --min-confidence 60
echo ===== running radon cc . -a -s =====
uv run radon cc . -a -s
echo ===== running radon mi . -s =====
uv run radon mi . -s
echo ===== FINISHED =====