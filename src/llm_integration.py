import os
import logging
from typing import Optional, Callable, Dict, Any, Union

# Import both handlers
from llm_handler import LLMHandler
from langgraph_handler import LangGraphHandler


class LLMIntegration:
    """Integration class to manage LLM handlers.

    This class provides a unified interface for both the original LLMHandler
    and the new LangGraphHandler, allowing for easy switching between them.
    """

    def __init__(self, use_langgraph: bool = False):
        """Initialize the LLM integration.

        Args:
            use_langgraph: Whether to use LangGraph-based handler (default: False)
        """
        self.use_langgraph = use_langgraph
        self._handler = None
        self._initialize_handler()

    def _initialize_handler(self):
        """Initialize the appropriate handler based on configuration."""
        if self.use_langgraph:
            logging.info("Initializing LangGraph-based handler")
            self._handler = LangGraphHandler()
        else:
            logging.info("Initializing original LLM handler")
            self._handler = LLMHandler()

    def switch_handler(self, use_langgraph: bool):
        """Switch between handlers.

        Args:
            use_langgraph: Whether to use LangGraph-based handler
        """
        if use_langgraph != self.use_langgraph:
            self.use_langgraph = use_langgraph
            self._initialize_handler()

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None,
                     model: Optional[str] = None, session_id: str = "default") -> str:
        """Get response from the active LLM handler.

        This method routes the request to either the original LLMHandler or
        the new LangGraphHandler based on the current configuration.

        Args:
            query: The query to send to the LLM
            callback: Optional callback for streaming responses
            model: Optional model name/ID to use
            session_id: Session ID for chat history

        Returns:
            The response from the LLM
        """
        return self._handler.get_response(query, callback, model, session_id)

    def clear_chat_history(self, session_id: str):
        """Clear chat history for a specific session."""
        self._handler.clear_chat_history(session_id)

    def suggest_filename(self, content: str, session_id: str = "default") -> str:
        """Suggest a filename based on content and recent query history."""
        return self._handler.suggest_filename(content, session_id)

    def initialize_llm(self, model_name: str = None, model_info: dict = None) -> bool:
        """Initialize the LLM with the specified model."""
        return self._handler.initialize_llm(model_name, model_info)

    @property
    def handler(self):
        """Get the active handler instance."""
        return self._handler
