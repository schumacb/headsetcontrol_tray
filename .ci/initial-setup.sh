# Install uv
curl -LsSf https://astral.sh/uv/install.sh | \sh

# Source the environment file from uv to add its directory to PATH
source /home/swebot/.local/bin/env  # Using the absolute path from your log

# Your existing PATH export line for .cargo/bin etc. can then be:
# export PATH="$PATH" # If the source command already set it up perfectly
# OR ensure $HOME/.local/bin is also in it if you still need to define other paths:
export PATH="/home/swebot/.local/bin:$PATH" # This prepends it to whatever PATH became after sourcing

# Now proceed with your project setup
set -eux
# cd /app # You should already be in /app
uv venv
source .venv/bin/activate

sudo apt-get update --allow-releaseinfo-change || echo "apt-get update failed but we continue"
sudo apt-get install -y python3.10-dev
uv pip install -e .
