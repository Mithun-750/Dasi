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
    c.run("uv run installer.py install") 