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
#   2. Make this script executable: chmod +x create_appimage.sh
#   3. Run the script: ./create_appimage.sh
#   4. The AppImage will be created in the current directory
#
# The final AppImage can be run directly:
#   ./Dasi-x.y.z-x86_64.AppImage
#
# Or with the extract-and-run option if FUSE is not available:
#   ./Dasi-x.y.z-x86_64.AppImage --appimage-extract-and-run
# =============================================================================

set -e

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

print_status "Starting AppImage creation process..."

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf AppDir || true
rm -rf Dasi-*.AppImage || true

# Create AppDir structure
print_status "Creating AppDir structure..."
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p AppDir/usr/lib/python3.10/site-packages

# Copy application files
print_status "Copying application files..."
cp -r src AppDir/usr/
cp LICENSE AppDir/usr/
cp README.md AppDir/usr/
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
if [ -f "src/assets/Dasi.png" ]; then
    cp src/assets/Dasi.png AppDir/dasi.png
    cp src/assets/Dasi.png AppDir/usr/share/icons/hicolor/256x256/apps/dasi.png
    print_success "Icon set successfully"
else
    print_warning "Icon file not found at src/assets/Dasi.png"
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

# Run the application with verbose output for easier debugging
exec "${HERE}/usr/bin/python3" -v "${HERE}/usr/src/main.py" "$@"
EOF

chmod +x AppDir/AppRun
print_success "AppRun script created"

# Download appimagetool
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    print_status "Downloading appimagetool..."
    wget -c "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
    print_success "Downloaded appimagetool"
else
    print_status "Using existing appimagetool"
fi

# Build the AppImage
print_status "Building AppImage..."
VERSION=$(grep -oP '(?<=version = ").*(?=")' pyproject.toml)
ARCH=$(uname -m)
./appimagetool-x86_64.AppImage AppDir "Dasi-${VERSION}-${ARCH}.AppImage"

print_success "AppImage created successfully!"
ls -la Dasi-*.AppImage

print_status "To run the AppImage:"
echo -e "${GREEN}chmod +x Dasi-${VERSION}-${ARCH}.AppImage"
echo -e "./Dasi-${VERSION}-${ARCH}.AppImage${NC}"
echo ""
print_status "Or if you have FUSE issues:"
echo -e "${GREEN}./Dasi-${VERSION}-${ARCH}.AppImage --appimage-extract-and-run${NC}" 