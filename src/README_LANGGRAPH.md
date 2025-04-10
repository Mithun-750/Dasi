# LangGraph Implementation

As of version 1.x, Dasi now exclusively uses the LangGraph implementation for LLM processing. The original `LLMHandler` implementation (`src/llm_handler.py.old`) has been deprecated and is kept only for reference.

## What Changed?

- The old implementation used direct LangChain calls to process user queries
- The new implementation uses a graph-based approach with LangGraph for more flexible processing
- Web search, vision and other capabilities are handled more effectively in the graph-based model
- All functionality is fully compatible with the old implementation

## Benefits of LangGraph

- Better separation of concerns with a state graph model
- More predictable processing flow
- Improved error handling
- Better support for complex capabilities like web search, vision integration, and more
- Easier to extend with new processing steps

## Implementation Details

The main classes involved are:

- `LangGraphHandler` (`src/langgraph_handler.py`) - The LangGraph implementation
- `LLMIntegration` (`src/llm_integration.py`) - A thin wrapper that now only uses LangGraphHandler

The old toggle in settings to switch between implementations has been removed, and the system now always uses LangGraph.

## Original Implementation

If you need to reference the original implementation:

1. See `src/llm_handler.py.old` for the original handler code
2. Understand that `LLMIntegration` used to support both implementations, but now exclusively uses LangGraph

## Adding New Features

When adding new features:

1. Implement them in the `LangGraphHandler` class
2. Add appropriate state handling in the graph
3. Follow the existing patterns for web search and vision processing

## Common Methods

The LangGraphHandler maintains the same API as the original LLMHandler:

- `get_response()` - Get a response from the LLM (primary method)
- `get_response_async()` - Async version of get_response
- `initialize_llm()` - Initialize the LLM with a specific model
- `clear_chat_history()` - Clear chat history for a session
- `suggest_filename()` - Generate a filename suggestion based on content 