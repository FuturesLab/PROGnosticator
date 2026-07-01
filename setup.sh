#!/bin/bash

set -e

echo "[INFO] Updating package index..."
sudo apt update

echo "[INFO] Installing system dependencies..."
sudo apt install -y python3 python3-pip git

echo "[INFO] Installing Python dependencies..."
pip3 install \
  tree-sitter \
  tree-sitter-c \
  tree-sitter-go \
  tree-sitter-javascript \
  python-dotenv \
  openai \
  matplotlib \
  psutil

echo "[INFO] Setup complete."
echo "[INFO] Make sure OPENAI_API_KEY is set before running PROGnosticator."