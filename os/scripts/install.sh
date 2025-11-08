#!/bin/bash
# KI-ana OS - One-Line Installer

set -e

echo "=================================================="
echo "🚀 KI-ana OS Installer"
echo "=================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

echo "✅ Python 3 found"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "Installing pip..."
    python3 -m ensurepip
fi

# Create venv
echo "📦 Creating virtual environment..."
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "=================================================="
echo "✅ Installation Complete!"
echo "=================================================="
echo ""
echo "🚀 Quick Start:"
echo ""
echo "  # Activate environment:"
echo "  source .venv/bin/activate"
echo ""
echo "  # Run tests:"
echo "  python examples/test_smart_brain.py"
echo ""
echo "  # Interactive mode:"
echo "  python core/ai_engine/smart_main.py"
echo ""
echo "  # Voice mode (requires microphone):"
echo "  python core/ai_engine/voice_brain.py"
echo ""
echo "=================================================="
