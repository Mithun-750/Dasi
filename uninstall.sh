#!/bin/bash

# Exit on error
set -e

echo "Uninstalling Dasi..."

# Remove desktop entry
rm -f ~/.local/share/applications/dasi.desktop

# Remove config directory
rm -rf ~/.config/dasi

# Remove build artifacts
rm -rf build/ dist/ 
# rm -f *.spec

echo "Uninstall complete!"
echo "Note: The source code directory has not been removed."