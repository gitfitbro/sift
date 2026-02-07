#!/usr/bin/env bash
# sift setup script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Default to project-local data directory (can override with SIFT_HOME env var)
SIFT_HOME="${SIFT_HOME:-$SCRIPT_DIR/data}"

echo "╔══════════════════════════════════════╗"
echo "║          sift installer              ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.10"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "Python $PYTHON_VERSION detected"

# Create directories
echo "Creating directories..."
mkdir -p "$SIFT_HOME/templates"
mkdir -p "$SIFT_HOME/sessions"
echo "Created $SIFT_HOME"

# Copy templates
echo "Installing templates..."
cp "$SCRIPT_DIR/templates/"*.yaml "$SIFT_HOME/templates/" 2>/dev/null || true
echo "Templates installed"

# Create virtual environment (recreate if stale or from another project)
VENV_DIR="$SCRIPT_DIR/.venv"
RECREATE_VENV=false
if [ ! -d "$VENV_DIR" ]; then
    RECREATE_VENV=true
elif ! grep -q "$VENV_DIR" "$VENV_DIR/bin/activate" 2>/dev/null; then
    echo "Existing .venv has incorrect paths, recreating..."
    rm -rf "$VENV_DIR"
    RECREATE_VENV=true
fi

if [ "$RECREATE_VENV" = true ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created at $VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# Use the venv's own pip directly (avoids PEP 668 externally-managed errors)
PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"

# Upgrade pip inside the venv
echo "Upgrading pip..."
"$PYTHON" -m pip install --upgrade pip --quiet

# Install package in editable mode
echo ""
echo "Installing sift..."
"$PIP" install -e "$SCRIPT_DIR[all]" --quiet
echo "sift installed successfully"

echo ""
echo "Setup complete!"
echo ""
echo "Quick Start:"
echo "  source .venv/bin/activate                       # Activate the venv (new shells)"
echo "  sift template list                              # List available templates"
echo "  sift new workflow-extraction --name my-session  # Create a session"
echo "  sift run my-session                             # Interactive mode"
echo ""
echo "Data Locations:"
echo "  Project:   $SCRIPT_DIR"
echo "  Templates: $SIFT_HOME/templates/"
echo "  Sessions:  $SIFT_HOME/sessions/"
echo ""
echo "For AI features (transcription + extraction), set your API key:"
echo "  cp .env.example .env"
echo "  # Edit .env and add your key"
echo ""
