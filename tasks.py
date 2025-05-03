from invoke import task
import os
import shutil


@task
def dev(c):
    """Run the development version of Dasi"""
    c.run("uv run src/main.py")


@task
def install(c):
    """Install project dependencies"""
    c.run("uv pip install -e .")


@task
def sync(c):
    """Sync project dependencies"""
    c.run("uv sync")


@task
def build(c):
    """Build the application"""
    c.run("uv run scripts/installer.py install")


@task
def load_defaults(c):
    """Copy default configuration files to user config directory."""
    print("Loading default configurations...")

    home_dir = os.path.expanduser("~")
    user_config_base = os.path.join(home_dir, ".config", "dasi")
    user_tools_config_dir = os.path.join(user_config_base, "config", "tools")

    # Ensure user config directories exist
    os.makedirs(user_tools_config_dir, exist_ok=True)

    # Path to default configurations in the project
    defaults_base = os.path.join(os.path.dirname(__file__), "defaults")
    defaults_tools_dir = os.path.join(defaults_base, "tools")

    # Copy tool configurations
    if os.path.exists(defaults_tools_dir):
        print(f"Checking defaults in {defaults_tools_dir}...")
        for filename in os.listdir(defaults_tools_dir):
            default_file_path = os.path.join(defaults_tools_dir, filename)
            user_file_path = os.path.join(user_tools_config_dir, filename)

            if os.path.isfile(default_file_path):
                # Copy only if the user file doesn't exist, to avoid overwriting user changes
                if not os.path.exists(user_file_path):
                    try:
                        shutil.copy2(default_file_path, user_file_path)
                        print(f"  Copied default config: {filename}")
                    except Exception as e:
                        print(f"  Error copying {filename}: {e}")
                else:
                    print(f"  Skipping existing config: {filename}")
        print("Tool defaults loaded.")
    else:
        print("No default tools directory found.")

    # Add logic here later to copy other defaults (e.g., prompt_chunks) if needed

    print("Default configurations loaded successfully.")


@task
def appimage(c):
    """Build Dasi as an AppImage"""
    # Make the script executable
    c.run("chmod +x scripts/create_appimage.sh")

    # Run the script
    print("Building Dasi AppImage...")
    c.run("./scripts/create_appimage.sh")

    print("\nAppImage created! You can find it in the current directory.")
