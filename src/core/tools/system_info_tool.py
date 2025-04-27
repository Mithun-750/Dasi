import logging
import platform
import os
import json
import psutil
from typing import Dict, Any, Optional, List, Type, Callable


class SystemInfoTool:
    """A tool to retrieve system information like OS details, memory usage, etc."""

    def __init__(self):
        """Initialize the SystemInfoTool."""
        logging.info("SystemInfoTool initialized.")
        self._name = "system_info"
        self._description = "Retrieves system information including OS details, memory usage, and CPU information"

    @property
    def name(self) -> str:
        """Get the name of the tool."""
        return self._name

    @property
    def description(self) -> str:
        """Get the description of the tool."""
        return self._description

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this tool.

        Returns:
            A dictionary representing the JSON schema for the tool parameters.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["basic", "memory", "cpu", "all"],
                        "description": "Type of system information to retrieve"
                    }
                },
                "required": []
            }
        }

    def run(self, info_type: str = 'basic') -> Dict[str, Any]:
        """
        Retrieves system information based on the requested type.

        Args:
            info_type: Type of information to retrieve ('basic', 'memory', 'cpu', 'all')

        Returns:
            A dictionary containing the results or an error message.
            Example: {'status': 'success', 'data': {...system info...}}
        """
        logging.info(f"SystemInfoTool run called with info_type={info_type}")

        try:
            # Validate the info_type parameter
            valid_types = ['basic', 'memory', 'cpu', 'all']
            if info_type not in valid_types:
                return {
                    'status': 'error',
                    'message': f"Invalid info_type: {info_type}. Must be one of {valid_types}"
                }

            # Collect requested information
            result = {}

            # Basic system info (always included)
            if info_type in ['basic', 'all']:
                result['system'] = self._get_basic_info()

            # Memory information
            if info_type in ['memory', 'all']:
                result['memory'] = self._get_memory_info()

            # CPU information
            if info_type in ['cpu', 'all']:
                result['cpu'] = self._get_cpu_info()

            # Format the result as a human-readable string
            formatted_data = json.dumps(result, indent=2)

            return {
                'status': 'success',
                'data': f"System Information:\n\n```json\n{formatted_data}\n```"
            }

        except ImportError as e:
            logging.error(f"Required package missing: {e}")
            return {
                'status': 'error',
                'message': f"Required package not installed: {str(e)}. Please install psutil."
            }
        except Exception as e:
            logging.exception(f"Error retrieving system information: {e}")
            return {
                'status': 'error',
                'message': f"Error retrieving system information: {str(e)}"
            }

    def _get_basic_info(self) -> Dict[str, Any]:
        """Get basic system information."""
        return {
            'os': platform.system(),
            'version': platform.version(),
            'platform': platform.platform(),
            'architecture': platform.architecture()[0],
            'machine': platform.machine(),
            'python_version': platform.python_version(),
            'hostname': platform.node()
        }

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        memory = psutil.virtual_memory()
        return {
            'total': f"{memory.total / (1024**3):.2f} GB",
            'available': f"{memory.available / (1024**3):.2f} GB",
            'used': f"{memory.used / (1024**3):.2f} GB",
            'percent': f"{memory.percent}%"
        }

    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information."""
        return {
            'cores_physical': psutil.cpu_count(logical=False),
            'cores_logical': psutil.cpu_count(logical=True),
            'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 'N/A',
            'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else 'N/A',
            'usage_percent': f"{psutil.cpu_percent(interval=0.1)}%"
        }

    @classmethod
    def get_tool_config(cls) -> Dict[str, Any]:
        """
        Get tool configuration for LangChain integration.

        Returns:
            A dictionary with tool configuration including name, description, and schema.
        """
        instance = cls()
        return {
            "name": instance.name,
            "description": instance.description,
            "schema": instance.get_schema()
        }


# Example Usage (for testing purposes, can be removed in production)
if __name__ == '__main__':
    # Setup basic logging for testing
    logging.basicConfig(level=logging.INFO)

    try:
        # Create the tool instance
        system_info_tool = SystemInfoTool()

        # Print tool metadata
        print("\n--- Tool Information ---")
        print(f"Name: {system_info_tool.name}")
        print(f"Description: {system_info_tool.description}")
        print(f"Schema: {json.dumps(system_info_tool.get_schema(), indent=2)}")

        # Test different information types
        print("\n--- Basic System Info ---")
        basic_info = system_info_tool.run('basic')
        print(basic_info.get('data', basic_info.get('message')))

        print("\n--- Memory Info ---")
        memory_info = system_info_tool.run('memory')
        print(memory_info.get('data', memory_info.get('message')))

        print("\n--- CPU Info ---")
        cpu_info = system_info_tool.run('cpu')
        print(cpu_info.get('data', cpu_info.get('message')))

        print("\n--- All Info ---")
        all_info = system_info_tool.run('all')
        print(all_info.get('data', all_info.get('message')))

        print("\n--- Invalid Info Type ---")
        invalid_info = system_info_tool.run('invalid')
        print(invalid_info.get('message'))

    except Exception as e:
        print(f"Error during example usage: {e}")
