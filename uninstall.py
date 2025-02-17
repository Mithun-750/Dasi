#!/usr/bin/env python3
import os
import shutil
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

def remove_shortcut():
    """Remove platform-specific shortcut/launcher."""
    if is_linux():
        desktop_file = os.path.join(get_desktop_dir(), "dasi.desktop")
        if os.path.exists(desktop_file):
            os.remove(desktop_file)
    
    elif is_macos():
        app_bundle = os.path.join(get_desktop_dir(), "Dasi.app")
        if os.path.exists(app_bundle):
            shutil.rmtree(app_bundle)
    
    else:  # Windows
        shortcut_path = os.path.join(get_desktop_dir(), "Dasi.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)

def main():
    print("Uninstalling Dasi...")

    # Remove shortcut/launcher
    remove_shortcut()

    # Remove config directory
    config_dir = get_config_dir()
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)

    # Remove build artifacts
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists(".venv"):
        shutil.rmtree(".venv")

    print("\nUninstall complete!")
    print("Note: The source code directory has not been removed.")

if __name__ == "__main__":
    main() 