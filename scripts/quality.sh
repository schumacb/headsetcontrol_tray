#! /bin/bash

echo ===== running pytest =====
uv run pytest
echo ===== running mypy =====
uv run mypy .
echo ===== running ruff check src =====
uv run ruff check src
echo ===== running ruff check tests =====
uv run ruff check tests
echo ===== running vulture src =====
uv run vulture src
echo ===== running vulture tests =====
uv run vulture tests
echo ===== running radon cc . -a -s =====
uv run radon cc . -a -s
echo ===== running radon mi . -s =====
uv run radon mi . -s
echo ===== FINISHED =====