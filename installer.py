#!/usr/bin/env python3
"""
Cross-Platform Installer and Uninstaller for Dasi

Usage:
    python installer.py install
    python installer.py uninstall

This script will:
  - Create a Python virtual environment (if needed)
  - Install project dependencies (from requirements.txt and PyInstaller)
  - Build Dasi using PyInstaller (via dasi.spec)
  - Create a system-specific launcher:
       • Linux: creates a desktop entry (~/.local/share/applications/dasi.desktop)
       • Windows: creates a shortcut on the current user's Desktop (requires pywin32)
       • macOS: creates a symlink in /Applications
       
The uninstall command removes the launcher, configuration directory,
and build artifacts (build/ and dist/ folders), while leaving your source code intact.
"""

import sys
import os
import platform
import subprocess
import shutil
import logging

def detect_shell():
    """Detect the current shell being used."""
    shell = os.environ.get('SHELL', '')
    if not shell and platform.system() == 'Windows':
        return 'cmd'
    return os.path.basename(shell)

def get_activate_command():
    """Get the appropriate activate command based on the shell."""
    shell = detect_shell()
    venv_path = os.path.abspath('.venv')
    
    if platform.system() == 'Windows':
        return f"{os.path.join(venv_path, 'Scripts', 'activate')}"
    
    activate_commands = {
        'fish': f"source {os.path.join(venv_path, 'bin', 'activate.fish')}",
        'zsh': f"source {os.path.join(venv_path, 'bin', 'activate')}",
        'bash': f"source {os.path.join(venv_path, 'bin', 'activate')}",
        'sh': f". {os.path.join(venv_path, 'bin', 'activate')}"
    }
    
    return activate_commands.get(shell, f"source {os.path.join(venv_path, 'bin', 'activate')}")

def create_virtualenv():
    if not os.path.exists(".venv"):
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
        
        # Print activation instructions
        activate_cmd = get_activate_command()
        print("\nVirtual environment created!")
        print(f"\nTo activate the virtual environment, run:")
        print(f"    {activate_cmd}")
        print("\nAfter activation, run the installer again:")
        print("    python installer.py install\n")
        sys.exit(0)
    else:
        print("Virtual environment already exists.")

def get_venv_python():
    if platform.system() == "Windows":
        return os.path.join(".venv", "Scripts", "python.exe")
    else:
        return os.path.join(".venv", "bin", "python")

def run_in_venv(args):
    """Run a command in the virtual environment."""
    venv_python = os.path.abspath(get_venv_python())
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment Python not found at {venv_python}")
        sys.exit(1)
    
    # Create a new environment with the virtual environment's Python in PATH
    env = os.environ.copy()
    venv_path = os.path.dirname(venv_python)
    if platform.system() == "Windows":
        env["PATH"] = venv_path + os.pathsep + env.get("PATH", "")
    else:
        env["PATH"] = venv_path + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = os.path.dirname(venv_path)
    
    try:
        subprocess.check_call([venv_python] + args, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error running command in virtual environment: {e}")
        sys.exit(1)

def install_dependencies():
    print("Installing dependencies...")
    run_in_venv(["-m", "pip", "install", "-r", "requirements.txt"])
    run_in_venv(["-m", "pip", "install", "pyinstaller"])
    
    # Optionally, install pywin32 on Windows if creating shortcuts:
    if platform.system() == "Windows":
        try:
            import win32com  # Check if already installed
        except ImportError:
            print("win32com not found. Installing pywin32 for Windows shortcut support...")
            run_in_venv(["-m", "pip", "install", "pywin32"])

def build_dasi():
    print("Building Dasi with PyInstaller...")
    run_in_venv(["-m", "PyInstaller", "dasi.spec", "--clean"])

def create_launcher():
    current_dir = os.getcwd()
    system = platform.system()
    
    if system == "Linux":
        desktop_entry_path = os.path.join(os.path.expanduser("~"), ".local", "share", "applications", "dasi.desktop")
        os.makedirs(os.path.dirname(desktop_entry_path), exist_ok=True)
        executable_path = os.path.join(current_dir, "dist", "dasi", "dasi")
        icon_path = os.path.join(current_dir, "src", "assets", "Dasi.png")
        content = f"""[Desktop Entry]
Version=1.0
Name=Dasi
Comment=Desktop Copilot with LLM Support
Exec={executable_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Utility;Development;
"""
        with open(desktop_entry_path, "w") as f:
            f.write(content)
        os.chmod(desktop_entry_path, 0o755)
        try:
            subprocess.check_call(["update-desktop-database", os.path.dirname(desktop_entry_path)])
        except Exception as e:
            print("Warning: update-desktop-database failed:", e)
        print("Desktop entry created at", desktop_entry_path)
        
    elif system == "Windows":
        try:
            import win32com.client
            desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
            shortcut_path = os.path.join(desktop, "Dasi.lnk")
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            executable_path = os.path.join(current_dir, "dist", "dasi", "dasi.exe")
            shortcut.Targetpath = executable_path
            shortcut.WorkingDirectory = current_dir
            # Use an .ico file if available (you might need to create one)
            icon_path = os.path.join(current_dir, "src", "assets", "Dasi.ico")
            if os.path.exists(icon_path):
                shortcut.IconLocation = icon_path
            shortcut.save()
            print("Shortcut created at", shortcut_path)
        except ImportError:
            print("win32com.client not available. Please install pywin32 to create a Windows shortcut automatically.")
    elif system == "Darwin":
        # macOS: Create a symlink in /Applications
        applications_dir = "/Applications"
        executable_path = os.path.join(current_dir, "dist", "dasi", "dasi")
        link_path = os.path.join(applications_dir, "Dasi")
        try:
            if os.path.exists(link_path):
                os.remove(link_path)
            os.symlink(executable_path, link_path)
            print("Symlink created in /Applications as Dasi")
        except Exception as e:
            print("Failed to create symlink in /Applications. Error:", e)
    else:
        print("Unsupported OS for launcher creation.")

def get_config_directory():
    system = platform.system()
    if system == "Linux":
        return os.path.join(os.path.expanduser("~"), ".config", "dasi")
    elif system == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA"), "dasi")
    elif system == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "dasi")
    else:
        return None

def initialize_prompt_chunks():
    """
    Initialize default prompt chunks in the user's configuration directory.
    Default prompt chunks are copied from the project's "defaults/prompt_chunks" folder.
    """
    # Determine the source directory containing the default prompt chunks
    default_chunks_dir = os.path.join(os.path.dirname(__file__), "defaults", "prompt_chunks")
    if not os.path.exists(default_chunks_dir):
        logging.warning(f"Default prompt chunks directory does not exist: {default_chunks_dir}")
        return

    # Determine the target configuration directory using the helper function
    config_dir = get_config_directory()
    if not config_dir:
        logging.error("Could not determine configuration directory for prompt chunks.")
        return

    # Create the prompt_chunks folder inside the configuration directory if it doesn't exist
    target_chunks_dir = os.path.join(config_dir, "prompt_chunks")
    os.makedirs(target_chunks_dir, exist_ok=True)

    # Copy each default prompt chunk (if it doesn't already exist)
    for file_name in os.listdir(default_chunks_dir):
        src_file = os.path.join(default_chunks_dir, file_name)
        target_file = os.path.join(target_chunks_dir, file_name)
        if not os.path.exists(target_file):
            shutil.copy2(src_file, target_file)
            logging.info(f"Initialized prompt chunk: {file_name}")

def install():
    create_virtualenv()
    install_dependencies()
    build_dasi()
    create_launcher()
    # Auto initialize default prompt chunks
    initialize_prompt_chunks()
    print("Installation complete!")

def remove_launcher():
    current_dir = os.getcwd()
    system = platform.system()
    
    if system == "Linux":
        desktop_entry_path = os.path.join(os.path.expanduser("~"), ".local", "share", "applications", "dasi.desktop")
        if os.path.exists(desktop_entry_path):
            os.remove(desktop_entry_path)
            print("Removed desktop entry at", desktop_entry_path)
    elif system == "Windows":
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        shortcut_path = os.path.join(desktop, "Dasi.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            print("Removed shortcut at", shortcut_path)
    elif system == "Darwin":
        link_path = os.path.join("/Applications", "Dasi")
        if os.path.islink(link_path):
            os.remove(link_path)
            print("Removed symlink at", link_path)
    else:
        print("Unsupported OS for launcher removal.")

def uninstall():
    print("Uninstalling Dasi...")
    remove_launcher()
    
    config_dir = get_config_directory()
    if config_dir and os.path.exists(config_dir):
        shutil.rmtree(config_dir)
        print("Removed configuration directory at", config_dir)
        
    # Remove build artifacts
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print("Removed folder", folder)
            
    print("Uninstall complete!")
    print("Note: The source code and virtual environment have not been removed.")

def main():
    if len(sys.argv) < 2:
        print("Usage: installer.py [install|uninstall]")
        sys.exit(1)
    command = sys.argv[1].lower()
    if command == "install":
        install()
    elif command == "uninstall":
        uninstall()
    else:
        print("Unknown command:", command)
        print("Usage: installer.py [install|uninstall]")
        sys.exit(1)

if __name__ == "__main__":
    main() 