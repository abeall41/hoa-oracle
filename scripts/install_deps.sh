#!/bin/bash
# Install project dependencies on hoa-api (CPU-only server, no GPU).
# Run this instead of "pip install -r requirements.txt" directly.
# torch must be installed from the CPU-only index before sentence-transformers
# pulls in the full CUDA build from PyPI.

set -e

echo "Installing CPU-only PyTorch..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo "Installing remaining dependencies..."
pip install -r "$(dirname "$0")/../requirements.txt"

echo "Done."
