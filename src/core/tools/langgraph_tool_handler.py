import asyncio
import logging
from typing import Dict, Any, Optional, List
from langchain_core.tools import BaseTool

from src.core.tools.langgraph_tool_config import get_available_tools
from src.core.tools.langgraph_tool_node import LangGraphToolNode

logger = logging.getLogger(__name__)


class ToolCallHandler:
    """
    Handles the execution of tool calls in the LangGraph system.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {
            tool.name: tool for tool in get_available_tools()
        }
        self._tool_node = LangGraphToolNode()

    async def execute_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call with the given name and arguments.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        if tool_name not in self._tools:
            error_msg = f"Tool '{tool_name}' not found"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg
            }

        try:
            # Process the tool call through the LangGraphToolNode
            result = await self._tool_node.process_tool_call(tool_name, tool_args)
            return result

        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "error": error_msg
            }

    def get_tool_names(self) -> List[str]:
        """Get a list of available tool names."""
        return list(self._tools.keys())

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool instance by name."""
        return self._tools.get(tool_name)
