#!/bin/bash
# KI-ana OS - Quick Start Script

set -e

echo "=================================================="
echo "🚀 KI-ana OS - Quick Start"
echo "=================================================="
echo ""

# Check if in os directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Please run this from the os/ directory"
    exit 1
fi

# Create venv if needed
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "=================================================="
echo "🧪 Available Tests:"
echo "=================================================="
echo ""
echo "1. Test Hardware Intelligence:"
echo "   python examples/test_hardware.py"
echo ""
echo "2. Test Enhanced AI Brain:"
echo "   python examples/test_enhanced_brain.py"
echo ""
echo "3. Run Interactive AI Core:"
echo "   python core/ai_engine/main.py"
echo ""
echo "=================================================="
