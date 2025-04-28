from PyQt6.QtCore import QObject, pyqtSignal
import logging
from typing import Dict, Any, Optional
import uuid
import json
import threading
import time
import os
import psutil
import platform
import socket
from pathlib import Path

# Import the tools
from .web_search_tool import WebSearchTool
from .system_info_tool import SystemInfoTool
from ..web_search_handler import WebSearchHandler


class ToolCallHandler(QObject):
    """
    Handles tool call requests, confirmation, and execution.
    Emits signals to the UI for confirmation and receives user responses.
    """
    # Signal emitted when a tool call requires user confirmation
    # e.g., {"tool": "web_search", "args": {...}}
    tool_call_requested = pyqtSignal(dict)
    # Signal emitted when a tool call is completed (success or failure)
    # e.g., {"tool": "web_search", "result": ...}
    tool_call_completed = pyqtSignal(dict)
    # Signal for when a tool call result is being processed by the LLM
    tool_call_processing = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_tool_call = None
        self.awaiting_confirmation = False
        self.tools = {}  # Dictionary to store tool instances
        self.web_search_handler = None  # Will be set later from the LLM handler
        self.user_response = None
        self.user_response_event = threading.Event()
        logging.info("ToolCallHandler initialized")

    def setup_tools(self, web_search_handler: Optional[WebSearchHandler] = None):
        """
        Set up the available tools.

        Args:
            web_search_handler: Optional WebSearchHandler instance from LangGraphHandler
        """
        # Setup WebSearchTool if handler provided
        if web_search_handler:
            self.web_search_handler = web_search_handler
            self.tools["web_search"] = WebSearchTool(web_search_handler)
            logging.info(
                "WebSearchTool initialized with provided WebSearchHandler")
        else:
            logging.warning(
                "WebSearchHandler not provided, web_search tool unavailable")

        # Setup SystemInfoTool
        try:
            self.tools["system_info"] = SystemInfoTool()
            logging.info("SystemInfoTool initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize SystemInfoTool: {e}")

    def request_tool_call(self, tool_name, args):
        """Request a tool call and emit a signal for UI confirmation."""
        logging.info(f"Tool call requested: {tool_name} with args: {args}")
        self.pending_tool_call = {"tool": tool_name, "args": args}
        self.awaiting_confirmation = True
        # Emit signal to UI - this should trigger the confirmation panel to be shown
        logging.debug("Emitting tool_call_requested signal")
        self.tool_call_requested.emit(self.pending_tool_call)

    def handle_user_response(self, approved: bool):
        """Handle the user's response to the tool call confirmation."""
        if not self.awaiting_confirmation or not self.pending_tool_call:
            logging.warning("No pending tool call to confirm.")
            return

        tool_name = self.pending_tool_call.get("tool", "unknown")
        tool_id = self.pending_tool_call.get("id")  # Get the ID if present

        # Generate a default ID if none exists
        if not tool_id:
            tool_id = f"call_{uuid.uuid4().hex[:24]}"
            self.pending_tool_call["id"] = tool_id

        if approved:
            logging.info(
                f"User accepted tool call: {tool_name} (ID: {tool_id})")
            self.execute_tool_call(self.pending_tool_call)
        else:
            logging.info(
                f"User rejected tool call: {tool_name} (ID: {tool_id})")
            self.tool_call_completed.emit({
                "tool": tool_name,
                "result": "rejected",
                "id": tool_id  # Include ID in the rejection result
            })
        self.awaiting_confirmation = False
        self.pending_tool_call = None

    def execute_tool_call(self, tool_call: Dict[str, Any]):
        """
        Execute a tool call with the appropriate tool instance.

        Args:
            tool_call: Dictionary with 'tool' name and 'args' to pass to the tool
        """
        tool_name = tool_call.get("tool", "")
        args = tool_call.get("args", {})
        tool_id = tool_call.get("id")  # Get the tool call ID

        # Generate an ID if none exists
        if not tool_id:
            tool_id = f"call_{uuid.uuid4().hex[:24]}"

        logging.info(
            f"Executing tool call: {tool_name} with args: {args}, ID: {tool_id}")

        # Check if the tool is initialized
        if tool_name not in self.tools:
            # Lazy initialization for tools
            if tool_name == "web_search" and self.web_search_handler:
                self.tools["web_search"] = WebSearchTool(
                    self.web_search_handler)
                logging.info("WebSearchTool initialized on demand")
            elif tool_name == "system_info":
                try:
                    self.tools["system_info"] = SystemInfoTool()
                    logging.info("SystemInfoTool initialized on demand")
                except Exception as e:
                    logging.error(f"Failed to initialize SystemInfoTool: {e}")
                    self.tool_call_completed.emit({
                        "tool": tool_name,
                        "result": {
                            "status": "error",
                            "message": f"Failed to initialize system info tool: {str(e)}"
                        },
                        "id": tool_id  # Include ID in error result
                    })
                    return
            else:
                logging.error(f"Unknown or unavailable tool: {tool_name}")
                self.tool_call_completed.emit({
                    "tool": tool_name,
                    "result": {
                        "status": "error",
                        "message": f"Unknown tool: {tool_name}"
                    },
                    "id": tool_id  # Include ID in error result
                })
                return

        # Execute web_search tool
        if tool_name == "web_search":
            try:
                # Extract arguments for the tool
                query = args.get('query', '')
                mode = args.get('mode', 'web_search')
                url = args.get('url') if mode == 'link_scrape' else None
                selected_text = args.get('selected_text')

                # Run the tool
                logging.info(
                    f"Calling WebSearchTool with query: '{query}', mode: {mode}")
                result = self.tools["web_search"].run(
                    query=query,
                    mode=mode,
                    url=url,
                    selected_text=selected_text
                )

                # Emit the result with ID
                logging.info(
                    f"Web search completed, emitting result: {result.get('status', 'unknown')}")
                self.tool_call_completed.emit({
                    "tool": tool_name,
                    "result": result,
                    "id": tool_id  # Include the ID in the result
                })

            except Exception as e:
                logging.exception(f"Error executing web_search tool: {e}")
                self.tool_call_completed.emit({
                    "tool": tool_name,
                    "result": {
                        "status": "error",
                        "message": f"Error executing web search: {str(e)}"
                    },
                    "id": tool_id  # Include ID in error result
                })

        # Handle system_info tool
        elif tool_name == "system_info":
            try:
                # Extract the info_type argument or use default
                info_type = args.get('info_type', 'basic')

                # Run the tool
                logging.info(
                    f"Calling SystemInfoTool with info_type: {info_type}")
                result = self.tools["system_info"].run(info_type=info_type)

                # Emit the result with ID
                logging.info(
                    f"System info retrieved, emitting result: {result.get('status', 'unknown')}")
                self.tool_call_completed.emit({
                    "tool": tool_name,
                    "result": result,
                    "id": tool_id  # Include the ID in the result
                })

            except Exception as e:
                logging.exception(f"Error executing system_info tool: {e}")
                self.tool_call_completed.emit({
                    "tool": tool_name,
                    "result": {
                        "status": "error",
                        "message": f"Error retrieving system info: {str(e)}"
                    },
                    "id": tool_id  # Include ID in error result
                })

        # Add other tools here in the future
        # elif tool_name == "another_tool":
        #     ...

        else:
            logging.error(f"Unknown tool: {tool_name}")
            self.tool_call_completed.emit({
                "tool": tool_name,
                "result": {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                },
                "id": tool_id  # Include ID in error result
            })

    def wait_for_user_response(self, timeout=120):
        """Wait for the user to respond to a tool call request."""
        logging.info(f"Waiting for user response (timeout: {timeout}s)")

        if self.user_response_event.wait(timeout):
            return self.user_response
        else:
            logging.warning("Timeout waiting for user response")
            return False

    def process_tool_call_request(self, tool_name, args, tool_id=None):
        """Process a tool call request from start to finish."""
        # Request user confirmation
        self.request_tool_call(tool_name, args)

        # Wait for user response
        approved = self.wait_for_user_response()

        if approved:
            # Execute the tool
            return self.execute_tool_call(self.pending_tool_call)
        else:
            # User rejected the tool call
            result = {
                "tool": tool_name,
                "id": tool_id,
                "result": "rejected"
            }
            self.tool_call_completed.emit(result)
            return result

    def _web_search_tool(self, args):
        """Web search tool implementation."""
        if not self.web_search_handler:
            return {
                "status": "error",
                "message": "Web search handler not configured"
            }

        query = args.get("query", "")
        if not query:
            return {
                "status": "error",
                "message": "No query provided for web search"
            }

        # Execute web search
        try:
            result = self.web_search_handler.execute_search({
                "query": query,
                "mode": args.get("mode", "web_search"),
                "url": args.get("url", ""),
                "context": {
                    "selected_text": args.get("selected_text", "")
                }
            })
            return {
                "status": "success",
                "data": result.get("content", "No results found")
            }
        except Exception as e:
            logging.error(f"Error executing web search: {str(e)}")
            return {
                "status": "error",
                "message": f"Error executing web search: {str(e)}"
            }

    def _system_info_tool(self, args):
        """System info tool implementation."""
        info_type = args.get("info_type", "basic")

        system_info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "hostname": socket.gethostname(),
            "python_version": platform.python_version()
        }

        if info_type in ["memory", "all"]:
            memory = psutil.virtual_memory()
            system_info["memory"] = {
                "total": f"{memory.total / (1024**3):.2f} GB",
                "available": f"{memory.available / (1024**3):.2f} GB",
                "used": f"{memory.used / (1024**3):.2f} GB",
                "percent": f"{memory.percent}%"
            }

        if info_type in ["cpu", "all"]:
            system_info["cpu"] = {
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "current_usage": f"{psutil.cpu_percent(interval=0.5)}%"
            }

        # Format system info as markdown
        markdown = "# System Information\n\n"

        # Basic info section
        markdown += "## Basic Information\n"
        markdown += f"- **OS**: {system_info['os']} {system_info['os_version']}\n"
        markdown += f"- **Hostname**: {system_info['hostname']}\n"
        markdown += f"- **Python Version**: {system_info['python_version']}\n\n"

        # Memory section if available
        if "memory" in system_info:
            markdown += "## Memory\n"
            markdown += f"- **Total**: {system_info['memory']['total']}\n"
            markdown += f"- **Available**: {system_info['memory']['available']}\n"
            markdown += f"- **Used**: {system_info['memory']['used']}\n"
            markdown += f"- **Usage**: {system_info['memory']['percent']}\n\n"

        # CPU section if available
        if "cpu" in system_info:
            markdown += "## CPU\n"
            markdown += f"- **Physical Cores**: {system_info['cpu']['cores_physical']}\n"
            markdown += f"- **Logical Cores**: {system_info['cpu']['cores_logical']}\n"
            markdown += f"- **Current Usage**: {system_info['cpu']['current_usage']}\n\n"

        return {
            "status": "success",
            "data": markdown
        }

    def get_tool_description(self, tool_name):
        """Get the description of a tool by name."""
        tool = self.get_tool(tool_name)
        if tool:
            if hasattr(tool, 'description'):
                return tool.description
            elif hasattr(tool, 'name') and hasattr(tool, 'description_for_model'):
                return tool.description_for_model
        return f"Tool: {tool_name}"

    def get_tools(self):
        """Get all available tools."""
        return list(self.tools.values())
