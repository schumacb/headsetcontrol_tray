#! /bin/sh
# Enable Qt plugin debugging and ensure tests run in a virtual display environment
export QT_DEBUG_PLUGINS=1
xvfb-run -a uv run pytest
