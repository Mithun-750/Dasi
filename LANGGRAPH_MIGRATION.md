# Migrating Dasi to LangGraph

This document explains the process of migrating Dasi from the original LangChain implementation to LangGraph for more powerful and flexible language model interactions.

## What is LangGraph?

LangGraph is an extension of LangChain aimed at building robust and stateful multi-actor applications with LLMs by modeling steps as edges and nodes in a graph. It provides better state management and more flexible workflows for complex AI applications.

## Migration Components

The migration includes the following new components:

1. **LangGraphHandler** (`src/langgraph_handler.py`) - A new implementation using LangGraph's graph-based approach
2. **LLMIntegration** (`src/llm_integration.py`) - An integration layer allowing easy switching between implementations
3. **Migration Script** (`src/migrate_to_langgraph.py`) - A utility script to help with migration

## How to Use

### Installing Dependencies

Make sure you have the required dependencies installed:

```bash
uv add langgraph langchain-cli
```

### Switching Between Implementations

There are two ways to switch between the original implementation and the new LangGraph implementation:

#### 1. Using the Migration Script

Run the migration script to switch to LangGraph:

```bash
python src/migrate_to_langgraph.py --enable
```

To switch back to the original implementation:

```bash
python src/migrate_to_langgraph.py
```

#### 2. Manual Configuration

You can manually edit your settings file located at `~/.config/dasi/settings.json` and add the following to the "general" section:

```json
{
  "general": {
    "use_langgraph": true
  }
}
```

Set to `false` to use the original implementation.

## Key Differences

### State Management

The LangGraph implementation uses a more structured approach to state management:

```python
class GraphState(TypedDict):
    """State for the LLM processing graph."""
    # Input fields
    query: str
    session_id: str
    selected_text: Optional[str]
    mode: str
    image_data: Optional[str]
    model_name: Optional[str]
    
    # Processing fields
    messages: List[Any]
    use_web_search: bool
    web_search_results: Optional[Dict]
    use_vision: bool
    vision_description: Optional[str]
    
    # Output fields
    response: str
    detected_language: Optional[str]
```

### Graph-Based Processing

Instead of procedural processing in a single method, the LangGraph implementation breaks down the process into distinct nodes and edges:

```python
def _build_graph(self):
    """Build the LangGraph processing graph."""
    # Create the state graph
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("initialize", self.initialize_state)
    graph.add_node("parse_query", self.parse_query)
    graph.add_node("prepare_messages", self.prepare_messages)
    graph.add_node("generate_response", self.generate_response)
    
    # Add edges
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "parse_query")
    graph.add_edge("parse_query", "prepare_messages")
    graph.add_edge("prepare_messages", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph
```

## Benefits of Migration

1. **More Structured Approach**: Clearly defined states and transitions
2. **Better Extensibility**: Easier to add new nodes or modify the processing flow
3. **Improved Testing**: Each component can be tested independently
4. **Enhanced Debugging**: Better visibility into each step of the process
5. **Future Compatibility**: Aligned with newer LangChain ecosystem direction

## Known Limitations

1. **Streaming Support**: Streaming with LangGraph is currently handled through a hybrid approach
2. **Performance**: Initial setup of the graph adds slight overhead for the first query

## Development and Testing

When developing or testing new features, you can easily switch between implementations to compare behavior:

```python
from llm_integration import LLMIntegration

# Use original implementation
llm = LLMIntegration(use_langgraph=False)

# Use LangGraph implementation
llm = LLMIntegration(use_langgraph=True)
```

## Running the Application

To run the application with the new implementation:

```bash
inv dev
```

The application will check the settings and use the appropriate implementation.

## Troubleshooting

If you encounter issues with the LangGraph implementation:

1. Check the logs for specific error messages
2. Try reverting to the original implementation
3. Make sure all dependencies are correctly installed
4. Verify that your settings file is correctly formatted 