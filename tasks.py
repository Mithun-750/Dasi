from invoke import task


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
def appimage(c):
    """Build Dasi as an AppImage"""
    # Make the script executable
    c.run("chmod +x scripts/create_appimage.sh")

    # Run the script
    print("Building Dasi AppImage...")
    c.run("./scripts/create_appimage.sh")

    print("\nAppImage created! You can find it in the current directory.")
