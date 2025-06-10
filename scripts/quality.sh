#! /bin/bash

uv run pytest
uv run mypy .
uv run ruff check src
uv run ruff check tests
uv run vulture src
uv run vulture tests
uv run radon cc . -a -s
uv run radon mi . -s