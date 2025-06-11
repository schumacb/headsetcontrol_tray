#!/bin/bash
set -e

echo "Starting development environment setup..."

# Check for uv, install if not found
if ! command -v uv &> /dev/null
then
    echo "uv could not be found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the environment script to make uv available in the current session
    if [ -f "$HOME/.cargo/env" ]; then
        source "$HOME/.cargo/env"
    elif [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    else
        echo "Warning: Could not find standard uv environment script to source. You might need to add uv to your PATH manually or restart your shell."
    fi
else
    echo "uv is already installed."
fi

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
else
    echo "Virtual environment .venv already exists."
fi

# Activate virtual environment (for subsequent commands in this script)
# Note: This activation is for the script's context.
# The user will need to source it themselves for their shell session.
source .venv/bin/activate
echo "Activated virtual environment for script execution."

# Install Python dependencies
echo "Installing Python dependencies..."
uv pip install -e ".[dev]"

# Install system dependencies
echo "Installing system dependencies (requires sudo)..."
if command -v sudo &> /dev/null
then
    sudo apt-get update && sudo apt-get install -y python3.10-dev xvfb x11-utils libhidapi-dev
else
    echo "sudo command not found. Please install system dependencies manually:"
    echo "  apt-get install -y python3.10-dev xvfb x11-utils libhidapi-dev"
fi

echo ""
echo "Development environment setup complete!"
echo "To activate the virtual environment in your shell, run: source .venv/bin/activate"
echo "After activation, you can run the quality script: bash scripts/quality.sh"
