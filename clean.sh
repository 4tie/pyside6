#!/usr/bin/env bash
# clean.sh — Remove __pycache__ dirs and .pytest_cache from the project
# Excludes .venv and .git to avoid breaking the virtual environment

set -e

echo "=== Cleaning __pycache__ directories ==="
find . -type d -name "__pycache__" \
  -not -path "./.venv/*" \
  -not -path "./.git/*" \
  -exec rm -rf {} + 2>/dev/null || true
echo "Done."

echo "=== Cleaning .pytest_cache directories ==="
find . -type d -name ".pytest_cache" \
  -not -path "./.venv/*" \
  -not -path "./.git/*" \
  -exec rm -rf {} + 2>/dev/null || true
echo "Done."

echo "=== Cleaning .hypothesis/examples (test shrink cache) ==="
rm -rf .hypothesis/examples 2>/dev/null || true
echo "Done."

echo "All caches cleaned."
