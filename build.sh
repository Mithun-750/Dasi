#!/bin/bash

# Exit on error
set -e

# Create and activate virtual environment
echo "Setting up virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "Building Dasi..."
pyinstaller dasi.spec --clean

echo "Creating desktop entry..."
cat > ~/.local/share/applications/dasi.desktop << EOL
[Desktop Entry]
Version=1.0
Name=Dasi
Comment=Linux Copilot with LLM Support
Exec=${PWD}/dist/dasi/dasi
Icon=${PWD}/src/assets/Dasi.png
Terminal=false
Type=Application
Categories=Utility;Development;
EOL

# Deactivate virtual environment
deactivate

echo "Build complete!"
echo "You can find the bundled application in the 'dist/dasi' directory"
echo "A desktop entry has been created. You can now launch Dasi from your application menu."
