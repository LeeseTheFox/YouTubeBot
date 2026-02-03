#!/bin/bash

# Startup script for YouTube Bot
# This script ensures all dependencies are installed before starting the bot

set -e  # Exit on error

echo "🚀 Starting YouTube Bot setup..."

# Activate virtual environment if it exists
if [ -f "/opt/venv/bin/activate" ]; then
    echo "📦 Activating virtual environment..."
    source /opt/venv/bin/activate
fi

# Check and install curl if missing
if ! command -v curl &> /dev/null; then
    echo "📥 Installing curl..."
    apt-get update -qq
    apt-get install -y curl
else
    echo "✅ curl is already installed"
fi

# Check and install unzip if missing
if ! command -v unzip &> /dev/null; then
    echo "📥 Installing unzip..."
    apt-get update -qq
    apt-get install -y unzip
else
    echo "✅ unzip is already installed"
fi

# Check and install Deno if missing
if ! command -v deno &> /dev/null; then
    echo "📥 Installing Deno..."
    curl -fsSL https://deno.land/install.sh | sh
    
    # Add Deno to PATH
    export DENO_INSTALL="$HOME/.deno"
    export PATH="$DENO_INSTALL/bin:$PATH"
    
    # Verify installation
    if command -v deno &> /dev/null; then
        echo "✅ Deno installed successfully: $(deno --version | head -n 1)"
    else
        echo "❌ Deno installation failed"
        exit 1
    fi
else
    echo "✅ Deno is already installed: $(deno --version | head -n 1)"
    export DENO_INSTALL="$HOME/.deno"
    export PATH="$DENO_INSTALL/bin:$PATH"
fi

# Ensure Python dependencies are installed
echo "📦 Checking Python dependencies..."
pip install --upgrade pip -q
pip install --upgrade --pre yt-dlp -q
pip install -r requirements.txt -q

echo "✅ All dependencies are ready!"
echo "🤖 Starting YouTube Bot..."
echo ""

# Start the bot
python main.py
