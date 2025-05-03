import logging
import subprocess
import shlex
import os
import pwd
import shutil
import re
import json
from typing import Dict, Any, Optional, List
import time
import platform


class TerminalCommandTool:
    """A tool to execute terminal commands safely."""

    def __init__(self):
        """Initialize the terminal command tool."""
        self.blocked_patterns = []
        self.default_shell = self._detect_default_shell()
        self.user_home = os.path.expanduser("~")

        # Load tool configuration from file
        self.config = self._load_config()
        self._setup_blocklist()

        logging.info(
            f"TerminalCommandTool initialized with default shell: {self.default_shell}")
        if self.blocked_patterns:
            logging.info(
                f"Loaded {len(self.blocked_patterns)} blocked command patterns.")
        else:
            logging.info("No blocked command patterns loaded.")

    def _load_config(self) -> Dict[str, Any]:
        """Load tool configuration from file."""
        config = {}

        # User config path (following XDG guidelines)
        user_config_dir = os.path.join(os.path.expanduser(
            "~"), ".config", "dasi", "config", "tools")
        config_path = os.path.join(
            user_config_dir, "terminal_tool_config.json")

        # Legacy config path (for backward compatibility)
        legacy_config_path = os.path.join(os.path.expanduser(
            "~"), ".dasi", "config", "tools", "terminal_tool_config.json")

        # Application default config path
        app_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))))
        app_config_path = os.path.join(
            app_dir, "defaults", "tools", "terminal_tool_config.json")

        try:
            # Try user config first
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    logging.info(
                        f"Loaded terminal tool config from {config_path}")
            # Then try legacy user config
            elif os.path.exists(legacy_config_path):
                with open(legacy_config_path, 'r') as f:
                    config = json.load(f)
                    logging.info(
                        f"Loaded terminal tool config from legacy path {legacy_config_path}")
                    # Consider migrating or notifying the user
            # Fall back to application default
            elif os.path.exists(app_config_path):
                with open(app_config_path, 'r') as f:
                    config = json.load(f)
                    logging.info(
                        f"Loaded default terminal tool config from {app_config_path}")
            else:
                logging.warning(
                    "No terminal tool configuration found, using internal defaults.")
        except Exception as e:
            logging.error(f"Error loading terminal tool configuration: {e}")

        return config

    def _setup_blocklist(self):
        """Set up blocklist patterns from configuration."""
        self.blocked_patterns = []

        if not self.config or 'blocklist' not in self.config:
            # Legacy behavior - read from file
            self._load_blocked_patterns_from_file()
            return

        blocklist_config = self.config.get('blocklist', {})

        # Check if blocklist is enabled
        if not blocklist_config.get('blocklist_enabled', True):
            logging.info(
                "Terminal command blocklist is disabled in configuration.")
            return

        # Process patterns from config
        for pattern_config in blocklist_config.get('patterns', []):
            if not pattern_config.get('enabled', True):
                continue

            pattern = pattern_config.get('pattern', '')
            description = pattern_config.get('description', '')

            if pattern:
                try:
                    self.blocked_patterns.append(re.compile(pattern))
                    logging.debug(
                        f"Added blocked pattern: '{pattern}' - {description}")
                except re.error as e:
                    logging.error(
                        f"Invalid regex pattern in blocklist: '{pattern}'. Error: {e}")

    def _load_blocked_patterns_from_file(self) -> None:
        """Legacy method to load blocked command patterns from the text file."""
        blocklist_file = os.path.join(
            os.path.dirname(__file__), 'terminal_blocklist.txt')
        if not os.path.exists(blocklist_file):
            logging.warning(f"Blocklist file not found: {blocklist_file}")
            return

        try:
            with open(blocklist_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Ignore empty lines and comments
                    if line and not line.startswith('#'):
                        try:
                            self.blocked_patterns.append(re.compile(line))
                        except re.error as e:
                            logging.error(
                                f"Invalid regex pattern in blocklist '{blocklist_file}': '{line}'. Error: {e}")
        except Exception as e:
            logging.error(
                f"Error reading blocklist file '{blocklist_file}': {e}")

    def _detect_default_shell(self) -> str:
        """Detect the user's default shell."""
        try:
            # Try to get the current user's shell from /etc/passwd
            if platform.system() != "Windows":
                username = os.getlogin()
                shell = pwd.getpwnam(username).pw_shell
                return shell
            else:
                # On Windows, default to cmd.exe
                return "cmd.exe"
        except Exception as e:
            logging.warning(f"Could not detect default shell: {e}")
            # Fallback to system default
            return "/bin/sh" if platform.system() != "Windows" else "cmd.exe"

    def run(self, command: str, working_dir: Optional[str] = None, timeout: Optional[int] = None,
            shell_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a terminal command safely.

        Args:
            command: The command to execute
            working_dir: Optional working directory for the command
            timeout: Maximum execution time in seconds
            shell_type: Specific shell to use (bash, fish, zsh, sh)

        Returns:
            Dictionary with status, stdout, stderr, and execution time
        """
        start_time = time.time()

        # Use configured timeout if not specified
        if timeout is None:
            timeout = self.config.get(
                'execution', {}).get('default_timeout', 30)

        # Determine the actual working directory
        if working_dir is None:
            # Use current directory by default
            actual_working_dir = os.getcwd()
        elif working_dir == "~" or working_dir == "$HOME":
            # Expand user home directory
            actual_working_dir = self.user_home
        else:
            # Use specified directory
            actual_working_dir = os.path.abspath(
                os.path.expanduser(working_dir))

        # Verify that the directory exists
        if not os.path.isdir(actual_working_dir):
            return {
                "status": "error",
                "message": f"Working directory '{actual_working_dir}' does not exist",
                "stdout": "",
                "stderr": f"Directory not found: {actual_working_dir}",
                "execution_time": 0,
                "data": f"Error: Working directory '{actual_working_dir}' does not exist"
            }

        # Determine which shell to use
        actual_shell = None
        if shell_type:
            if shell_type in ["bash", "sh", "fish", "zsh"]:
                shell_path = shutil.which(shell_type)
                if shell_path:
                    actual_shell = shell_path
                else:
                    logging.warning(
                        f"Requested shell {shell_type} not found, using default")
                    actual_shell = self.default_shell
            else:
                logging.warning(
                    f"Unsupported shell type: {shell_type}, using default")
                actual_shell = self.default_shell
        else:
            actual_shell = self.default_shell

        if not command or not isinstance(command, str):
            return {
                "status": "error",
                "message": "Command must be a non-empty string",
                "stdout": "",
                "stderr": "Invalid command format",
                "execution_time": 0,
                "metadata": {
                    "working_dir": actual_working_dir,
                    "shell": actual_shell
                },
                "data": "Error: Command must be a non-empty string"
            }

        logging.info(
            f"Executing terminal command: {command} in directory: {actual_working_dir} with shell: {actual_shell}")

        # Check against blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.search(command):
                logging.warning(
                    f"Blocked execution of command matching pattern: {pattern.pattern}. Command: '{command}'")
                return {
                    "status": "error",
                    "message": f"Command pattern is blocked for security reasons.",
                    "stdout": "",
                    "stderr": f"Security: Command pattern '{pattern.pattern}' is blocked.",
                    "execution_time": 0,
                    "metadata": {
                        "working_dir": actual_working_dir,
                        "shell": actual_shell,
                        "attempted_command": command,
                        "blocked_pattern": pattern.pattern
                    },
                    "data": f"Error: Command pattern '{pattern.pattern}' is blocked for security reasons."
                }

        try:
            # Create environment with PATH to find commands
            env = os.environ.copy()

            # Prepare the command
            if actual_shell in ["/bin/fish", "/usr/bin/fish"]:
                # Special handling for fish shell
                full_command = [actual_shell, "-c", command]
                use_shell = False
            elif actual_shell in ["/bin/bash", "/usr/bin/bash", "/bin/zsh", "/usr/bin/zsh"]:
                # For bash/zsh, use the -c option
                full_command = [actual_shell, "-c", command]
                use_shell = False
            else:
                # Default approach
                full_command = command
                use_shell = True

            # Run the command
            process = subprocess.Popen(
                full_command,
                shell=use_shell,  # Use shell based on our determination
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=actual_working_dir,
                env=env
            )

            # Wait for the command to complete with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
                execution_time = time.time() - start_time

                # Format result
                result = {
                    "status": "success" if exit_code == 0 else "error",
                    "exit_code": exit_code,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "execution_time": round(execution_time, 2),
                    "metadata": {
                        "working_dir": actual_working_dir,
                        "shell": actual_shell,
                        "command": command
                    }
                }

                if exit_code != 0:
                    result["message"] = f"Command failed with exit code {exit_code}"

                logging.info(
                    f"Terminal command completed with exit code {exit_code} in {execution_time:.2f}s")

                # Add data field for compatibility with other tools
                # Include metadata in the formatted response
                metadata_info = f"Directory: {actual_working_dir}\nShell: {os.path.basename(actual_shell)}\nCommand: {command}\n\n"

                if stdout.strip():
                    result["data"] = f"{metadata_info}```\n{stdout.strip()}\n```"
                else:
                    result["data"] = f"{metadata_info}(Command executed with no output)"

                if stderr.strip():
                    result["data"] += f"\n\nErrors:\n```\n{stderr.strip()}\n```"

                return result

            except subprocess.TimeoutExpired:
                # Kill the process if it times out
                process.kill()
                stdout, stderr = process.communicate()

                return {
                    "status": "error",
                    "message": f"Command timed out after {timeout} seconds",
                    "stdout": stdout.strip() if stdout else "",
                    "stderr": stderr.strip() if stderr else "Execution timed out",
                    "execution_time": timeout,
                    "metadata": {
                        "working_dir": actual_working_dir,
                        "shell": actual_shell,
                        "command": command
                    },
                    "data": f"Error: Command timed out after {timeout} seconds"
                }

        except Exception as e:
            logging.exception(f"Error executing terminal command: {e}")
            return {
                "status": "error",
                "message": f"Failed to execute command: {str(e)}",
                "stdout": "",
                "stderr": str(e),
                "execution_time": time.time() - start_time,
                "metadata": {
                    "working_dir": actual_working_dir,
                    "shell": actual_shell,
                    "command": command
                },
                "data": f"Error: {str(e)}"
            }

    def reload_config(self):
        """Reload configuration from disk at runtime."""
        logging.info("Reloading terminal command tool configuration")
        old_pattern_count = len(self.blocked_patterns)
        self.config = self._load_config()
        self._setup_blocklist()
        new_pattern_count = len(self.blocked_patterns)
        logging.info(
            f"Configuration reloaded: patterns changed from {old_pattern_count} to {new_pattern_count}")
        return True
