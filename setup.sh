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

# Install package
echo ""
echo "Installing sift..."
if pip install -e "$SCRIPT_DIR[all]" --quiet 2>/dev/null; then
    echo "sift installed successfully"
elif pip install -e "$SCRIPT_DIR[all]" --user --quiet 2>/dev/null; then
    echo "sift installed (user)"
else
    echo "Automated install failed. Please run manually:"
    echo "    pip install -e \".[all]\""
fi

echo ""
echo "Setup complete!"
echo ""
echo "Quick Start:"
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
