import os
import logging
import json  # Add this import for tool call JSON parsing
import uuid  # Add this import for tool call ID generation
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Callable
import operator
from pathlib import Path
import asyncio
import nest_asyncio
import re  # Import re for _extract_code_block
import time  # Add time for timing logs
import threading

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


# Define the state structure for our graph
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
    web_search_query: Optional[str]  # Query used for web search node
    web_search_results: Optional[Dict]  # Results from web search node
    use_vision: bool
    vision_description: Optional[str]
    llm_instance: Optional[Any]  # Add field for the specific LLM instance

    # Tool calling fields
    pending_tool_call: Optional[Dict]  # Tool call requested by LLM
    # Result of a tool call after user confirmation
    tool_call_result: Optional[Dict]

    # Output fields
    response: str
    detected_language: Optional[str]


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

        # Initialize tool call event - reinitialized here to be safe
        self.tool_call_event = threading.Event()
        self.tool_call_result = None

        # Connect the signal after initializing the event
        self.tool_call_handler.tool_call_completed.connect(
            self._on_tool_call_completed)

        # Connect to settings changes
        self.settings.models_changed.connect(self.on_models_changed)
        self.settings.custom_instructions_changed.connect(
            self.on_custom_instructions_changed)
        self.settings.temperature_changed.connect(self.on_temperature_changed)

        # Create the graph
        self.graph = self._build_graph()
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
            tools = [
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
                }
            ]

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

    # Node functions for LangGraph

    def initialize_state(self, state: GraphState) -> GraphState:
        """Initialize the state with defaults for any missing values."""
        # Ensure all required fields are present
        if 'session_id' not in state:
            state['session_id'] = 'default'
        if 'mode' not in state:
            state['mode'] = 'chat'
        if 'messages' not in state:
            state['messages'] = []
        if 'use_web_search' not in state:
            state['use_web_search'] = False
        if 'use_vision' not in state:
            state['use_vision'] = False
        if 'pending_tool_call' not in state:
            state['pending_tool_call'] = None
        if 'tool_call_result' not in state:
            state['tool_call_result'] = None

        return state

    def parse_query(self, state: GraphState) -> GraphState:
        """Parse query for mode, image, web search triggers, and selected text."""
        logging.info("Entering parse_query node")
        updated_state = state.copy()
        query = updated_state['query']
        image_data = updated_state.get('image_data')
        selected_text = updated_state.get('selected_text')
        logging.debug(
            f"Inside parse_query: query='{query[:50]}...', has_image_data={image_data is not None}")

        # Default flags
        updated_state['use_vision'] = bool(image_data)
        updated_state['use_web_search'] = False
        updated_state['web_search_query'] = None  # Initialize web search query

        # Let the WebSearchHandler process the query context.
        # It will determine if web search is applicable based on triggers (e.g., /web, URL)
        # and its own internal checks against settings (API keys, enabled providers).
        process_result = self.web_search_handler.process_query_context(
            query,
            {'selected_text': selected_text}
        )

        # Store the potentially processed query for the web search node
        # This might be the original query or one modified by the context processor
        updated_state['web_search_query'] = process_result['query']

        # Set the flag if the handler determined web search/scrape is needed
        if process_result['mode'] in ['web_search', 'link_scrape']:
            logging.info(
                f"Web search/scrape triggered by handler. Mode: {process_result['mode']}")
            updated_state['use_web_search'] = True
            # The actual search happens in the web_search node
            # Keep the original query in updated_state['query'] for context in later steps
            # The web_search node will use updated_state['web_search_query']
        else:
            # If web search wasn't triggered by the handler, update the main query
            # with the result from the context processor (which might have just extracted context)
            updated_state['query'] = process_result['query']

        logging.debug(
            f"Parsed query. State: use_vision={updated_state['use_vision']}, use_web_search={updated_state['use_web_search']}, web_search_query={updated_state['web_search_query']}")
        return updated_state

    def web_search(self, state: GraphState) -> GraphState:
        """Perform web search or link scraping if triggered."""
        updated_state = state.copy()
        logging.info("Entering web_search node")

        if not updated_state.get('use_web_search', False):
            logging.debug("Skipping web search - use_web_search is false.")
            # Ensure flag is false if somehow reached here erroneously
            updated_state['use_web_search'] = False
            return updated_state

        selected_text = updated_state.get('selected_text')

        # Re-run context processing using the *original* query from the state
        # to ensure we correctly identify the mode (web_search vs link_scrape)
        # and extract the URL if it's a scrape.
        process_result = self.web_search_handler.process_query_context(
            updated_state['query'],  # Use original query for context detection
            {'selected_text': selected_text}
        )

        search_mode = process_result.get('mode')
        if search_mode not in ['web_search', 'link_scrape']:
            logging.warning(
                f"Web search node entered, but mode is '{search_mode}' based on original query. Skipping search.")
            # Turn off flag if mode is wrong
            updated_state['use_web_search'] = False
            return updated_state

        logging.info(f"Executing {search_mode}...")

        # --- CORRECTED CALL ---
        # Pass the full process_result dictionary obtained above directly
        search_result = self.web_search_handler.execute_search_or_scrape(
            process_result,  # Pass the dictionary directly
            selected_text
        )
        # --- END CORRECTION ---

        # Store results in the state
        updated_state['web_search_results'] = search_result
        logging.debug(f"Web search/scrape execution results: {search_result}")

        return updated_state

    def vision_processing(self, state: GraphState) -> GraphState:
        """Process image data using the VisionHandler if needed."""
        updated_state = state.copy()
        logging.info("Entering vision_processing node")
        use_vis = updated_state.get('use_vision')
        has_img = updated_state.get('image_data') is not None
        logging.debug(
            f"Inside vision_processing: use_vision={use_vis}, has_image={has_img}")

        if not use_vis or not has_img:
            logging.debug(
                "Skipping vision processing - use_vision is false or no image data.")
            # Ensure flag is false if state is inconsistent
            updated_state['use_vision'] = False
            return updated_state

        try:
            logging.info("Calling VisionHandler to get visual description.")
            description = self.vision_handler.get_visual_description(
                image_data_base64=updated_state['image_data'],
                # Use original query as hint
                prompt_hint=updated_state['query']
            )

            if description:
                # Vision model processed the image and returned a description
                updated_state['vision_description'] = description
                logging.info("Vision description generated successfully.")
                # If we have a description, then the main model shouldn't get the image
                updated_state['use_vision'] = True
            else:
                # Check if vision model is not configured
                if not self.vision_handler.has_vision_model_configured():
                    logging.info(
                        "No vision model configured - passing image to main model")
                    # Keep use_vision=True so the image is passed to the main model
                    updated_state['vision_description'] = None
                else:
                    # Vision model failed to generate a description
                    logging.warning("VisionHandler returned no description.")
                    # Add a system note later in prepare_messages if description failed
                    updated_state['vision_description'] = None
        except Exception as e:
            logging.error(
                f"Error during vision processing: {str(e)}", exc_info=True)
            # Add a system note later in prepare_messages
            # Explicitly set to None
            updated_state['vision_description'] = None

        return updated_state

    def prepare_messages(self, state: GraphState) -> GraphState:
        """Prepare the messages list for the LLM, incorporating web results and vision description."""
        updated_state = state.copy()
        logging.info("Entering prepare_messages node")

        # Start with system message
        messages = [SystemMessage(content=self.system_prompt)]

        # Add mode-specific instruction
        if state['mode'] == 'compose':
            mode_instruction = COMPOSE_MODE_INSTRUCTION
        else:
            mode_instruction = CHAT_MODE_INSTRUCTION

        messages.append(SystemMessage(content=mode_instruction))

        # Add chat history
        session_id = state['session_id']
        message_history = self._get_message_history(session_id)
        history_messages = message_history.messages[-self.history_limit:
                                                    ] if message_history.messages else []

        # Convert to appropriate message types
        typed_history = []
        for msg in history_messages:
            if isinstance(msg, HumanMessage):
                typed_history.append(msg)
            elif isinstance(msg, AIMessage):
                typed_history.append(msg)
            elif isinstance(msg, SystemMessage):
                typed_history.append(msg)
            elif isinstance(msg, ToolMessage):
                typed_history.append(msg)  # Make sure to include ToolMessages
            elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                if msg.type == 'human':
                    typed_history.append(HumanMessage(content=msg.content))
                elif msg.type == 'ai':
                    typed_history.append(AIMessage(content=msg.content))
                elif msg.type == 'tool':
                    # Handle legacy tool messages
                    tool_call_id = getattr(msg, 'tool_call_id', None)
                    typed_history.append(ToolMessage(
                        content=msg.content, tool_call_id=tool_call_id))

        messages.extend(typed_history)

        # <<< MODIFIED SECTION: Handle Tool Call Results >>>
        # If there's a tool call result from user confirmation, add a ToolMessage to the messages
        tool_call_result = state.get('tool_call_result')
        if tool_call_result and isinstance(tool_call_result, dict):
            logging.info(
                f"Adding tool call result to messages: {tool_call_result}")
            tool_name = tool_call_result.get('tool', 'unknown')
            result = tool_call_result.get('result', {})
            # Get the tool call ID if present
            tool_call_id = tool_call_result.get('id')

            if result == 'rejected':
                # For rejected tool calls, add a special ToolMessage indicating rejection
                # This provides explicit feedback to the model about the rejection
                messages.append(ToolMessage(
                    content="The user rejected this tool call request. Please proceed without using this tool.",
                    tool_call_id=tool_call_id
                ))
                logging.info("Added tool rejection message")
            else:
                # For successful tool calls:
                if tool_name == 'web_search' and isinstance(result, dict) and result.get('status') == 'success':
                    # Format web search results as a structured ToolMessage
                    tool_content = result.get('data', 'No results found')
                    messages.append(ToolMessage(
                        content=tool_content, tool_call_id=tool_call_id))
                    logging.info(
                        f"Added web search ToolMessage with ID: {tool_call_id}")
                elif tool_name == 'system_info' and isinstance(result, dict) and result.get('status') == 'success':
                    # Format system info results
                    tool_content = result.get(
                        'data', 'No system information available')
                    messages.append(ToolMessage(
                        content=tool_content, tool_call_id=tool_call_id))
                    logging.info(
                        f"Added system info ToolMessage with ID: {tool_call_id}")
                else:
                    # Generic format for other tools or error cases
                    if isinstance(result, dict) and 'data' in result:
                        tool_content = result.get('data')
                    elif isinstance(result, dict) and 'status' in result and 'data' in result:
                        tool_content = result.get('data')
                    else:
                        # Try to extract useful information from nested structures
                        if isinstance(result, dict) and 'result' in result and isinstance(result['result'], dict):
                            inner_result = result['result']
                            if 'data' in inner_result:
                                tool_content = inner_result['data']
                            elif 'status' in inner_result and inner_result.get('status') == 'success':
                                tool_content = str(inner_result)
                            else:
                                tool_content = str(result)
                        else:
                            tool_content = str(result)

                    messages.append(ToolMessage(
                        content=tool_content, tool_call_id=tool_call_id))
                    logging.info(
                        f"Added generic ToolMessage for {tool_name} with ID: {tool_call_id}")
                    logging.debug(f"Tool content: {tool_content[:100]}..." if len(
                        str(tool_content)) > 100 else tool_content)

            # Clear the tool call result after using it to prevent reprocessing
            updated_state['tool_call_result'] = None
        # <<< END MODIFIED SECTION >>>

        # Handle web search results (separate from tool calls)
        web_search_results = state.get('web_search_results')
        final_query_text = updated_state['query']  # Start with original query

        # Existing web search results handling
        if web_search_results:
            logging.info(
                "Incorporating web search/scrape results into messages.")
            if web_search_results.get('status') == 'error':
                logging.error(
                    f"Web search/scrape failed: {web_search_results.get('error')}")
                # Modify query to inform LLM about the error
                search_mode_desc = web_search_results.get(
                    'mode', 'web task').replace('_', ' ')  # Use a generic term
                error_info = web_search_results.get('error', 'Unknown error')
                # The query before web node modified it
                original_query = updated_state['query']
                final_query_text = f"I tried to perform a {search_mode_desc} based on the query '{original_query}' but encountered an error: {error_info}. Please answer the original query '{original_query}' without the web results."
            elif web_search_results.get('status') == 'success':
                # Use the fully formatted query from the web_search_handler
                if 'query' in web_search_results:
                    final_query_text = web_search_results['query']
                    logging.debug(
                        "Using pre-formatted query from web_search_handler.")
                else:
                    logging.warning(
                        "Web search results status is success, but 'query' key is missing. Using original query.")

                # Add system instruction from web_search_handler if it exists
                if web_search_results.get('system_instruction'):
                    messages.append(SystemMessage(
                        content=web_search_results['system_instruction']))
                    logging.debug(
                        "Added system instruction from web_search_handler.")
            else:
                logging.warning(
                    f"Web search results present but status is not 'success' or 'error': {web_search_results.get('status')}")
                # Fallback to original query if status is unexpected

        # Append selected text if present AND not already added via web blocks
        if state.get('selected_text') and "=====SELECTED_TEXT=====" not in final_query_text:
            final_query_text += f"\n\n=====SELECTED_TEXT=====<text selected by the user>\n{state['selected_text']}\n======================="

        # Determine final message type based on image and vision description
        image_data = state.get('image_data')
        vision_description = state.get('vision_description')
        is_vision_model_configured = self.vision_handler.has_vision_model_configured()

        if vision_description:
            # Case 1: Vision model success - Append description, send text-only
            logging.info(
                "Vision description present. Appending to text query.")
            final_query_content = f"\n\n=====VISUAL_DESCRIPTION=====<description generated by vision model>\n{vision_description}\n======================="
            query_message = HumanMessage(content=final_query_content)

        elif image_data:
            # Image present, but no description generated
            if is_vision_model_configured:
                # Case 3: Vision model configured but failed - Send text-only with error note
                logging.warning(
                    "Image present, vision model configured but failed. Adding system note.")
                final_query_content = "\n\n=====SYSTEM_NOTE=====\n(Failed to process the provided visual input using the configured vision model.)\n====================="
                query_message = HumanMessage(content=final_query_content)
            else:
                # Case 2: No vision model configured - Send multimodal message
                logging.info(
                    "Image present, no vision model configured. Constructing multimodal message.")
                # Clean base64 data
                if image_data.startswith('data:'):
                    image_data = image_data.split(',', 1)[-1]
                content_blocks = [
                    {"type": "text", "text": final_query_content},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"}
                    }
                ]
                query_message = HumanMessage(content=content_blocks)
        else:
            # Case 4: No image data - Send text-only
            logging.info("No image data. Constructing text-only message.")
            query_message = HumanMessage(content=final_query_text)

        # Add the final prepared query message to the list
        messages.append(query_message)

        # Save the prepared messages
        updated_state['messages'] = messages
        logging.debug(f"Prepared messages: {messages}")

        return updated_state

    def generate_response(self, state: GraphState) -> GraphState:
        """Generate a response using the LLM. If a tool call is detected, add it to state and route to tool_call node."""
        updated_state = state.copy()
        llm_instance = state.get('llm_instance')
        try:
            if not llm_instance:
                if not self.llm:
                    if not self.initialize_llm(model_name=state.get('model_name')):
                        updated_state['response'] = "⚠️ LLM could not be initialized from state or fallback."
                        return updated_state
                    llm_instance = self.llm
                else:
                    llm_instance = self.llm

            logging.info("Invoking LLM for response generation")
            response = llm_instance.invoke(state['messages'])
            final_response = response.content.strip()

            # Log the full response for debugging
            logging.debug(f"LLM raw response: {final_response[:200]}..." if len(
                final_response) > 200 else final_response)

            # Improved tool call detection - check for both marker format and function calling if available
            tool_detected = False
            tool_name = None
            tool_args = None
            tool_id = None

            # Check for the custom tool marker format
            if '<<TOOL:' in final_response:
                logging.info("Tool call marker detected in LLM response")
                import json
                import re
                import uuid

                match = re.search(
                    r'<<TOOL:\s*(\w+)\s*(\{.*?\})>>', final_response)
                if match:
                    tool_detected = True
                    tool_name = match.group(1)
                    tool_args_str = match.group(2)
                    logging.info(
                        f"Parsed tool call: {tool_name} with args: {tool_args_str}")
                    try:
                        tool_args = json.loads(tool_args_str)
                        # Generate a unique ID for this tool call if none exists
                        tool_id = f"call_{uuid.uuid4().hex[:24]}"
                        # Clean the response by removing the tool call marker
                        cleaned_response = re.sub(
                            r'<<TOOL:.*?>>', '', final_response).strip()
                        final_response = cleaned_response
                    except json.JSONDecodeError as e:
                        logging.error(f"Error parsing tool args JSON: {e}")
                        tool_detected = False
                else:
                    logging.warning(
                        "Tool call marker found but couldn't parse the format")

            # Check for function calling in OpenAI/Anthropic response format if available
            # This is model-dependent and would need to be expanded for each supported model's format
            elif hasattr(response, 'additional_kwargs') and response.additional_kwargs:
                # OpenAI format
                if 'function_call' in response.additional_kwargs:
                    func_call = response.additional_kwargs['function_call']
                    if isinstance(func_call, dict) and 'name' in func_call and 'arguments' in func_call:
                        tool_detected = True
                        tool_name = func_call['name']
                        try:
                            import json
                            tool_args = json.loads(func_call['arguments'])
                            tool_id = func_call.get('id')
                            if not tool_id:
                                import uuid
                                tool_id = f"call_{uuid.uuid4().hex[:24]}"
                            logging.info(
                                f"Detected OpenAI function call: {tool_name}, id: {tool_id}")
                        except json.JSONDecodeError:
                            logging.error(
                                f"Error parsing OpenAI function args JSON")
                            tool_detected = False

                # Anthropic format (tool_use)
                elif 'tool_use' in response.additional_kwargs:
                    tool_use = response.additional_kwargs['tool_use']
                    if isinstance(tool_use, dict) and 'name' in tool_use and 'input' in tool_use:
                        tool_detected = True
                        tool_name = tool_use['name']
                        # Already a dict in Anthropic's format
                        tool_args = tool_use['input']
                        tool_id = tool_use.get('id')
                        if not tool_id:
                            import uuid
                            tool_id = f"call_{uuid.uuid4().hex[:24]}"
                        logging.info(
                            f"Detected Anthropic tool_use: {tool_name}, id: {tool_id}")

                # Check for tool_calls array (newer format like OpenAI API)
                elif 'tool_calls' in response.additional_kwargs:
                    tool_calls = response.additional_kwargs['tool_calls']
                    if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                        first_call = tool_calls[0]
                        if isinstance(first_call, dict):
                            # Extract from potential nested structure
                            if 'function' in first_call and isinstance(first_call['function'], dict):
                                tool_detected = True
                                tool_name = first_call['function'].get('name')
                                try:
                                    import json
                                    args_str = first_call['function'].get(
                                        'arguments', '{}')
                                    tool_args = json.loads(args_str)
                                    tool_id = first_call.get('id')
                                    if not tool_id:
                                        import uuid
                                        tool_id = f"call_{uuid.uuid4().hex[:24]}"
                                    logging.info(
                                        f"Detected tool_calls array: {tool_name}, id: {tool_id}")
                                except json.JSONDecodeError:
                                    logging.error(
                                        f"Error parsing tool_calls args JSON")
                                    tool_detected = False
                            else:
                                # Direct structure
                                tool_detected = True
                                tool_name = first_call.get('name')
                                tool_args = first_call.get('args', {})
                                tool_id = first_call.get('id')
                                if not tool_id:
                                    import uuid
                                    tool_id = f"call_{uuid.uuid4().hex[:24]}"
                                logging.info(
                                    f"Detected direct tool_calls: {tool_name}, id: {tool_id}")

            if tool_detected and tool_name and tool_args is not None:
                # Add the tool call to state and let the graph handle routing
                updated_state['pending_tool_call'] = {
                    'tool': tool_name,
                    'args': tool_args,
                    'id': tool_id  # Include the tool ID
                }
                updated_state['response'] = final_response
                logging.info(
                    f"Tool call for {tool_name} (ID: {tool_id}) added to state, routing to tool_call node")
                return updated_state
            else:
                logging.debug("No tool calls detected in response")

            # Normal response processing (non-tool call)
            is_compose_mode = (state['mode'] == 'compose')
            if is_compose_mode:
                final_response, detected_language = self._extract_code_block(
                    final_response)
                updated_state['detected_language'] = detected_language
            session_id = state['session_id']
            message_history = self._get_message_history(session_id)
            message_history.add_message(state['messages'][-1])
            message_history.add_message(AIMessage(content=final_response))
            updated_state['response'] = final_response
            return updated_state
        except Exception as e:
            logging.error(
                f"Error getting LLM response in generate_response node: {str(e)}", exc_info=True)
            error_msg = str(e)
            updated_state['response'] = f"⚠️ Error in generate_response: {error_msg}"
            return updated_state

    def _extract_code_block(self, response: str):
        """Extract code blocks from response text."""
        # Strip whitespace for more reliable pattern matching
        stripped_response = response.strip()

        # Check if response starts with triple backticks and ends with triple backticks
        if stripped_response.startswith("```") and stripped_response.endswith("```"):
            # Find the first newline to extract language
            first_line_end = stripped_response.find("\n")
            if first_line_end > 3:  # We have a language identifier
                language = stripped_response[3:first_line_end].strip().lower()
                # Remove the starting line with backticks and language
                content = stripped_response[first_line_end+1:-3].strip()
                return content, language
            else:
                # No language specified
                content = stripped_response[4:-3].strip()
                return content, None

        # Fallback to regex for more complex patterns
        code_block_pattern = r'^\s*```(\w*)\s*\n([\s\S]*?)\n\s*```\s*$'
        match = re.match(code_block_pattern, stripped_response)

        if match:
            language = match.group(1).strip().lower() or None
            code_content = match.group(2)
            return code_content, language

        # If we get here, it wasn't a code block or the pattern didn't match
        return response, None

    def _build_graph(self):
        """Build the LangGraph processing graph with conditional web search and vision processing."""
        graph = StateGraph(GraphState)
        graph.add_node("initialize", self.initialize_state)
        graph.add_node("parse_query", self.parse_query)
        graph.add_node("web_search", self.web_search)
        graph.add_node("vision_processing", self.vision_processing)
        graph.add_node("prepare_messages", self.prepare_messages)
        graph.add_node("generate_response", self.generate_response)
        graph.add_node("tool_call", self.tool_call_node)  # Tool call node

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
            elif use_vis and has_img and self.vision_handler.has_vision_model_configured():
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
            if use_vis and has_img and self.vision_handler.has_vision_model_configured():
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

    async def tool_call_node(self, state):
        """
        LangGraph node for tool calling with user confirmation.

        This node:
        1. Takes a tool call request from the LLM
        2. Sends it to the ToolCallHandler for user confirmation
        3. Waits for user response (accept/reject)
        4. Receives the tool result
        5. Updates the state with the result
        6. Routes back to prepare_messages
        """
        # Get the pending tool call
        tool_call = state.get('pending_tool_call')
        if not tool_call:
            logging.warning(
                "tool_call_node entered without a pending_tool_call in state")
            return state

        tool_name = tool_call.get('tool')
        tool_args = tool_call.get('args', {})
        # The tool call ID for proper response association
        tool_id = tool_call.get('id')

        logging.info(
            f"Tool call node processing: {tool_name} with ID: {tool_id}")

        # Clear the pending tool call from state to prevent reprocessing
        new_state = state.copy()
        new_state['pending_tool_call'] = None

        try:
            # Emit to UI and wait for user confirmation
            self.tool_call_handler.request_tool_call(tool_name, tool_args)
            self.tool_call_event.clear()

            # Log the start of waiting period
            wait_start_time = time.monotonic()
            logging.info(f"Waiting for user to confirm tool call: {tool_name}")

            # Update the UI callback if available to show we're waiting
            callback = None  # Define callback to avoid reference errors
            accumulated_response = ""
            # TODO: Get callback and current accumulated response if possible
            if 'response' in state:
                accumulated_response = state['response']

            if callback:
                callback(accumulated_response +
                         "\n\n[Waiting for your confirmation to use the tool...]")

            # Wait for user response with periodic progress updates
            logging.info(
                f"Waiting for user response for {tool_name} tool call")
            try:
                # Run the blocking threading.Event.wait() in a separate thread
                # to avoid blocking the main asyncio event loop.
                loop = asyncio.get_running_loop()
                tool_call_timeout = 120.0

                if callback:
                    # If we have a callback, we need to periodically check
                    wait_start = time.monotonic()
                    while True:
                        # Wait for 1 second in executor
                        event_set = await loop.run_in_executor(
                            None, self.tool_call_event.wait, 1.0
                        )
                        if event_set:
                            break  # Event was set

                        # Check for timeout
                        wait_duration = time.monotonic() - wait_start
                        if wait_duration >= tool_call_timeout:
                            logging.warning(
                                f"Timeout waiting for tool call response for {tool_name}")
                            # Set result to timeout error
                            self.tool_call_result = {
                                'tool': tool_name,
                                'id': tool_id,
                                'result': {
                                    'status': 'error',
                                    'message': 'Timeout waiting for user confirmation'
                                }
                            }
                            break  # Exit loop on timeout

                        # Update dots for UI callback
                        dots = "." * (int(wait_duration) % 4)
                        waiting_message = f"{accumulated_response}\n\n[Waiting for your confirmation to use the tool{dots}]"
                        callback(waiting_message)
                else:
                    # If no callback, just wait directly in executor
                    event_set = await loop.run_in_executor(
                        None, self.tool_call_event.wait, tool_call_timeout
                    )
                    if not event_set:
                        logging.warning(
                            f"Timeout waiting for tool call response for {tool_name}")
                        # Set result to timeout error
                        self.tool_call_result = {
                            'tool': tool_name,
                            'id': tool_id,
                            'result': {
                                'status': 'error',
                                'message': 'Timeout waiting for user confirmation'
                            }
                        }

                wait_end_time = time.monotonic()
                wait_duration = wait_end_time - wait_start_time
                logging.info(
                    f"Received user response for {tool_name} tool call after {wait_duration:.3f} seconds")

            except Exception as e:
                logging.error(
                    f"Error during tool call wait: {e}", exc_info=True)
                # Set result to error
                self.tool_call_result = {
                    'tool': tool_name,
                    'id': tool_id,
                    'result': {
                        'status': 'error',
                        'message': f'Error waiting for response: {str(e)}'
                    }
                }

            # Clear the event for the next tool call
            self.tool_call_event.clear()

            # Get the result
            result = self.tool_call_result

            # Add the tool_call_id to the result for proper association
            if result and isinstance(result, dict):
                if 'id' not in result:
                    result['id'] = tool_id

            # Store the result in the state for prepare_messages to process
            new_state['tool_call_result'] = result
            logging.info(f"Tool call result added to state: {result}")

            # Reset the tool_call_result to avoid reuse
            self.tool_call_result = None

            # Notify the UI that we're about to process the tool results with the LLM
            # This helps ensure the preview panel is visible for the follow-up response
            try:
                self.tool_call_handler.tool_call_processing.emit(tool_name)
            except Exception as e:
                logging.error(f"Error emitting processing signal: {e}")

        except Exception as e:
            logging.error(f"Error in tool_call_node: {e}", exc_info=True)
            # Add error result to state
            new_state['tool_call_result'] = {
                'tool': tool_name,
                'result': {
                    'status': 'error',
                    'message': f"Error during tool execution: {str(e)}"
                },
                'id': tool_id
            }

        return new_state

    def _on_tool_call_completed(self, result):
        """
        Callback for when a tool call is completed.

        Args:
            result: The result of the tool call, containing:
                - tool: The name of the tool that was called
                - result: The result of the tool call
                - id: The ID of the tool call
        """
        logging.info(f"Tool call completed with result: {result}")

        # Store the result for the tool_call_node to use
        self.tool_call_result = result

        # Use threading.Event.set() instead of asyncio.Event.set()
        try:
            self.tool_call_event.set()
            logging.info("Tool call event set successfully")
        except Exception as e:
            logging.error(f"Error setting tool call event: {e}")
            # Try to recreate the event if it's somehow invalid
            try:
                self.tool_call_event = threading.Event()
                self.tool_call_event.set()
                logging.info("Created new event and set it successfully")
            except Exception as inner_e:
                logging.error(f"Failed to recreate event: {inner_e}")

    async def get_response_async(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None, session_id: str = "default", selected_text: str = None, mode: str = "chat", image_data: Optional[str] = None) -> str:
        """
        Process a query asynchronously using the LangGraph application and stream the response.

        Args:
            query: The user's query.
            callback: Optional callback function to receive streamed chunks.
            model: Optional specific model ID to use.
            session_id: The session ID for maintaining chat history.
            selected_text: Optional selected text from the user's environment.
            mode: The interaction mode ("chat" or "compose").
            image_data: Optional base64 encoded image data for vision models.

        Returns:
            The complete response string.
        """
        try:
            logging.info(
                f"get_response_async called: model={model}, session_id={session_id}, mode={mode}, has_image_data={image_data is not None}")
            if image_data:
                logging.debug(
                    f"Image data received (first 50 chars): {image_data[:50]}...")

            loop = asyncio.get_event_loop()  # Get the current event loop
            logging.info(
                f"get_response_async called with model: {model}, session_id: {session_id}, mode: {mode}")

            # --- Initialize LLM based on model (or default) ---
            if model:
                selected_models = self.settings.get_selected_models()
                model_info = next(
                    (m for m in selected_models if m.get('id') == model), None)
                if not model_info:
                    logging.error(
                        f"Model '{model}' not found. Falling back to default.")
                    # Fallback to default if specific model not found/initialized
                    if not self.initialize_llm():
                        raise ValueError("Failed to initialize default LLM.")
                else:
                    if not self.initialize_llm(model_name=model, model_info=model_info):
                        raise ValueError(
                            f"Failed to initialize LLM for model: {model}")
            elif not self.llm:  # Initialize default if no LLM exists
                if not self.initialize_llm():
                    raise ValueError(
                        "LLM is not initialized and default failed.")
            # --- LLM Initialization END ---

            # Prepare initial state
            initial_state = GraphState(
                query=query,
                session_id=session_id,
                selected_text=selected_text,
                mode=mode,
                image_data=image_data,
                model_name=model if model else getattr(self.llm, 'model_name', None) or getattr(
                    self.llm, 'model', 'unknown'),  # Use actual model name
                messages=[],
                use_web_search=False,
                web_search_query=None,
                web_search_results=None,
                use_vision=bool(image_data),
                vision_description=None,
                llm_instance=self.llm,  # Pass the initialized LLM instance
                response="",
                detected_language=None,
                pending_tool_call=None,
                tool_call_result=None
            )

            # Prepare configuration for the specific session
            config = {"configurable": {"session_id": session_id}}

            # Direct approach: Run the state through the necessary nodes to prepare the messages,
            # then manually invoke the LLM with streaming rather than relying on LangGraph streaming

            # First process the state through all the nodes up to the LLM call
            # This is a simplified version of what the graph would do
            logging.info("Processing initial state through graph nodes")
            state = self.initialize_state(initial_state)
            state = self.parse_query(state)

            if state.get('use_web_search', False):
                state = self.web_search(state)

            if state.get('use_vision', False) and state.get('image_data') is not None:
                state = self.vision_processing(state)

            state = self.prepare_messages(state)

            # At this point, state['messages'] contains all the necessary messages for the LLM

            if not state.get('messages'):
                raise ValueError("No messages prepared for LLM")

            logging.info(f"Prepared {len(state['messages'])} messages for LLM")

            # Now directly call the LLM with streaming
            llm_instance = state.get('llm_instance') or self.llm

            if not llm_instance:
                raise ValueError("No LLM instance available")

            logging.info(f"Invoking LLM ({model or 'default'}) with streaming")

            # Send a small initial chunk to signal the stream is starting
            if callback:
                callback("")

            # Use LangChain's streaming capability directly
            accumulated_response = ""
            accumulated_chunk = None

            # We'll capture tool calls here if they happen
            detected_tool_calls = []

            # Process each chunk from the stream
            async for chunk in llm_instance.astream(state['messages']):
                # If this is our first chunk, remember it for accumulation
                if accumulated_chunk is None:
                    accumulated_chunk = chunk
                else:
                    # Otherwise, add this chunk to our accumulated chunk
                    accumulated_chunk = accumulated_chunk + chunk

                # Extract content for displaying in the UI
                chunk_content = chunk.content if hasattr(
                    chunk, 'content') else str(chunk)
                accumulated_response += chunk_content

                # Check for tool calls using LangChain's standardized interface
                if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                    # Log all tool call chunks we find
                    logging.info(
                        f"Tool call chunks in chunk: {chunk.tool_call_chunks}")
                    detected_tool_calls = chunk.tool_call_chunks

                # For compatibility, also check the tool_calls property
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    logging.info(f"Tool calls in chunk: {chunk.tool_calls}")
                    # This is the fully assembled tool call
                    detected_tool_calls = chunk.tool_calls

                # Pass the FULL accumulated response to the callback
                if callback:
                    try:
                        callback(accumulated_response)
                    except Exception as e:
                        logging.error(f"Error in callback: {e}")

            # Store the final accumulated response
            full_response = accumulated_response

            logging.info(
                f"Streaming completed. Final response length: {len(full_response)}")

            # Once streaming is done, check if we've accumulated any tool calls
            if accumulated_chunk and hasattr(accumulated_chunk, 'tool_calls') and accumulated_chunk.tool_calls:
                logging.info(
                    f"Final tool calls: {accumulated_chunk.tool_calls}")

                # Process each tool call from the standardized LangChain format
                for tool_call in accumulated_chunk.tool_calls:
                    # Extract the standard fields
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args')
                    tool_id = tool_call.get('id')

                    if tool_name and tool_args is not None:
                        logging.info(
                            f"Processing LangChain tool call: {tool_name} with ID: {tool_id}")

                        try:
                            # Request tool call confirmation from the user
                            self.tool_call_handler.request_tool_call(
                                tool_name, tool_args)
                            self.tool_call_event.clear()

                            # Log the start of waiting period
                            wait_start_time = time.monotonic()
                            logging.info(
                                f"Waiting for user to confirm tool call: {tool_name}")

                            # Update the UI callback if available to show we're waiting
                            if callback:
                                callback(
                                    accumulated_response + "\n\n[Waiting for your confirmation to use the tool...]")

                            # Wait for user response with periodic progress updates
                            logging.info(
                                f"Waiting for user response for {tool_name} tool call")
                            try:
                                # Run the blocking threading.Event.wait() in a separate thread
                                # to avoid blocking the main asyncio event loop.
                                loop = asyncio.get_running_loop()
                                tool_call_timeout = 120.0

                                if callback:
                                    # If we have a callback, we need to periodically check
                                    wait_start = time.monotonic()
                                    while True:
                                        # Wait for 1 second in executor
                                        event_set = await loop.run_in_executor(
                                            None, self.tool_call_event.wait, 1.0
                                        )
                                        if event_set:
                                            break  # Event was set

                                        # Check for timeout
                                        wait_duration = time.monotonic() - wait_start
                                        if wait_duration >= tool_call_timeout:
                                            logging.warning(
                                                f"Timeout waiting for tool call response for {tool_name}")
                                            # Set result to timeout error
                                            self.tool_call_result = {
                                                'tool': tool_name,
                                                'id': tool_id,
                                                'result': {
                                                    'status': 'error',
                                                    'message': 'Timeout waiting for user confirmation'
                                                }
                                            }
                                            break  # Exit loop on timeout

                                        # Update dots for UI callback
                                        dots = "." * (int(wait_duration) % 4)
                                        waiting_message = f"{accumulated_response}\n\n[Waiting for your confirmation to use the tool{dots}]"
                                        callback(waiting_message)
                                else:
                                    # If no callback, just wait directly in executor
                                    event_set = await loop.run_in_executor(
                                        None, self.tool_call_event.wait, tool_call_timeout
                                    )
                                    if not event_set:
                                        logging.warning(
                                            f"Timeout waiting for tool call response for {tool_name}")
                                        # Set result to timeout error
                                        self.tool_call_result = {
                                            'tool': tool_name,
                                            'id': tool_id,
                                            'result': {
                                                'status': 'error',
                                                'message': 'Timeout waiting for user confirmation'
                                            }
                                        }

                                wait_end_time = time.monotonic()
                                wait_duration = wait_end_time - wait_start_time
                                logging.info(
                                    f"Received user response for {tool_name} tool call after {wait_duration:.3f} seconds")

                            except Exception as e:
                                logging.error(
                                    f"Error during tool call wait: {e}", exc_info=True)
                                # Set result to error
                                self.tool_call_result = {
                                    'tool': tool_name,
                                    'id': tool_id,
                                    'result': {
                                        'status': 'error',
                                        'message': f'Error waiting for response: {str(e)}'
                                    }
                                }

                            # Clear the event for the next tool call
                            self.tool_call_event.clear()

                            # Get the result
                            result = self.tool_call_result

                            # Add the tool_call_id to the result for proper association
                            if result and isinstance(result, dict):
                                if 'id' not in result:
                                    result['id'] = tool_id

                            # If the result is not rejected
                            if result and result.get('result') != 'rejected':
                                # Create state with tool call result for a second round of processing
                                logging.info(
                                    "Processing tool results for follow-up response")
                                tool_state = state.copy()
                                tool_state['tool_call_result'] = result

                                # Process through prepare_messages to incorporate the tool result
                                logging.info(
                                    "Processing tool results for follow-up response")
                                tool_state = self.prepare_messages(tool_state)

                                # Log the tool state messages for debugging
                                logging.info(
                                    f"Prepared {len(tool_state['messages'])} messages for follow-up LLM call")
                                # Log the last few messages to see if the tool result is included
                                for i, msg in enumerate(tool_state['messages'][-3:]):
                                    content_preview = ""
                                    if hasattr(msg, 'content'):
                                        if isinstance(msg.content, str):
                                            content_preview = msg.content[:100]
                                        elif isinstance(msg.content, list):
                                            content_preview = str(
                                                msg.content)[:100]
                                        else:
                                            content_preview = str(
                                                msg.content)[:100]
                                    logging.info(
                                        f"Message {len(tool_state['messages']) - 3 + i}: {type(msg).__name__} - {content_preview}...")

                                # Get a second response from the LLM with the tool results
                                logging.info(
                                    "Getting follow-up response with tool results")

                                # Give the UI a moment to update with the tool result before continuing
                                await asyncio.sleep(0.5)

                                # Send initial empty chunk to signal continuation
                                if callback:
                                    callback(full_response + "\n\n")

                                # Explicitly check if the LLM instance is available
                                if not llm_instance:
                                    logging.error(
                                        "LLM instance not available for follow-up call")
                                    return full_response

                                # Log before the second LLM call
                                logging.info("Starting follow-up LLM stream")
                                start_time = time.monotonic()

                                # Stream the follow-up response
                                follow_up_accumulated = full_response + "\n\n"
                                follow_up_chunk = None

                                async for chunk in llm_instance.astream(tool_state['messages']):
                                    # Accumulate chunks for the follow-up response
                                    if follow_up_chunk is None:
                                        follow_up_chunk = chunk
                                    else:
                                        follow_up_chunk = follow_up_chunk + chunk

                                    # Extract content
                                    chunk_content = chunk.content if hasattr(
                                        chunk, 'content') else str(chunk)
                                    follow_up_accumulated += chunk_content

                                    # Send the updated full text with each chunk
                                    if callback:
                                        try:
                                            callback(follow_up_accumulated)
                                        except Exception as e:
                                            logging.error(
                                                f"Error in follow-up callback: {e}")

                                # Log after the second LLM call completes
                                end_time = time.monotonic()
                                duration = end_time - start_time
                                logging.info(
                                    f"Follow-up LLM stream completed in {duration:.3f} seconds")

                                # Signal that the tool call is being processed with a new follow-up response
                                # This helps ensure the UI is ready to show the response
                                try:
                                    self.tool_call_handler.tool_call_processing.emit(
                                        tool_name)
                                except Exception as e:
                                    logging.error(
                                        f"Error emitting tool_call_processing signal: {e}")

                                # Update full response with the follow-up
                                full_response = follow_up_accumulated

                                # Save the entire conversation to history
                                message_history = self._get_message_history(
                                    session_id)
                                message_history.add_message(
                                    state['messages'][-1])  # User message

                                # Add tool message
                                tool_content = None
                                if isinstance(result.get('result'), dict) and 'data' in result.get('result'):
                                    tool_content = result.get(
                                        'result').get('data')
                                else:
                                    tool_content = str(result.get('result', {}).get(
                                        'data', 'Tool execution completed'))

                                message_history.add_message(ToolMessage(
                                    content=tool_content, tool_call_id=tool_id))

                                # Add final AI response
                                message_history.add_message(
                                    AIMessage(content=full_response))
                                return full_response
                            else:
                                # Just save the normal conversation if tool was rejected
                                message_history = self._get_message_history(
                                    session_id)
                                message_history.add_message(
                                    state['messages'][-1])
                                message_history.add_message(
                                    AIMessage(content=full_response))

                            # Reset the tool_call_result to avoid reuse
                            self.tool_call_result = None

                        except Exception as e:
                            logging.error(
                                f"Error processing tool call: {e}", exc_info=True)
                            # Save normal conversation on error
                            message_history = self._get_message_history(
                                session_id)
                            message_history.add_message(state['messages'][-1])
                            message_history.add_message(
                                AIMessage(content=full_response))

            # Store in chat history for normal responses (if we didn't already save it during tool call handling)
            message_history = self._get_message_history(session_id)
            message_history.add_message(
                state['messages'][-1])  # Add the user message
            message_history.add_message(
                AIMessage(content=full_response))  # Add the AI response

            # Handle post-processing for compose mode
            if state['mode'] == 'compose':
                processed_response, detected_language = self._extract_code_block(
                    full_response)
                self.detected_language = detected_language
                return processed_response

            return full_response

        except RuntimeError as e:
            # Catch the specific loop error
            if "attached to a different loop" in str(e):
                logging.error(
                    f"Caught asyncio loop error: {e}. This might indicate an issue with nest_asyncio or thread interaction.")
                # Potentially re-raise or handle differently if needed
                raise e  # Re-raise for now
            else:
                logging.error(f"Runtime error during async response: {e}")
                raise e
        except Exception as e:
            logging.exception(
                f"Error during async LLM stream for session {session_id}: {e}")
            # Ensure callback is called with error if provided
            if callback:
                try:
                    callback(f"Error: {e}")
                except Exception as cb_err:
                    logging.error(
                        f"Error calling callback with error message: {cb_err}")
            raise  # Re-raise the exception after logging

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None, session_id: str = "default", selected_text: str = None, mode: str = "chat", image_data: Optional[str] = None) -> str:
        """Synchronous wrapper for get_response_async."""
        try:
            # Get the current running event loop or create a new one if none exists
            # This is important when calling from a synchronous context (like Qt signal handlers)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If a loop is already running (e.g., from nest_asyncio), create a future
                # and run the coroutine within that loop.
                future = asyncio.ensure_future(
                    self.get_response_async(
                        query, callback, model, session_id, selected_text, mode, image_data)
                )
                # This part is tricky. Blocking here might freeze the UI if called from the main thread.
                # Consider running this in a separate thread if blocking is an issue.
                # For now, let's assume nest_asyncio handles the blocking correctly.
                return loop.run_until_complete(future)
            else:
                # If no loop is running, asyncio.run can be used (but nest_asyncio should make this rare)
                return asyncio.run(
                    self.get_response_async(
                        query, callback, model, session_id, selected_text, mode, image_data)
                )
        except RuntimeError as e:
            if "cannot run nested event loops" in str(e) or "cannot schedule new futures after shutdown" in str(e):
                # This might happen if nest_asyncio isn't working as expected or due to shutdown sequences
                logging.error(
                    f"Caught common asyncio runtime error: {e}. Trying fallback loop management.")
                # Fallback: try creating a new loop specifically for this call (might have side effects)
                try:
                    return asyncio.run(
                        self.get_response_async(
                            query, callback, model, session_id, selected_text, mode, image_data)
                    )
                except Exception as fallback_e:
                    logging.error(
                        f"Fallback asyncio.run also failed: {fallback_e}")
                    raise fallback_e from e
            elif "attached to a different loop" in str(e):
                logging.error(
                    f"Caught asyncio loop error: {e}. This might indicate an issue with nest_asyncio or thread interaction.")
                raise e
            else:
                logging.error(f"Runtime error during sync wrapper: {e}")
                raise e
        except Exception as e:
            logging.exception(f"Error in get_response sync wrapper: {e}")
            raise

    def suggest_filename(self, content: str, session_id: str = "default") -> str:
        """Suggest a filename based on content and recent query history."""
        try:
            # Get message history for this session
            message_history = self._get_message_history(session_id)

            # Get the most recent user query from history
            messages = message_history.messages
            recent_query = ""

            # Find the most recent user query
            if messages:
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        recent_query = msg.content
                        break

            # Update the filename suggester's detected language if we have one
            if self.detected_language:
                self.filename_suggester.set_detected_language(
                    self.detected_language)
                # Reset our copy since the suggester will handle it
                self.detected_language = None

            # Get suggestion from the filename suggester
            return self.filename_suggester.suggest_filename(content, recent_query)

        except Exception as e:
            logging.error(
                f"Error in suggest_filename: {str(e)}", exc_info=True)
            # Return default filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"dasi_response_{timestamp}.md"

    def handle_tool_call_result(self, result):
        """Handle the result of a tool call from the tool handler."""
        logging.info(f"Received tool call result: {result}")
        self.tool_call_result = result

        # Use threading.Event.set() instead of asyncio.Event.set()
        try:
            self.tool_call_event.set()
            logging.info("Tool call event set successfully")
        except Exception as e:
            logging.error(f"Error setting tool call event: {e}")
            # Try to recreate the event if it's somehow invalid
            try:
                self.tool_call_event = threading.Event()
                self.tool_call_event.set()
                logging.info("Created new event and set it successfully")
            except Exception as inner_e:
                logging.error(f"Failed to recreate event: {inner_e}")
