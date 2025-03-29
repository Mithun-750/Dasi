#!/bin/bash
# =============================================================================
# Dasi AppImage Creator
# =============================================================================
# This script creates a self-contained AppImage package for the Dasi application.
# 
# The AppImage includes:
# - Python interpreter and standard library
# - All required Python dependencies
# - Qt libraries and plugins for PyQt6
# - System libraries and dependencies
# - Application icon and desktop entry
#
# The resulting AppImage can be run on most Linux distributions without
# requiring installation or additional dependencies.
#
# Usage:
#   1. Ensure you have a working Python virtual environment with all required
#      dependencies installed.
#   2. Make this script executable: chmod +x scripts/create_appimage.sh
#   3. Run the script: ./scripts/create_appimage.sh
#   4. The AppImage will be created in the project root directory
#
# The final AppImage can be run directly:
#   ./Dasi-x.y.z-x86_64.AppImage
#
# Or with the extract-and-run option if FUSE is not available:
#   ./Dasi-x.y.z-x86_64.AppImage --appimage-extract-and-run
# =============================================================================

set -e

# Navigate to project root directory (parent of scripts folder)
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# Color definitions
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${BLUE}[*] $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}[+] $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}[!] $1${NC}"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

# Error handling
error_handler() {
    print_error "An error occurred on line $1"
    exit 1
}

# Set up error trap
trap 'error_handler $LINENO' ERR

print_status "Starting AppImage creation process from: $PROJECT_ROOT"

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf AppDir || true
rm -rf Dasi-*.AppImage || true

# Create AppDir structure
print_status "Creating AppDir structure..."
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p AppDir/usr/share/pixmaps
mkdir -p AppDir/usr/lib/python3.10/site-packages

# Copy application files
print_status "Copying application files..."
cp -r src AppDir/usr/
cp LICENSE AppDir/usr/
cp README.md AppDir/usr/

# Copy default prompt chunks
print_status "Copying default prompt chunks..."
mkdir -p AppDir/usr/defaults/prompt_chunks
cp -r defaults/prompt_chunks/* AppDir/usr/defaults/prompt_chunks/

cp -r .venv/lib/python3.10/site-packages/* AppDir/usr/lib/python3.10/site-packages/

# Copy Python standard library (more comprehensive approach)
print_status "Copying Python standard library..."
cp -L $(which python3) AppDir/usr/bin/
mkdir -p AppDir/usr/lib/python3.10
cp -r /usr/lib/python3.10/* AppDir/usr/lib/python3.10/
# Include Python dynamic libraries
cp /usr/lib/x86_64-linux-gnu/libpython3.10.so* AppDir/usr/lib/ || true
cp /usr/lib/libpython3.10.so* AppDir/usr/lib/ || true

# Copy Qt plugins and libraries
print_status "Copying Qt plugins and libraries..."
mkdir -p AppDir/usr/plugins
find .venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins -name "*.so" -exec cp -v --parents {} AppDir/usr/ \; 2>/dev/null || print_warning "No Qt plugins found"

# Copy shared libraries
print_status "Copying shared libraries..."
mkdir -p AppDir/usr/lib
ldd AppDir/usr/bin/python3 | grep "=> /" | awk '{print $3}' | sort | uniq | xargs -I '{}' cp -v '{}' AppDir/usr/lib/ 2>/dev/null || print_warning "Failed to copy some Python libraries"

# Try to copy Qt libraries if available
if [ -d ".venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms" ]; then
    ldd .venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so 2>/dev/null | grep "=> /" | awk '{print $3}' | sort | uniq | xargs -I '{}' cp -v '{}' AppDir/usr/lib/ || print_warning "Failed to copy some Qt libraries"
else
    print_warning "Qt platform plugins not found, this may not be a PyQt application"
fi

# Also include additional dependencies that might be needed
print_status "Resolving additional dependencies..."
for lib in $(find AppDir/usr/lib -name "*.so*"); do
    ldd $lib 2>/dev/null | grep "=> /" | awk '{print $3}' | sort | uniq | xargs -I '{}' cp -v '{}' AppDir/usr/lib/ || true
done

# Set up icon
print_status "Setting up application icon..."
ICON_FOUND=false

# First try to use PNG icon (preferred for AppImage)
if [ -f "src/assets/Dasi.png" ]; then
    # Copy the main icon
    cp src/assets/Dasi.png AppDir/dasi.png
    cp src/assets/Dasi.png AppDir/usr/share/icons/hicolor/256x256/apps/dasi.png
    cp src/assets/Dasi.png AppDir/usr/share/pixmaps/dasi.png
    
    # Copy the icon to .DirIcon directly instead of using a symlink
    cp src/assets/Dasi.png AppDir/.DirIcon
    
    # Try to convert icons to different sizes if ImageMagick is available
    if command -v convert &> /dev/null; then
        print_status "Converting icon to different sizes..."
        for size in 16 24 32 48 64 96 128 192; do
            mkdir -p AppDir/usr/share/icons/hicolor/${size}x${size}/apps
            convert src/assets/Dasi.png -resize ${size}x${size} AppDir/usr/share/icons/hicolor/${size}x${size}/apps/dasi.png || print_warning "Could not convert icon to ${size}x${size}, continuing anyway"
        done
    else
        print_warning "ImageMagick not available. Only using the 256x256 icon."
    fi
    
    print_success "Icon set successfully from PNG"
    ICON_FOUND=true
# Next try to use ICO file and convert it if possible
elif [ -f "src/assets/Dasi.ico" ]; then
    print_status "Found ICO file, attempting to use it..."
    
    # Check if convert (ImageMagick) is available
    if command -v convert &> /dev/null; then
        print_status "Converting ICO to PNG for AppImage..."
        
        # Extract the largest icon from the ICO file for the AppImage icon
        convert "src/assets/Dasi.ico[0]" AppDir/dasi.png
        cp AppDir/dasi.png AppDir/.DirIcon
        cp AppDir/dasi.png AppDir/usr/share/icons/hicolor/256x256/apps/dasi.png
        cp AppDir/dasi.png AppDir/usr/share/pixmaps/dasi.png
        
        # Also generate smaller size icons
        for size in 16 24 32 48 64 96 128 192; do
            mkdir -p AppDir/usr/share/icons/hicolor/${size}x${size}/apps
            convert "src/assets/Dasi.ico[0]" -resize ${size}x${size} AppDir/usr/share/icons/hicolor/${size}x${size}/apps/dasi.png || print_warning "Could not convert icon to ${size}x${size}, continuing anyway"
        done
        
        # Create a high-quality PNG from the ICO for better appearance
        convert "src/assets/Dasi.ico[0]" -background none -flatten -alpha off AppDir/dasi.png
        cp AppDir/dasi.png AppDir/.DirIcon
        
        print_success "Icon converted and set successfully from ICO"
        ICON_FOUND=true
    else
        print_warning "ImageMagick not available. Cannot convert ICO to PNG for AppImage."
    fi
fi

if [ "$ICON_FOUND" = false ]; then
    print_warning "No usable icon found (tried src/assets/Dasi.png and src/assets/Dasi.ico)"
    print_warning "AppImage will have no icon. Please add a PNG or ICO icon file to src/assets/"
fi

# Create desktop file
print_status "Creating desktop entry..."
cat > AppDir/dasi.desktop << EOF
[Desktop Entry]
Type=Application
Name=Dasi
Comment=A powerful desktop copilot that provides inline LLM support
Exec=python3 /usr/src/main.py
Icon=dasi
Categories=Utility;Development;
Terminal=false
StartupNotify=true
EOF
print_success "Desktop entry created"

# Create AppRun script
print_status "Creating AppRun script..."
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

# Set up Python environment
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
export PYTHONPATH="${HERE}/usr/lib/python3.10:${HERE}/usr/lib/python3.10/site-packages:${HERE}/usr/src:${PYTHONPATH}"
export PYTHONHOME="${HERE}/usr"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

# Set up Qt environment
export QT_PLUGIN_PATH="${HERE}/usr/lib/python3.10/site-packages/PyQt6/Qt6/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="${HERE}/usr/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms"
export QML2_IMPORT_PATH="${HERE}/usr/lib/python3.10/site-packages/PyQt6/Qt6/qml"
export XDG_CONFIG_HOME="${HOME}/.config"
export QT_DEBUG_PLUGINS=1

# Set icon path for the application to use
export DASI_ICON_PATH="${HERE}/usr/share/icons/hicolor/256x256/apps/dasi.png"

# Set path for default prompt chunks
export DASI_DEFAULT_CHUNKS_PATH="${HERE}/usr/defaults/prompt_chunks"

# Create a script to modify the src/main.py file to use the absolute icon path
TEMP_SCRIPT="${HERE}/usr/src/icon_fix.py"
cat > "${TEMP_SCRIPT}" << 'PYTHON_EOF'
import os
import re

# Get the icon path from environment
icon_path = os.environ.get('DASI_ICON_PATH', '')
if not icon_path:
    print("Warning: DASI_ICON_PATH not set, icon might not display correctly")
    exit(0)

# Read the main.py file
main_file = os.path.join(os.path.dirname(__file__), 'main.py')
with open(main_file, 'r') as f:
    content = f.read()

# Check if we already modified this file
if "# APPIMAGE ICON FIX" in content:
    print("Icon fix already applied")
    exit(0)

# Add code to use the absolute icon path when running from AppImage
icon_fix = """
# APPIMAGE ICON FIX
import os
appimage_icon = os.environ.get('DASI_ICON_PATH')
if appimage_icon and os.path.exists(appimage_icon):
    print(f"Using AppImage icon from: {appimage_icon}")
    ICON_PATH = appimage_icon
"""

# Insert the fix at the beginning of the file after imports
# Look for a suitable position to insert the code
import_pattern = re.compile(r'((?:^|\n)import .*?(?:\n|$))', re.DOTALL)
matches = list(import_pattern.finditer(content))
if matches:
    # Find the last import statement
    last_import = matches[-1]
    position = last_import.end()
    # Insert the icon fix code after the last import
    new_content = content[:position] + icon_fix + content[position:]
    with open(main_file, 'w') as f:
        f.write(new_content)
    print("Icon fix applied to main.py")
else:
    print("Could not find a suitable position to insert icon fix")
PYTHON_EOF

# Run the icon fix script
"${HERE}/usr/bin/python3" "${TEMP_SCRIPT}"

# Create a script to initialize default prompt chunks from AppImage
CHUNKS_SCRIPT="${HERE}/usr/src/prompt_chunks_fix.py"
cat > "${CHUNKS_SCRIPT}" << 'PYTHON_EOF'
import os
import shutil
import logging
from pathlib import Path

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Get the default prompt chunks path from environment
default_chunks_path = os.environ.get('DASI_DEFAULT_CHUNKS_PATH', '')
if not default_chunks_path or not os.path.exists(default_chunks_path):
    logging.error(f"Default prompt chunks directory not found: {default_chunks_path}")
    exit(1)

# Determine the user's config directory
home_dir = Path.home()
config_dir = home_dir / '.config' / 'dasi'
target_chunks_dir = config_dir / 'prompt_chunks'

# Create the target directory if it doesn't exist
target_chunks_dir.mkdir(parents=True, exist_ok=True)

# Check if we need to copy default prompt chunks
if len(list(target_chunks_dir.glob('*.md'))) == 0:
    logging.info(f"No prompt chunks found in {target_chunks_dir}, copying defaults...")
    # Copy all files from default chunks directory
    for chunk_file in Path(default_chunks_path).glob('*.md'):
        target_file = target_chunks_dir / chunk_file.name
        shutil.copy2(chunk_file, target_file)
        logging.info(f"Copied default prompt chunk: {chunk_file.name}")
else:
    logging.info(f"Prompt chunks directory already exists with content, not copying defaults.")
    
    # Check for missing default chunks and copy them
    default_chunks = set(f.name for f in Path(default_chunks_path).glob('*.md'))
    existing_chunks = set(f.name for f in target_chunks_dir.glob('*.md'))
    missing_chunks = default_chunks - existing_chunks
    
    if missing_chunks:
        logging.info(f"Adding {len(missing_chunks)} missing default prompt chunks...")
        for chunk_name in missing_chunks:
            src_file = Path(default_chunks_path) / chunk_name
            target_file = target_chunks_dir / chunk_name
            shutil.copy2(src_file, target_file)
            logging.info(f"Added missing prompt chunk: {chunk_name}")

logging.info("Prompt chunks check completed")
PYTHON_EOF

# Run the prompt chunks initialization script
"${HERE}/usr/bin/python3" "${CHUNKS_SCRIPT}"

# Run the application with verbose output for easier debugging
exec "${HERE}/usr/bin/python3" -v "${HERE}/usr/src/main.py" "$@"
EOF

chmod +x AppDir/AppRun
print_success "AppRun script created"

# Download appimagetool
if [ ! -f "scripts/appimagetool-x86_64.AppImage" ]; then
    print_status "Downloading appimagetool..."
    wget -c "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O scripts/appimagetool-x86_64.AppImage
    chmod +x scripts/appimagetool-x86_64.AppImage
    print_success "Downloaded appimagetool"
else
    print_status "Using existing appimagetool"
fi

# Build the AppImage
print_status "Building AppImage..."
VERSION=$(grep -oP '(?<=version = ").*(?=")' pyproject.toml || echo "0.1.0")
ARCH=$(uname -m)

# Ensure .DirIcon has proper permissions
chmod 644 AppDir/.DirIcon || true
chmod 644 AppDir/dasi.png || true

# Verify icon files are present
if [ -f "AppDir/.DirIcon" ]; then
    print_status "Icon file (.DirIcon) found, it will be embedded in the AppImage"
else
    print_warning "No .DirIcon file found, AppImage may not have an icon"
    # Try to create it as a last resort
    if [ -f "src/assets/Dasi.png" ]; then
        cp src/assets/Dasi.png AppDir/.DirIcon
        print_status "Created .DirIcon from src/assets/Dasi.png"
    elif [ -f "src/assets/Dasi.ico" ] && command -v convert &> /dev/null; then
        convert src/assets/Dasi.ico AppDir/.DirIcon
        print_status "Created .DirIcon from src/assets/Dasi.ico"
    fi
fi

# Also make sure there's a root icon file with the same name as the desktop file
cp AppDir/.DirIcon AppDir/dasi.png || true

# Ensure icon name in desktop file matches the actual icon files
desktop_icon=$(grep -oP '(?<=Icon=).*' AppDir/dasi.desktop)
if [ -n "$desktop_icon" ]; then
    print_status "Desktop entry uses icon: $desktop_icon"
    # Create symlink from .DirIcon to the icon name in the desktop file if needed
    if [ "$desktop_icon" != "dasi" ] && [ -f "AppDir/.DirIcon" ]; then
        cp AppDir/.DirIcon "AppDir/$desktop_icon.png"
        print_status "Created icon with name $desktop_icon.png for desktop entry integration"
    fi
fi

# One final check - ensure the icon file is in the AppDir root with proper permissions
if [ -f "AppDir/.DirIcon" ]; then
    chmod 644 AppDir/.DirIcon
    # AppImageTool sometimes works better with the icon having the same name as the AppDir
    cp AppDir/.DirIcon AppDir/dasi.png
    chmod 644 AppDir/dasi.png
    print_status "Final icon setup complete"
fi

# Generate the AppImage with desktop integration
print_status "Running AppImageTool with desktop integration..."
ARCH=$ARCH ./scripts/appimagetool-x86_64.AppImage --comp xz -g AppDir "Dasi-${VERSION}-${ARCH}.AppImage"

print_success "AppImage created successfully!"
ls -la Dasi-*.AppImage

print_status "To run the AppImage:"
echo -e "${GREEN}chmod +x Dasi-${VERSION}-${ARCH}.AppImage"
echo -e "./Dasi-${VERSION}-${ARCH}.AppImage${NC}"
echo ""
print_status "Or if you have FUSE issues:"
echo -e "${GREEN}./Dasi-${VERSION}-${ARCH}.AppImage --appimage-extract-and-run${NC}"

print_status "The AppImage should have the Dasi icon embedded. If it doesn't appear immediately in your file manager,"
print_status "you may need to clear your icon cache or restart your file manager." 