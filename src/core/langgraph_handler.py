import os
import logging
import json
import uuid
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Callable
from pathlib import Path
import asyncio
import nest_asyncio
import re
import time
import threading
from PyQt6.QtCore import QTimer

# LangChain imports
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import SQLChatMessageHistory

# LangGraph imports
from langgraph.graph import StateGraph, END, START
from langgraph.constants import Send

# Local imports
from ui.settings import Settings
from .web_search_handler import WebSearchHandler
from .vision_handler import VisionHandler
from .llm_factory import create_llm_instance
from .filename_suggester import FilenameSuggester
from .prompts_hub import (
    LANGGRAPH_BASE_SYSTEM_PROMPT,
    COMPOSE_MODE_INSTRUCTION,
    CHAT_MODE_INSTRUCTION,
    TOOL_CALLING_INSTRUCTION
)
from core.tools.tool_call_handler import ToolCallHandler
from core.instance_manager import DasiInstanceManager

# Import our new modules
from .langgraph_nodes import LangGraphNodes, GraphState
from .graph_builder import LangGraphBuilder
from .response_generation import ResponseGenerator


class LangGraphHandler:
    """Handler for LLM interactions using LangGraph."""

    def __init__(self):
        """Initialize the LangGraph handler."""
        self.settings = Settings()
        self.current_provider = None
        self.llm = None
        self.detected_language = None

        # Initialize database path for chat history
        self.db_path = str(Path(self.settings.config_dir) / 'chat_history.db')

        # Store message histories by session
        self.message_histories = {}

        # Get chat history limit from settings
        self.history_limit = self.settings.get(
            'general', 'chat_history_limit', default=20)

        # Initialize handlers
        self.web_search_handler = WebSearchHandler(self)
        self.vision_handler = VisionHandler(self.settings)

        # Build system prompt
        self._initialize_system_prompt()

        # Initialize filename suggester
        self.filename_suggester = FilenameSuggester(
            self.llm, self.system_prompt)

        # Use shared tool call handler from instance manager
        self.tool_call_handler = DasiInstanceManager.get_tool_call_handler()
        # Set up all tools - both web_search and system_info
        self.tool_call_handler.setup_tools(
            web_search_handler=self.web_search_handler)

        # Initialize the graph nodes
        self.graph_nodes = LangGraphNodes(self)

        # Initialize graph builder
        self.graph_builder = LangGraphBuilder(self)

        # Initialize the response generator
        self.response_generator = ResponseGenerator(self)

        # Connect to settings changes
        self.settings.models_changed.connect(self.on_models_changed)
        self.settings.custom_instructions_changed.connect(
            self.on_custom_instructions_changed)
        self.settings.temperature_changed.connect(self.on_temperature_changed)
        self.settings.tools_settings_changed.connect(
            self.on_tools_settings_changed)

        # Create the graph
        self.graph = self.graph_builder.build_graph()
        self.app = self.graph.compile()

        # Initialize LLM
        self.initialize_llm()

        # Apply nest_asyncio globally to allow nested event loops (e.g., running asyncio.run from within Qt)
        nest_asyncio.apply()

    def _initialize_system_prompt(self):
        """Initialize the system prompt with base and custom instructions."""
        # Base system prompt from prompts hub
        self.base_system_prompt = LANGGRAPH_BASE_SYSTEM_PROMPT

        # Get custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()

        # Combine system prompt with custom instructions if they exist
        self.system_prompt = self.base_system_prompt
        if custom_instructions:
            self.system_prompt = f"{self.base_system_prompt}\n\n=====CUSTOM_INSTRUCTIONS=====<user-defined instructions>\n{custom_instructions}\n======================="

        # Add tool calling instructions
        self.system_prompt = f"{self.system_prompt}\n\n{TOOL_CALLING_INSTRUCTION}"

        # Create base prompt template with memory
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{query}")
        ])

    def on_models_changed(self):
        """Handle changes to the models list."""
        # Reload settings
        self.settings.load_settings()
        # Update system prompt
        self._initialize_system_prompt()
        # Reinitialize LLM
        self.initialize_llm()

    def on_custom_instructions_changed(self):
        """Handle changes to custom instructions."""
        # Reload settings
        self.settings.load_settings()
        # Update system prompt
        self._initialize_system_prompt()

    def on_temperature_changed(self):
        """Handle changes to temperature setting."""
        # Reload settings
        self.settings.load_settings()
        # Update LLM if initialized
        if self.llm:
            try:
                temperature = self.settings.get(
                    'general', 'temperature', default=0.7)
                if hasattr(self.llm, 'temperature'):
                    self.llm.temperature = temperature
                elif hasattr(self.llm, 'model_kwargs') and isinstance(self.llm.model_kwargs, dict):
                    self.llm.model_kwargs['temperature'] = temperature
                logging.info(f"Updated LLM temperature to {temperature}")
            except Exception as e:
                logging.error(f"Error updating temperature: {str(e)}")

    def on_tools_settings_changed(self):
        """Handle changes to tool settings."""
        # Reload settings
        self.settings.load_settings()
        logging.info(
            "Tool settings changed, reinitializing LLM with updated tool configurations")

        # Reinitialize the LLM with current model but updated tool settings
        if self.llm and self.current_provider:
            current_model_id = None
            # Extract the current model ID from the LLM instance
            if hasattr(self.llm, 'model_name'):
                current_model_id = self.llm.model_name
            elif hasattr(self.llm, 'model'):
                current_model_id = self.llm.model

            if current_model_id:
                logging.info(
                    f"Reinitializing LLM with current model: {current_model_id}")
                self.initialize_llm(model_name=current_model_id)
            else:
                logging.info("Reinitializing LLM with default model")
                self.initialize_llm()
        else:
            logging.info(
                "No active LLM instance, initializing with default settings")
            self.initialize_llm()

    def initialize_llm(self, model_name: str = None, model_info: dict = None) -> bool:
        """Initialize the LLM using the llm_factory."""
        try:
            # Reload settings to ensure we have the latest config
            self.settings.load_settings()

            # --- Determine model info (provider, model_id) --- START ---
            resolved_model_info = None
            if model_info and isinstance(model_info, dict):
                resolved_model_info = model_info
                logging.info(
                    f"Initializing LLM using provided model info: {resolved_model_info.get('id', 'N/A')}, provider: {resolved_model_info.get('provider', 'N/A')}")
            elif model_name:
                selected_models = self.settings.get_selected_models()
                model_ids = [m['id'] for m in selected_models]
                logging.info(f"Available selected model IDs: {model_ids}")

                found_model = next(
                    (m for m in selected_models if m['id'] == model_name), None)

                # Google specific path
                if not found_model and model_name.startswith('models/'):
                    logging.info(
                        f"Looking up Google model by full path: {model_name}")
                    found_model = next(
                        (m for m in selected_models if m['id'] == model_name), None)

                if not found_model and '/' in model_name:  # Handle potential names like 'provider/model'
                    base_name = model_name.split('/')[-1]
                    logging.info(
                        f"Model '{model_name}' not found by exact match. Trying base name: {base_name}")
                    found_model = next(
                        (m for m in selected_models if m['id'].endswith(f"/{base_name}")), None)
                    if found_model:
                        logging.info(
                            f"Found model by partial match: {found_model['id']}, provider: {found_model['provider']}")

                if not found_model:
                    logging.error(
                        f"Model '{model_name}' not found in selected models.")
                    return False
                resolved_model_info = found_model
                logging.info(f"Selected model info: {resolved_model_info}")
            else:
                default_model_id = self.settings.get('models', 'default_model')
                selected_models = self.settings.get_selected_models()
                if not default_model_id:
                    if selected_models:
                        resolved_model_info = selected_models[0]
                        logging.info(
                            f"Using first selected model as default: {resolved_model_info['id']}, provider: {resolved_model_info['provider']}")
                    else:
                        logging.error(
                            "No default model set and no models selected.")
                        return False
                else:
                    resolved_model_info = next(
                        (m for m in selected_models if m['id'] == default_model_id), None)
                    if not resolved_model_info:
                        if selected_models:
                            resolved_model_info = selected_models[0]
                            logging.warning(
                                f"Default model '{default_model_id}' not found, using first selected model: {resolved_model_info['id']}, provider: {resolved_model_info['provider']}")
                        else:
                            logging.error(
                                "Default model specified but no models are selected.")
                            return False
            # --- Determine model info (provider, model_id) --- END ---

            if not resolved_model_info:
                logging.error(
                    "Could not resolve model information to initialize LLM.")
                return False

            provider = resolved_model_info['provider']
            model_id = resolved_model_info['id']
            temperature = self.settings.get(
                'general', 'temperature', default=0.7)

            # Define the tools that will be available to the LLM
            all_tools = [
                {
                    "name": "web_search",
                    "description": "Search the web for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The text to search for"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["web_search", "link_scrape"],
                                "description": "Either 'web_search' (default) or 'link_scrape'"
                            },
                            "url": {
                                "type": "string",
                                "description": "URL to scrape content from (required for link_scrape mode)"
                            },
                            "selected_text": {
                                "type": "string",
                                "description": "Additional context from user's selected text"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "system_info",
                    "description": "Retrieve information about the user's system",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {
                                "type": "string",
                                "enum": ["basic", "memory", "cpu", "all"],
                                "description": "Type of information to retrieve (basic, memory, cpu, or all)"
                            }
                        }
                    }
                },
                {
                    "name": "terminal_command",
                    "description": "Execute terminal commands safely",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The terminal command to execute"
                            },
                            "working_dir": {
                                "type": "string",
                                "description": "Optional working directory for the command (use ~ for home directory)"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Maximum execution time in seconds (default: 30)"
                            },
                            "shell_type": {
                                "type": "string",
                                "enum": ["bash", "sh", "fish", "zsh"],
                                "description": "Specific shell to use (default is user's shell)"
                            }
                        },
                        "required": ["command"]
                    }
                }
            ]

            # Filter tools based on what's enabled in settings
            tools = []
            for tool in all_tools:
                tool_name = tool["name"]
                setting_key = f"{tool_name}_enabled"
                if self.settings.get('tools', setting_key, default=True):
                    tools.append(tool)
                    logging.info(
                        f"Including enabled tool in LLM configuration: {tool_name}")
                else:
                    logging.info(
                        f"Excluding disabled tool from LLM configuration: {tool_name}")

            logging.info(
                f"Attempting to create LLM instance via factory: provider={provider}, model={model_id}, temp={temperature}")

            # Call the factory function with tools
            llm_instance = create_llm_instance(
                provider=provider,
                model_id=model_id,
                settings=self.settings,
                temperature=temperature,
                # Pass resolved info which might contain base_url etc.
                model_info=resolved_model_info,
                tools=tools
            )

            if llm_instance:
                self.llm = llm_instance
                self.current_provider = provider
                # Update the filename suggester's LLM instance
                self.filename_suggester.llm = llm_instance
                logging.info(
                    f"Successfully initialized {provider} model: {model_id} via factory")
                return True
            else:
                logging.error(
                    f"Failed to initialize {provider} model: {model_id} using factory")
                self.llm = None
                self.current_provider = None
                return False

        except Exception as e:
            logging.error(
                f"Unexpected error during LLM initialization: {str(e)}", exc_info=True)
            self.llm = None
            self.current_provider = None
            return False

    def _get_message_history(self, session_id: str):
        """Get or create message history for a session."""
        if session_id not in self.message_histories:
            self.message_histories[session_id] = SQLChatMessageHistory(
                session_id=session_id,
                connection=f"sqlite:///{self.db_path}"
            )
        return self.message_histories[session_id]

    def clear_chat_history(self, session_id: str):
        """Clear chat history for a specific session."""
        history = self._get_message_history(session_id)
        history.clear()
        if session_id in self.message_histories:
            del self.message_histories[session_id]

    # Delegate to ResponseGenerator
    def get_response_async(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None,
                           session_id: str = "default", selected_text: str = None,
                           mode: str = "chat", image_data: Optional[str] = None) -> str:
        """Process a query asynchronously using the LangGraph application and stream the response."""
        return self.response_generator.get_response_async(
            query=query,
            callback=callback,
            model=model,
            session_id=session_id,
            selected_text=selected_text,
            mode=mode,
            image_data=image_data
        )

    # Delegate to ResponseGenerator
    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None,
                     session_id: str = "default", selected_text: str = None,
                     mode: str = "chat", image_data: Optional[str] = None) -> str:
        """Synchronous wrapper for get_response_async."""
        return self.response_generator.get_response(
            query=query,
            callback=callback,
            model=model,
            session_id=session_id,
            selected_text=selected_text,
            mode=mode,
            image_data=image_data
        )

    # Delegate to ResponseGenerator
    def suggest_filename(self, content: str, session_id: str = "default") -> str:
        """Suggest a filename based on content and recent query history."""
        return self.response_generator.suggest_filename(content, session_id)

    # Forward tool call results to graph nodes
    def handle_tool_call_result(self, result):
        """Handle the result of a tool call from the tool handler."""
        logging.info(f"Forwarding tool call result to graph nodes: {result}")
        self.graph_nodes._on_tool_call_completed(result)
