#!/usr/bin/env python3
import os
import sys
import shutil
import venv
import subprocess
import platform
from pathlib import Path

def is_windows():
    return platform.system().lower() == "windows"

def is_macos():
    return platform.system().lower() == "darwin"

def is_linux():
    return platform.system().lower() == "linux"

def get_config_dir():
    """Get the appropriate config directory for the platform."""
    if is_windows():
        return os.path.join(os.environ.get("APPDATA"), "Dasi")
    elif is_macos():
        return os.path.expanduser("~/Library/Application Support/Dasi")
    else:  # Linux and others
        return os.path.expanduser("~/.config/dasi")

def get_desktop_dir():
    """Get the appropriate desktop entry directory for the platform."""
    if is_linux():
        return os.path.expanduser("~/.local/share/applications")
    elif is_macos():
        return os.path.expanduser("~/Applications")
    else:  # Windows
        return os.path.join(os.environ.get("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs")

def create_virtual_environment():
    """Create and activate a virtual environment."""
    print("Creating virtual environment...")
    
    # Check if we're in a virtual environment or Anaconda
    in_venv = sys.prefix != sys.base_prefix
    in_conda = os.path.exists(os.path.join(sys.prefix, 'conda-meta'))
    
    if in_venv or in_conda:
        print("Detected active virtual environment or Anaconda.")
        print("Installing dependencies in current environment...")
        # Install directly in current environment
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return
    
    try:
        # Try creating a new virtual environment
        venv.create(".venv", with_pip=True)
        
        # Get the pip path
        if is_windows():
            pip_path = ".venv/Scripts/pip"
        else:
            pip_path = ".venv/bin/pip"
        
        # Install dependencies
        print("Installing dependencies...")
        subprocess.run([pip_path, "install", "-r", "requirements.txt"])
        subprocess.run([pip_path, "install", "pyinstaller"])
    except Exception as e:
        print(f"Warning: Could not create virtual environment: {str(e)}")
        print("Installing dependencies in current environment instead...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_application():
    """Build the application using PyInstaller."""
    print("Building Dasi...")
    subprocess.run(["pyinstaller", "dasi.spec", "--clean"])

def create_shortcut():
    """Create platform-specific shortcut/launcher."""
    app_path = os.path.abspath("dist/dasi/dasi")
    icon_path = os.path.abspath("src/assets/Dasi.png")
    
    if is_linux():
        desktop_entry = f"""[Desktop Entry]
Version=1.0
Name=Dasi
Comment=Desktop Copilot with LLM Support
Exec={app_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Utility;Development;
"""
        desktop_file = os.path.join(get_desktop_dir(), "dasi.desktop")
        os.makedirs(get_desktop_dir(), exist_ok=True)
        with open(desktop_file, "w") as f:
            f.write(desktop_entry)
        os.chmod(desktop_file, 0o755)

    elif is_macos():
        # Create a simple AppleScript launcher
        app_dir = os.path.join(get_desktop_dir(), "Dasi.app")
        os.makedirs(os.path.join(app_dir, "Contents", "MacOS"), exist_ok=True)
        os.makedirs(os.path.join(app_dir, "Contents", "Resources"), exist_ok=True)
        
        # Copy the icon
        shutil.copy2(icon_path, os.path.join(app_dir, "Contents", "Resources", "Dasi.icns"))
        
        # Create the launcher script
        with open(os.path.join(app_dir, "Contents", "MacOS", "Dasi"), "w") as f:
            f.write(f'#!/bin/bash\nexec "{app_path}"')
        os.chmod(os.path.join(app_dir, "Contents", "MacOS", "Dasi"), 0o755)

    else:  # Windows
        try:
            import winshell
            from win32com.client import Dispatch
            
            shortcut_path = os.path.join(get_desktop_dir(), "Dasi.lnk")
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = app_path
            shortcut.IconLocation = icon_path
            shortcut.save()
        except ImportError:
            print("Note: Could not create Windows shortcut. Please install pywin32 and winshell packages.")

def main():
    try:
        # Create virtual environment and install dependencies
        create_virtual_environment()
        
        # Build the application
        build_application()
        
        # Create platform-specific shortcut
        create_shortcut()
        
        print("\nInstallation complete!")
        print(f"You can find the bundled application in the 'dist/dasi' directory")
        print("A shortcut/launcher has been created in your applications menu.")
        
    except Exception as e:
        print(f"Error during installation: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 