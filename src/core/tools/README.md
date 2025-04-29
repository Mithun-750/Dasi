# Dasi Tools System

The Dasi Tools system provides a modular way to extend Dasi's capabilities through user-confirmable tools. Tools are specialized classes that can perform specific tasks and are integrated with Dasi's LLM system to allow AI-driven tool usage with user confirmation.

## Available Tools

### WebSearchTool (`web_search_tool.py`)

Provides web search and link scraping capabilities. Uses the WebSearchHandler to execute searches against various providers (Google Serper, Brave Search, DuckDuckGo, Tavily, Exa).

**Arguments:**
- `query` (string): The search query or context for scraping
- `mode` (string): Either 'web_search' or 'link_scrape'
- `url` (string, optional): Required for 'link_scrape' mode - the URL to scrape
- `selected_text` (string, optional): Additional context from user's selected text

### SystemInfoTool (`system_info_tool.py`)

Provides system information like OS details, memory usage, and CPU information.

**Arguments:**
- `info_type` (string): Type of information to retrieve ('basic', 'memory', 'cpu', 'all')

### TerminalCommandTool (`terminal_command_tool.py`)

Executes terminal commands safely in a background thread, with security restrictions, metadata collection, and proper error handling.

**Arguments:**
- `command` (string): The terminal command to execute
- `working_dir` (string, optional): Working directory for the command (use ~ for home directory)
- `timeout` (integer, optional): Maximum execution time in seconds (default: 30)
- `shell_type` (string, optional): Specific shell to use (bash, fish, zsh, sh)

**Features:**
- Runs commands asynchronously in a background thread to prevent UI freezing
- Validates commands against an allowlist for security
- Automatically detects the user's default shell
- Provides detailed metadata about execution environment
- Handles command timeouts and proper error reporting
- Formats output in a user-friendly way with markdown code blocks

## Architecture

The tool system consists of:

1. **Individual Tool Classes**: Self-contained classes that implement a `run` method
2. **ToolCallHandler**: Manages tool registration, user confirmation, and execution
3. **LangGraphHandler**: Detects tool calls from LLM responses and routes to the appropriate tool
4. **LangGraphToolNode**: Processes tool calls within the LangGraph system, acting as an execution node in the graph
5. **LangGraphToolConfig**: Defines schemas and configurations for tools used with LangGraph

## LangGraph Tool Integration

Dasi uses LangGraph to coordinate the flow of tool usage. The key components are:

### LangGraphToolNode (`langgraph_tool_node.py`)

A specialized node class for the LangGraph system that handles tool execution.

**Features:**
- Asynchronous tool call processing
- JSON-based response formatting
- Proper error handling and logging
- Extensible handler system for different tool types

**Methods:**
- `process_tool_call(tool_name, tool_args)`: Main entry point for tool execution
- Tool-specific handlers (e.g., `_handle_web_search`, `_handle_system_info`)

### LangGraphToolConfig (`langgraph_tool_config.py`)

Provides schemas and configurations for tools used with LangGraph.

**Features:**
- Pydantic models for tool inputs
- Tool descriptions for LLM prompts
- Centralized tool registration

## Creating a New Tool

Follow these steps to create a new tool:

1. Create a new file `your_tool_name_tool.py` in the `src/core/tools/` directory
2. Implement your tool class with a `run` method that returns a structured result
3. Update `tool_call_handler.py` to register and use your tool
4. Add a handler method in `LangGraphToolNode` for your new tool
5. (Optional) Add a Pydantic schema in `LangGraphToolConfig` for your tool's inputs
6. (Optional) Update requirements.txt if your tool requires additional dependencies

### Tool Template

```python
import logging
from typing import Dict, Any, Optional

class YourToolNameTool:
    """Description of your tool's purpose."""

    def __init__(self, optional_dependency=None):
        """Initialize your tool with any dependencies it needs."""
        self.optional_dependency = optional_dependency
        logging.info("YourToolNameTool initialized.")
    
    def run(self, param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute the tool's functionality.
        
        Args:
            param1: First parameter description
            param2: Second parameter description
                
        Returns:
            A dictionary with the following structure:
            - On success: {'status': 'success', 'data': result_data}
            - On failure: {'status': 'error', 'message': error_message}
        """
        logging.info(f"YourToolNameTool run called with: {param1}, {param2}")
        
        try:
            # Your tool implementation here
            result = f"Processed {param1}"
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            logging.exception(f"Error during tool execution: {e}")
            return {
                'status': 'error',
                'message': f"Error: {str(e)}"
            }
```

### LangGraphToolNode Handler

Add a handler for your tool in the `LangGraphToolNode` class:

```python
async def _handle_your_tool(self, args: Dict[str, Any]) -> str:
    """
    Handle your custom tool calls.

    Args:
        args (Dict[str, Any]): Must contain required parameters for your tool

    Returns:
        str: JSON string containing tool results
    """
    # Validate required parameters
    param1 = args.get("param1")
    if not param1:
        raise ValueError("Your tool requires a 'param1' parameter")

    # TODO: Implement actual tool functionality
    return json.dumps({
        "status": "success",
        "data": f"Tool results for: {param1}"
    })
```

Then register it in the `__init__` method:

```python
self._tool_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[str]]] = {
    "web_search": self._handle_web_search,
    "system_info": self._handle_system_info,
    "terminal_command": self._handle_terminal_command,  # Added terminal command tool handler
    "your_tool_name": self._handle_your_tool,  # Add your new tool here
}
```

### Integration with ToolCallHandler

After creating your tool, add it to the `ToolCallHandler` class:

1. Import your tool at the top of `tool_call_handler.py`
2. Initialize it in the constructor or the `setup_tools` method
3. Add a handler for your tool in the `execute_tool_call` method

### LLM Tool Call Format

LLMs can invoke tools using the following formats:

1. Custom marker format: `<<TOOL: tool_name {\"param1\": \"value\", \"param2\": 42}>>`
2. OpenAI function calling format (when using OpenAI or compatible models)
3. Anthropic Tool Use format (when using Claude or compatible models)

## Dependencies

- The WebSearchTool requires the WebSearchHandler from `src/core/web_search_handler.py`
- The SystemInfoTool requires the `psutil` package (add with `uv add psutil`)
- The TerminalCommandTool requires `subprocess`, `shlex`, `pwd` and `shutil` (all standard library)

## Best Practices

1. Make tool interfaces simple and clear
2. Always return structured results in the format `{'status': 'success|error', 'data|message': result}` 
3. Implement proper error handling and logging
4. Ensure your tool can be initialized without crashing the application
5. Document your tool's arguments and return values
6. Add tests for your tool 
7. Use async handlers in `LangGraphToolNode` for potentially long-running operations
8. Return properly formatted JSON strings from tool handlers 
9. For long-running operations, use background threads to prevent UI freezing