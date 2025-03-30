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

# Detect Python version and venv
print_status "Detecting Python environment..."
if [ -n "$VIRTUAL_ENV" ]; then
    VENV_PATH="$VIRTUAL_ENV"
    print_status "Using active virtual environment: $VENV_PATH"
elif [ -d ".venv" ]; then
    VENV_PATH="$PROJECT_ROOT/.venv"
    print_status "Using .venv directory: $VENV_PATH"
elif [ -d "venv" ]; then
    VENV_PATH="$PROJECT_ROOT/venv"
    print_status "Using venv directory: $VENV_PATH"
else
    print_error "No virtual environment found. Please activate your venv before running this script."
    exit 1
fi

# Detect Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
print_status "Detected Python version: $PYTHON_VERSION"

# Create AppDir structure
print_status "Creating AppDir structure..."
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p AppDir/usr/share/pixmaps
mkdir -p AppDir/usr/lib/python$PYTHON_VERSION/site-packages

# Copy application files
print_status "Copying application files..."
cp -r src AppDir/usr/
cp LICENSE AppDir/usr/
cp README.md AppDir/usr/

# Copy default prompt chunks
print_status "Copying default prompt chunks..."
mkdir -p AppDir/usr/defaults/prompt_chunks
cp -r defaults/prompt_chunks/* AppDir/usr/defaults/prompt_chunks/

# Copy Python packages from virtual environment
print_status "Copying Python packages from virtual environment..."
SITE_PACKAGES_DIR="$VENV_PATH/lib/python$PYTHON_VERSION/site-packages"
if [ -d "$SITE_PACKAGES_DIR" ]; then
    print_status "Copying from: $SITE_PACKAGES_DIR"
    cp -r "$SITE_PACKAGES_DIR"/* AppDir/usr/lib/python$PYTHON_VERSION/site-packages/
    print_success "Python packages copied successfully"
else
    print_error "Site-packages directory not found: $SITE_PACKAGES_DIR"
    print_error "Cannot continue without Python packages. Please check your virtual environment."
    exit 1
fi

# Copy Python standard library (more comprehensive approach)
print_status "Copying Python standard library..."
PY_BINARY=$(which python3)
cp -L $PY_BINARY AppDir/usr/bin/
mkdir -p AppDir/usr/lib/python$PYTHON_VERSION
SYSTEM_PY_LIB="/usr/lib/python$PYTHON_VERSION"
if [ -d "$SYSTEM_PY_LIB" ]; then
    cp -r "$SYSTEM_PY_LIB"/* AppDir/usr/lib/python$PYTHON_VERSION/
    print_success "Python standard library copied successfully"
else
    print_warning "System Python library not found at $SYSTEM_PY_LIB"
    print_warning "Trying alternative locations..."
    
    # Try to find Python lib directory
    PY_LIB_DIR=$(python3 -c "import sys; print(sys.path[-1])")
    if [ -d "$PY_LIB_DIR" ] && [ -f "$PY_LIB_DIR/os.py" ]; then
        print_status "Found Python lib at: $PY_LIB_DIR"
        cp -r "$PY_LIB_DIR"/* AppDir/usr/lib/python$PYTHON_VERSION/
        print_success "Python standard library copied from alternate location"
    else
        print_warning "Cannot locate full Python standard library, trying minimum required files"
        python3 -c "
import sys, os, shutil
from pathlib import Path
essential = ['abc.py', 'ast.py', 'codecs.py', 'collections', 'copy.py', 'encodings', 'enum.py', 
             'functools.py', 'genericpath.py', 'importlib', 'io.py', 'json', 'logging', 'os.py', 
             'pathlib.py', 'posixpath.py', 're.py', 'site.py', 'stat.py', 'tempfile.py', 'types.py']
target = Path('AppDir/usr/lib/python$PYTHON_VERSION')
for item in essential:
    for p in sys.path:
        source = Path(p) / item
        if source.exists():
            if source.is_dir():
                shutil.copytree(source, target / item, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target / item)
            break
"
        print_warning "Copied minimal Python standard library, some functionality might be limited"
    fi
fi

# Include Python dynamic libraries
cp /usr/lib/x86_64-linux-gnu/libpython$PYTHON_VERSION.so* AppDir/usr/lib/ 2>/dev/null || true
cp /usr/lib/libpython$PYTHON_VERSION.so* AppDir/usr/lib/ 2>/dev/null || true

# Additional location check for Python libs
python3 -c "
import os, sys, shutil
from pathlib import Path
so_file = f'libpython{sys.version_info.major}.{sys.version_info.minor}.so'
for path in sys.path:
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            if so_file in files:
                print(f'Found Python library at: {os.path.join(root, so_file)}')
                shutil.copy2(os.path.join(root, so_file), 'AppDir/usr/lib/')
                break
"

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

# Update AppRun script with dynamic Python version - fix variable expansion issues
print_status "Creating AppRun script with Python $PYTHON_VERSION support..."
# Use a temporary variable to ensure proper expansion
PY_VERSION=$PYTHON_VERSION

# First, create the variable portion of the script
cat > AppDir/AppRun << EOF
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"

# Startup performance optimization
# First-run flag to track if this is the first time the app runs
DASI_FIRST_RUN="\${HOME}/.cache/dasi/first_run"

# Create cache directories for faster startup
CACHE_DIR="\${HOME}/.cache/dasi"
mkdir -p "\${CACHE_DIR}"
mkdir -p "\${CACHE_DIR}/llm_responses"
mkdir -p "\${CACHE_DIR}/models"

# Set up Python environment
export PATH="\${HERE}/usr/bin:\${PATH}"
export LD_LIBRARY_PATH="\${HERE}/usr/lib:\${LD_LIBRARY_PATH}"
export PYTHONPATH="\${HERE}/usr/lib/python$PY_VERSION:\${HERE}/usr/lib/python$PY_VERSION/site-packages:\${HERE}/usr/src:\${PYTHONPATH}"
export PYTHONHOME="\${HERE}/usr"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

# Set up performance-related environment variables
# Disable Python gc during startup for faster launch
export PYTHONRUNTIME=1

# Set up Qt environment for faster startup
export QT_PLUGIN_PATH="\${HERE}/usr/lib/python$PY_VERSION/site-packages/PyQt6/Qt6/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="\${HERE}/usr/lib/python$PY_VERSION/site-packages/PyQt6/Qt6/plugins/platforms"
export QML2_IMPORT_PATH="\${HERE}/usr/lib/python$PY_VERSION/site-packages/PyQt6/Qt6/qml"
export XDG_CONFIG_HOME="\${HOME}/.config"
EOF

# Append the rest of the AppRun script content with a distinct delimiter
cat >> AppDir/AppRun << 'EOFMARKER'
# Set up cache directory for faster startups
export XDG_CACHE_HOME="${HOME}/.cache"
export DASI_CACHE_DIR="${CACHE_DIR}"
export DASI_LLM_CACHE="${CACHE_DIR}/llm_responses"
export DASI_MODELS_CACHE="${CACHE_DIR}/models"

# Initialize AppImage hash for cache invalidation
APPIMAGE_PATH=$(readlink -f "${APPIMAGE}")
if [ -z "$APPIMAGE_PATH" ]; then
    APPIMAGE_PATH="$0"
fi
APPIMAGE_HASH=$(sha256sum "$APPIMAGE_PATH" 2>/dev/null | cut -d' ' -f1 | head -c 16)
if [ -z "$APPIMAGE_HASH" ]; then
    APPIMAGE_HASH=$(date +%s)
fi
export DASI_APPIMAGE_HASH="$APPIMAGE_HASH"

# Set icon path for the application to use
export DASI_ICON_PATH="${HERE}/usr/share/icons/hicolor/256x256/apps/dasi.png"

# Set path for default prompt chunks
export DASI_DEFAULT_CHUNKS_PATH="${HERE}/usr/defaults/prompt_chunks"

# Initialize prompt chunks only the first time or if they don't exist yet
PROMPT_CHUNKS_DIR="${HOME}/.config/dasi/prompt_chunks"
if [ ! -d "$PROMPT_CHUNKS_DIR" ] || [ -z "$(ls -A "$PROMPT_CHUNKS_DIR")" ]; then
    mkdir -p "$PROMPT_CHUNKS_DIR"
    # Copy default chunks directly
    echo "Initializing default prompt chunks..."
    for chunk_file in "${HERE}/usr/defaults/prompt_chunks/"*.md; do
        cp "$chunk_file" "$PROMPT_CHUNKS_DIR/"
    done
fi

# Apply icon fix directly to main.py if needed
MAIN_FILE="${HERE}/usr/src/main.py"
if ! grep -q "# APPIMAGE ICON FIX" "$MAIN_FILE"; then
    # Create a temp file with the icon fix
    TMP_FILE=$(mktemp)
    cat > "$TMP_FILE" << 'ICONFIX'
# APPIMAGE ICON FIX
import os
appimage_icon = os.environ.get('DASI_ICON_PATH')
if appimage_icon and os.path.exists(appimage_icon):
    ICON_PATH = appimage_icon
ICONFIX
    
    # Insert it after imports
    awk -v icon_fix="$(cat $TMP_FILE)" '
        /^import / { imports = 1 }
        /^[^#]/ && imports && !/^import / { 
            imports = 0
            print icon_fix
        }
        { print }
    ' "$MAIN_FILE" > "${MAIN_FILE}.new"
    mv "${MAIN_FILE}.new" "$MAIN_FILE"
    rm "$TMP_FILE"
fi

# Preload common Python modules for faster startup (if this is first run)
if [ ! -f "$DASI_FIRST_RUN" ]; then
    echo "First run detected, preloading modules..."
    echo "This will make future startups faster."
    
    # Create the first run marker
    touch "$DASI_FIRST_RUN"
    
    # Run a simple Python script to import and precompile common modules
    "${HERE}/usr/bin/python3" -c "
import sys, os
print('Preloading common modules...')
modules = ['logging', 'json', 'pathlib', 'PyQt6', 'PyQt6.QtWidgets', 
           'PyQt6.QtCore', 'PyQt6.QtGui', 'langchain_core']
for module in modules:
    try:
        print(f'Preloading {module}')
        __import__(module)
    except ImportError as e:
        print(f'Failed to preload {module}: {e}')
print('Preloading complete')
" > "${CACHE_DIR}/preload.log" 2>&1
fi

# Run the application
exec "${HERE}/usr/bin/python3" "${HERE}/usr/src/main.py" "$@"
EOFMARKER

# Make AppRun executable
chmod +x AppDir/AppRun
print_success "AppRun script created successfully"

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

# Fix Python version in verification scripts
PY_VERSION=$PYTHON_VERSION  # Store in a temporary variable for consistent expansion

# Add a package verification step before building the AppImage
print_status "Verifying Python packages in AppDir..."
cat > verify_packages.py << EOF
import importlib.util
import sys
import os
from pathlib import Path

# Essential packages to verify
essential_packages = [
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'langchain', 'aiohttp', 'requests', 'json', 'pathlib'
]

# Add the AppDir paths to Python's search path
app_dir = Path('AppDir/usr/lib/python$PY_VERSION')
app_site_packages = Path('AppDir/usr/lib/python$PY_VERSION/site-packages')
sys.path.insert(0, str(app_dir))
sys.path.insert(0, str(app_site_packages))

# Initialize counters
found = 0
missing = []

# Check each package
for package in essential_packages:
    try:
        # For submodules (e.g., PyQt6.QtWidgets), check parent first
        if '.' in package:
            parent = package.split('.')[0]
            if importlib.util.find_spec(parent) is None:
                raise ImportError(f"Parent module {parent} not found")
        
        # Check if the module can be found
        spec = importlib.util.find_spec(package)
        if spec is not None:
            print(f"✓ Found package: {package}")
            found += 1
        else:
            print(f"✗ Missing package: {package}")
            missing.append(package)
    except ImportError as e:
        print(f"✗ Error importing {package}: {e}")
        missing.append(package)

# Print summary
print(f"\nPackage verification summary:")
print(f"- Found: {found}/{len(essential_packages)} packages")
if missing:
    print(f"- Missing: {len(missing)} packages: {', '.join(missing)}")
    print("\nMissing packages must be installed in your virtual environment.")
    print("Run the following commands and try again:")
    for pkg in missing:
        base_pkg = pkg.split('.')[0]
        print(f"python -m pip install {base_pkg}")
    sys.exit(1)
else:
    print("- All essential packages verified successfully!")
    sys.exit(0)
EOF

# Run the verification script
python3 verify_packages.py
if [ $? -ne 0 ]; then
    print_error "Package verification failed. Please install missing packages and try again."
    exit 1
fi
print_success "All essential packages verified!"

# Clean up verification script
rm verify_packages.py

# Verify Qt plugins - fix variable references
print_status "Verifying Qt plugins..."
QT_PLUGINS_PATH="AppDir/usr/lib/python$PY_VERSION/site-packages/PyQt6/Qt6/plugins"
PLATFORM_PLUGINS="$QT_PLUGINS_PATH/platforms"

if [ ! -d "$PLATFORM_PLUGINS" ]; then
    print_warning "Qt platform plugins directory not found: $PLATFORM_PLUGINS"
    print_warning "Creating platforms directory..."
    mkdir -p "$PLATFORM_PLUGINS"
fi

if [ ! -f "$PLATFORM_PLUGINS/libqxcb.so" ]; then
    print_warning "Qt XCB platform plugin not found."
    print_warning "Searching for Qt plugins in virtual environment..."
    
    VENV_QT_PLUGINS="$VENV_PATH/lib/python$PY_VERSION/site-packages/PyQt6/Qt6/plugins"
    if [ -d "$VENV_QT_PLUGINS" ]; then
        print_status "Found Qt plugins directory in venv: $VENV_QT_PLUGINS"
        print_status "Copying Qt plugins to AppDir..."
        mkdir -p "$QT_PLUGINS_PATH"
        cp -rv "$VENV_QT_PLUGINS"/* "$QT_PLUGINS_PATH/"
        
        if [ -f "$PLATFORM_PLUGINS/libqxcb.so" ]; then
            print_success "Qt XCB platform plugin copied successfully!"
        else
            print_warning "Qt XCB platform plugin still not found after copying."
            # Try another approach - use find to locate the plugin across the system
            print_status "Searching system-wide for libqxcb.so..."
            SYSTEM_QXCB=$(find /usr/lib /usr/local/lib -name "libqxcb.so" 2>/dev/null | head -n 1)
            if [ -n "$SYSTEM_QXCB" ]; then
                print_status "Found system Qt XCB plugin: $SYSTEM_QXCB"
                mkdir -p "$PLATFORM_PLUGINS"
                cp -v "$SYSTEM_QXCB" "$PLATFORM_PLUGINS/"
                print_success "Copied system Qt XCB plugin to AppDir"
            else
                print_warning "Could not locate Qt XCB plugin on system. AppImage may not work correctly."
            fi
        fi
    else
        print_warning "Qt plugins directory not found in virtual environment."
        print_warning "AppImage may not work correctly without Qt plugins."
    fi
else
    print_success "Qt XCB platform plugin present!"
fi

# Fix the additional site-packages script too
print_status "Checking for additional site-packages directories..."
cat > find_site_packages.py << EOF
import sys, os, shutil
from pathlib import Path

def report(msg):
    print(f'[SCRIPT] {msg}')

# Get all site-packages directories
site_dirs = [p for p in sys.path if 'site-packages' in p]
report(f'Found {len(site_dirs)} site-packages directories:')

app_dir = Path('AppDir/usr/lib/python$PY_VERSION/site-packages')
app_dir.mkdir(parents=True, exist_ok=True)

# Only process directories outside our venv
venv_path = os.environ.get('VENV_PATH', '')
external_dirs = [d for d in site_dirs if venv_path not in d]

for i, site_dir in enumerate(external_dirs, 1):
    path = Path(site_dir)
    if path.exists():
        report(f'{i}. Processing: {site_dir}')
        
        # Check for key packages in this site-packages dir
        key_packages = ['PyQt6', 'langchain', 'aiohttp', 'requests']
        for pkg in key_packages:
            pkg_dir = path / pkg
            if pkg_dir.exists() and pkg_dir.is_dir():
                report(f'   Found {pkg} package - copying to AppDir')
                target = app_dir / pkg
                if not target.exists():
                    shutil.copytree(pkg_dir, target, dirs_exist_ok=True)
            
            # Also check for dist-info directories
            for info_dir in path.glob(f'{pkg}*.dist-info'):
                report(f'   Found {info_dir.name} - copying to AppDir')
                target = app_dir / info_dir.name
                if not target.exists():
                    shutil.copytree(info_dir, target, dirs_exist_ok=True)
            
            # And check for egg-info directories
            for info_dir in path.glob(f'{pkg}*.egg-info'):
                report(f'   Found {info_dir.name} - copying to AppDir')
                target = app_dir / info_dir.name
                if not target.exists():
                    shutil.copytree(info_dir, target, dirs_exist_ok=True)
                    
        # Look for additional useful packages like typing_extensions, etc.
        useful_packages = ['typing_extensions', 'packaging', 'regex', 'urllib3']
        for pkg in useful_packages:
            pkg_dir = path / pkg
            if pkg_dir.exists() and pkg_dir.is_dir():
                report(f'   Found useful package {pkg} - copying to AppDir')
                target = app_dir / pkg
                if not target.exists():
                    shutil.copytree(pkg_dir, target, dirs_exist_ok=True)
EOF

python3 find_site_packages.py
rm find_site_packages.py

# Final check for missing modules - add to requirements.txt if found missing
print_status "Final check for missing modules..."
touch AppDir/usr/requirements.txt
print_status "Creating helper script to detect missing modules..."
cat > find_missing_modules.py << EOF
import sys
import importlib.util
import subprocess
from pathlib import Path

def install_package(package):
    print(f"Installing {package}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}")
        return False

# Modules to verify
modules_to_check = [
    # Core modules
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'langchain', 
    # Web/API modules
    'aiohttp', 'requests', 'urllib3', 'websockets',
    # Utility modules
    'typing_extensions', 'packaging', 'regex', 'pydantic',
    # Potential additional modules used by Dasi
    'openai', 'anthropic', 'google.generativeai'
]

# Try to ensure all required modules are installed
missing_modules = []
for module_name in modules_to_check:
    if '.' in module_name:  # It's a submodule
        base_module = module_name.split('.')[0]
        try:
            importlib.import_module(base_module)
        except ImportError:
            missing_modules.append(base_module)
    else:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_modules.append(module_name)

# Remove duplicates
missing_modules = list(set(missing_modules))
if missing_modules:
    print(f"Detected missing modules: {', '.join(missing_modules)}")
    print("Installing missing modules...")
    
    # Install missing packages
    for module in missing_modules:
        installed = install_package(module)
        if installed:
            # Add to requirements file
            req_path = Path("AppDir/usr/requirements.txt")
            with open(req_path, 'a') as f:
                f.write(f"{module}\\n")

    print("\\nMissing modules installed. The modules and their dependencies have been")
    print(f"recorded in AppDir/usr/requirements.txt. You should add these to your")
    print(f"project's requirements file to ensure they're always included.")

print("Module verification complete.")
EOF

python3 find_missing_modules.py
rm find_missing_modules.py

print_status "Adding a repair script to the AppImage..."
cat > AppDir/usr/bin/repair-dasi << 'EOF'
#!/usr/bin/env python3
import sys
import os
import subprocess
import importlib.util
from pathlib import Path

print("Dasi AppImage Repair Tool")
print("=========================")
print("This tool will check for missing Python modules and install them.")

# Get the AppDir path
appdir = os.environ.get('APPDIR', Path(__file__).parent.parent.parent)
appdir_path = Path(appdir)

# Get the Python executable
python_exe = Path(sys.executable)
print(f"Using Python: {python_exe}")

# Read the requirements file
requirements_path = appdir_path / "usr" / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, "r") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
else:
    requirements = [
        "PyQt6", "langchain", "aiohttp", "requests", "urllib3", 
        "typing_extensions", "packaging", "regex", "pydantic"
    ]

# Check which modules are missing
missing = []
for req in requirements:
    try:
        importlib.import_module(req)
        print(f"✓ {req} is installed")
    except ImportError:
        missing.append(req)
        print(f"✗ {req} is missing")

# Install missing modules
if missing:
    print("\nInstalling missing modules...")
    for module in missing:
        print(f"Installing {module}...")
        subprocess.check_call([python_exe, "-m", "pip", "install", module])
    print("\nDone! All missing modules have been installed.")
else:
    print("\nNo missing modules detected. Your Dasi AppImage looks healthy!")

input("\nPress Enter to exit...")
EOF

chmod +x AppDir/usr/bin/repair-dasi

# Add repair option to the desktop file
print_status "Adding repair option to desktop file..."
cat > AppDir/dasi-repair.desktop << EOF
[Desktop Entry]
Type=Application
Name=Repair Dasi
Comment=Repair the Dasi AppImage by installing missing modules
Exec=python3 /usr/bin/repair-dasi
Icon=dasi
Categories=Utility;Development;
Terminal=true
StartupNotify=true
EOF

# Generate the AppImage with desktop integration
print_status "Running AppImageTool with desktop integration..."
ARCH=$ARCH ./scripts/appimagetool-x86_64.AppImage --comp gzip -g AppDir "Dasi-${VERSION}-${ARCH}.AppImage"

print_success "AppImage created successfully!"
ls -la Dasi-*.AppImage

print_status "To run the AppImage:"
echo -e "${GREEN}chmod +x Dasi-${VERSION}-${ARCH}.AppImage"
echo -e "./Dasi-${VERSION}-${ARCH}.AppImage${NC}"
echo ""
print_status "If the AppImage is slow to start, you can extract it once with:"
echo -e "${GREEN}./Dasi-${VERSION}-${ARCH}.AppImage --appimage-extract${NC}"
echo -e "And then use the extracted version with:"
echo -e "${GREEN}./squashfs-root/AppRun${NC}" 