#! /bin/bash
# set -e # Exit immediately if a command exits with a non-zero status.

echo ===== running pytest via test.sh =====
# xvfb installation is now handled within test.sh

# Ensure test.sh is executable and run it
chmod +x ./scripts/test.sh
./scripts/test.sh

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