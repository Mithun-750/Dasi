import logging
from langgraph.graph import StateGraph, END, START

from core.langgraph_nodes import GraphState


class LangGraphBuilder:
    """
    Handles the creation and maintenance of the LangGraph workflow.
    This class requires a LangGraphHandler instance to be passed to the constructor.
    """

    def __init__(self, handler):
        """
        Initialize with a reference to the main handler.

        Args:
            handler: The LangGraphHandler instance that owns this builder
        """
        self.handler = handler
        self.nodes = None

    def build_graph(self):
        """Build the LangGraph processing graph with conditional web search and vision processing."""
        self.nodes = self.handler.graph_nodes
        graph = StateGraph(GraphState)
        graph.add_node("initialize", self.nodes.initialize_state)
        graph.add_node("parse_query", self.nodes.parse_query)
        graph.add_node("web_search", self.nodes.web_search)
        graph.add_node("vision_processing", self.nodes.vision_processing)
        graph.add_node("prepare_messages", self.nodes.prepare_messages)
        graph.add_node("generate_response", self.nodes.generate_response)
        # Tool call node
        graph.add_node("tool_call", self.nodes.tool_call_node)

        # Initial graph flow
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "parse_query")

        # Conditional routing after parsing the query
        def route_after_parse(state: GraphState):
            use_web = state.get("use_web_search", False)
            use_vis = state.get("use_vision", False)
            has_img = state.get("image_data") is not None
            if use_web:
                return "web_search"
            elif use_vis and has_img and self.handler.vision_handler.has_vision_model_configured():
                return "vision_processing"
            elif use_vis and has_img:
                return "prepare_messages"
            else:
                return "prepare_messages"

        graph.add_conditional_edges(
            "parse_query",
            route_after_parse,
            {
                "web_search": "web_search",
                "vision_processing": "vision_processing",
                "prepare_messages": "prepare_messages"
            }
        )

        # Conditional routing after web search
        def route_after_web_search(state: GraphState):
            use_vis = state.get("use_vision", False)
            has_img = state.get("image_data") is not None
            if use_vis and has_img and self.handler.vision_handler.has_vision_model_configured():
                return "vision_processing"
            else:
                return "prepare_messages"

        graph.add_conditional_edges(
            "web_search",
            route_after_web_search,
            {
                "vision_processing": "vision_processing",
                "prepare_messages": "prepare_messages"
            }
        )

        # Vision processing always goes to prepare_messages
        graph.add_edge("vision_processing", "prepare_messages")

        # After preparing messages, always go to generate_response
        graph.add_edge("prepare_messages", "generate_response")

        # Route to tool_call if pending_tool_call is set after generate_response
        def route_after_generate_response(state: GraphState):
            if state.get('pending_tool_call'):
                return "tool_call"
            else:
                return END

        graph.add_conditional_edges(
            "generate_response",
            route_after_generate_response,
            {
                "tool_call": "tool_call",
                END: END
            }
        )

        # CRITICAL: After tool_call, ALWAYS go to prepare_messages to properly incorporate results
        # This ensures the tool results are added to the conversation before generating a response
        graph.add_edge("tool_call", "prepare_messages")

        logging.info(
            "LangGraph graph definition built with proper tool calling flow")
        return graph
