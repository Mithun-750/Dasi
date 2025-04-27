from typing import Dict, Any, List, Optional
from langchain_core.tools import BaseTool
from langchain_core.pydantic_v1 import BaseModel, Field


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""
    query: str = Field(..., description="The search query to look up")


class SystemInfoInput(BaseModel):
    """Input schema for system info tool."""
    info_type: str = Field(...,
                           description="Type of system information to retrieve")


class WebSearchTool(BaseTool):
    """Tool for performing web searches."""
    name = "web_search"
    description = "Search the web for information about a topic"
    args_schema = WebSearchInput

    def _run(self, query: str) -> Dict[str, Any]:
        """This method should not be called directly - tool calls are handled by ToolCallHandler"""
        raise NotImplementedError(
            "Tool calls should be handled by ToolCallHandler")


class SystemInfoTool(BaseTool):
    """Tool for retrieving system information."""
    name = "system_info"
    description = "Get information about the system"
    args_schema = SystemInfoInput

    def _run(self, info_type: str) -> Dict[str, Any]:
        """This method should not be called directly - tool calls are handled by ToolCallHandler"""
        raise NotImplementedError(
            "Tool calls should be handled by ToolCallHandler")


def get_available_tools() -> List[BaseTool]:
    """
    Get a list of all available tools for use with LangGraph.

    Returns:
        List of tool instances
    """
    return [
        WebSearchTool(),
        SystemInfoTool()
    ]


def get_tool_descriptions() -> List[Dict[str, str]]:
    """
    Get descriptions of all available tools in a format suitable for LLM prompts.

    Returns:
        List of tool descriptions
    """
    tools = get_available_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": str(tool.args_schema.schema())
        }
        for tool in tools
    ]
