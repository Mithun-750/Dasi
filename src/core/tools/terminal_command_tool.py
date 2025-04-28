import logging
import subprocess
import shlex
import os
import pwd
import shutil
from typing import Dict, Any, Optional, List
import time
import platform


class TerminalCommandTool:
    """A tool to execute terminal commands safely."""

    def __init__(self):
        """Initialize the terminal command tool."""
        self.allowed_commands = self._get_allowed_commands()
        self.default_shell = self._detect_default_shell()
        self.user_home = os.path.expanduser("~")
        logging.info(
            f"TerminalCommandTool initialized with default shell: {self.default_shell}")

    def _get_allowed_commands(self) -> List[str]:
        """Get list of allowed commands for security."""
        # Safe commands that don't pose significant security risks
        # This list can be expanded based on requirements
        return [
            "ls", "dir", "pwd", "echo", "cat", "head", "tail", "grep", "find",
            "date", "whoami", "uptime", "df", "du", "free", "ps", "top",
            "uname", "hostname", "ping", "ip", "ifconfig", "netstat", "curl", "wget",
            "python", "pip", "pnpm", "npm", "node", "git", "fish", "bash", "sh", "zsh"
        ]

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

    def _is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed to run."""
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return False

        base_cmd = os.path.basename(cmd_parts[0])

        # Check if command is in allowed list
        for allowed_cmd in self.allowed_commands:
            if base_cmd == allowed_cmd:
                return True

        return False

    def run(self, command: str, working_dir: Optional[str] = None, timeout: int = 30,
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

        # Validate command
        if not self._is_command_allowed(command):
            cmd_parts = shlex.split(command)
            base_cmd = os.path.basename(
                cmd_parts[0]) if cmd_parts else "unknown"

            return {
                "status": "error",
                "message": f"Command '{base_cmd}' is not allowed for security reasons",
                "stdout": "",
                "stderr": f"Security: Command '{base_cmd}' is not allowed",
                "execution_time": 0,
                "metadata": {
                    "working_dir": actual_working_dir,
                    "shell": actual_shell,
                    "attempted_command": base_cmd
                },
                "data": f"Error: Command '{base_cmd}' is not allowed for security reasons"
            }

        logging.info(
            f"Executing terminal command: {command} in directory: {actual_working_dir} with shell: {actual_shell}")

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
