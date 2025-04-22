import os
import logging
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Callable
import operator
from pathlib import Path
import asyncio
import nest_asyncio
import re  # Import re for _extract_code_block

# LangChain imports
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_together import ChatTogether
from langchain_xai import ChatXAI
from langchain_community.chat_message_histories import SQLChatMessageHistory

# LangGraph imports
from langgraph.graph import StateGraph, END, START
from langgraph.constants import Send

# Local imports
from ui.settings import Settings
from .web_search_handler import WebSearchHandler
from .vision_handler import VisionHandler
from .llm_factory import create_llm_instance
from .prompts_hub import (
    LANGGRAPH_BASE_SYSTEM_PROMPT,
    COMPOSE_MODE_INSTRUCTION,
    CHAT_MODE_INSTRUCTION,
    FILENAME_SUGGESTION_TEMPLATE,
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
    web_search_query: Optional[str]  # Query used for web search
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

        # Use shared tool call handler from instance manager
        self.tool_call_handler = DasiInstanceManager.get_tool_call_handler()
        self.tool_call_event = asyncio.Event()
        self.tool_call_result = None
        self.tool_call_handler.tool_call_completed.connect(
            self._on_tool_call_completed)

        # Build system prompt
        self._initialize_system_prompt()

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

            logging.info(
                f"Attempting to create LLM instance via factory: provider={provider}, model={model_id}, temp={temperature}")

            # Call the factory function
            llm_instance = create_llm_instance(
                provider=provider,
                model_id=model_id,
                settings=self.settings,
                temperature=temperature,
                # Pass resolved info which might contain base_url etc.
                model_info=resolved_model_info
            )

            if llm_instance:
                self.llm = llm_instance
                self.current_provider = provider
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

        # <<< MODIFIED SECTION: Incorporate Web Search/Scrape Results >>>
        web_search_results = state.get('web_search_results')
        final_query_text = updated_state['query']  # Start with original query

        # If there's a tool call result from user confirmation, add it to the message
        tool_call_result = state.get('tool_call_result')
        if tool_call_result:
            logging.info(
                f"Adding tool call result to messages: {tool_call_result}")
            tool_name = tool_call_result.get('tool', 'unknown')
            result = tool_call_result.get('result', {})

            if tool_name == 'web_search' and isinstance(result, dict) and result.get('status') == 'success':
                # Format similar to web search results for consistency
                search_data = result.get('data', 'No results found')
                final_query_text += f"\n\n=====TOOL_RESULT=====<web_search>\n{search_data}\n======================="
            elif result == 'rejected':
                # Inform the LLM that the user rejected the tool call
                final_query_text += "\n\n=====TOOL_RESULT=====<rejected>\nThe user rejected the tool call. Please proceed without using external tools.\n======================="
            else:
                # Generic format for other tools or error cases
                final_query_text += f"\n\n=====TOOL_RESULT=====<{tool_name}>\n{result}\n======================="

            # Clear the tool call result after using it
            updated_state['tool_call_result'] = None

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

        # <<< END MODIFIED SECTION >>>

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
            elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                if msg.type == 'human':
                    typed_history.append(HumanMessage(content=msg.content))
                elif msg.type == 'ai':
                    typed_history.append(AIMessage(content=msg.content))

        messages.extend(typed_history)

        # Start constructing the final query content
        # Already contains web results if applicable
        final_query_content = final_query_text

        # Append selected text if present AND not already added via web blocks
        if state.get('selected_text') and "=====SELECTED_TEXT=====" not in final_query_content:
            final_query_content += f"\\n\\n=====SELECTED_TEXT=====<text selected by the user>\\n{state['selected_text']}\\n======================="

        # Determine final message type based on image and vision description
        image_data = state.get('image_data')
        vision_description = state.get('vision_description')
        is_vision_model_configured = self.vision_handler.has_vision_model_configured()

        if vision_description:
            # Case 1: Vision model success - Append description, send text-only
            logging.info(
                "Vision description present. Appending to text query.")
            final_query_content += f"\\n\\n=====VISUAL_DESCRIPTION=====<description generated by vision model>\\n{vision_description}\\n======================="
            query_message = HumanMessage(content=final_query_content)

        elif image_data:
            # Image present, but no description generated
            if is_vision_model_configured:
                # Case 3: Vision model configured but failed - Send text-only with error note
                logging.warning(
                    "Image present, vision model configured but failed. Adding system note.")
                final_query_content += "\\n\\n=====SYSTEM_NOTE=====\\n(Failed to process the provided visual input using the configured vision model.)\\n====================="
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
            query_message = HumanMessage(content=final_query_content)

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

            # Tool call detection (simple example: look for special marker)
            # In production, use OpenAI function calling or similar
            if '<<TOOL:' in final_response:
                logging.info("Tool call marker detected in LLM response")
                import json
                import re
                match = re.search(
                    r'<<TOOL:\s*(\w+)\s*(\{.*?\})>>', final_response)
                if match:
                    tool_name = match.group(1)
                    tool_args_str = match.group(2)
                    logging.info(
                        f"Parsed tool call: {tool_name} with args: {tool_args_str}")
                    try:
                        tool_args = json.loads(tool_args_str)
                        updated_state['pending_tool_call'] = {
                            'tool': tool_name, 'args': tool_args}
                        # Remove tool call marker from response
                        cleaned_response = re.sub(
                            r'<<TOOL:.*?>>', '', final_response).strip()
                        updated_state['response'] = cleaned_response
                        logging.info(
                            f"Tool call for {tool_name} added to state, routing to tool_call node")
                        return updated_state
                    except json.JSONDecodeError as e:
                        logging.error(f"Error parsing tool args JSON: {e}")
                else:
                    logging.warning(
                        "Tool call marker found but couldn't parse the format")
            else:
                logging.debug("No tool call markers found in response")

            # Normal response
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
        graph.add_node("tool_call", self.tool_call_node)  # New node
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "parse_query")

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
        graph.add_edge("vision_processing", "prepare_messages")
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
        # After tool_call, go back to prepare_messages (tool result in state)
        graph.add_edge("tool_call", "prepare_messages")
        graph.add_edge("prepare_messages", "generate_response")
        graph.add_edge("generate_response", END)
        logging.info("LangGraph graph definition built with tool_call node.")
        return graph

    async def tool_call_node(self, state):
        """LangGraph node for tool calling with user confirmation."""
        # Assume tool call info is in state['pending_tool_call']
        tool_call = state.get('pending_tool_call')
        if not tool_call:
            # No tool call, just return state
            return state
        tool_name = tool_call.get('tool')
        tool_args = tool_call.get('args', {})
        # Emit to UI and wait for user
        self.tool_call_handler.request_tool_call(tool_name, tool_args)
        self.tool_call_event.clear()
        await self.tool_call_event.wait()
        # After user responds, update state with result
        result = self.tool_call_result
        new_state = state.copy()
        new_state['tool_call_result'] = result
        return new_state

    def _on_tool_call_completed(self, result):
        self.tool_call_result = result
        self.tool_call_event.set()

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

            full_response = ""
            stream = self.app.astream(initial_state, config=config)

            # --- Stream Processing ---
            # Run the streaming part explicitly in the current loop
            stream_task = loop.create_task(
                self._process_stream(stream, callback))
            await stream_task  # Wait for the streaming task to complete

            # The final state should contain the complete response after streaming
            # However, LangGraph streaming might not update the final state directly in the iterator
            # We accumulate the response via the callback or within _process_stream
            # Let's retrieve the final state to check if 'response' is updated
            # Note: This might require adjustments based on LangGraph's async streaming behavior

            # It seems LangGraph's astream might yield intermediate states.
            # Let's try getting the final accumulated response from the task result.
            final_response_from_task = stream_task.result()
            if final_response_from_task:
                full_response = final_response_from_task
            else:
                # Fallback or alternative way to get the final state if needed
                # This part might be complex depending on how LangGraph manages state in async streams
                logging.warning(
                    "Could not retrieve final response from stream task result. Accumulated response might be incomplete.")
                # We rely on the callback having accumulated the full_response if the task doesn't return it

            logging.info(
                f"Final response for session {session_id}: {full_response[:100]}...")
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

    async def _process_stream(self, stream, callback: Optional[Callable[[str], None]] = None) -> str:
        """Helper coroutine to process the LangGraph stream and call the callback."""
        full_response = ""
        try:
            async for event in stream:
                # Determine the type of event and extract relevant data
                # LangGraph streams yield dictionaries where keys are node names
                # and values are the outputs of those nodes (or the state itself)
                logging.debug(f"Stream event: {event}")

                # Check if the event contains the final response or intermediate steps
                # Adjust this logic based on your graph structure and node names
                response_chunk = None

                # Look for response chunks in the event data
                # This depends heavily on your graph structure and node names
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict):
                        # Check common places for response chunks
                        if "response" in node_output and isinstance(node_output["response"], str):
                            # Check if it's an update to the final response
                            if node_output["response"] != full_response:
                                new_part = node_output["response"][len(
                                    full_response):]
                                if new_part:
                                    response_chunk = new_part
                                    # Update tracked full response
                                    full_response = node_output["response"]
                                    break  # Found response chunk in this node output
                        elif "messages" in node_output and isinstance(node_output["messages"], list):
                            # Check the last message if it's an AIMessage chunk
                            if node_output["messages"]:
                                last_message = node_output["messages"][-1]
                                if isinstance(last_message, AIMessage) and isinstance(last_message.content, str):
                                    # Check if it's a new chunk added to the last AI message
                                    # This logic assumes streaming updates the content of the last message
                                    current_ai_content = last_message.content
                                    # Find the previous AI message content to diff (more complex state needed)
                                    # Simple approach: assume any AI message content is part of the stream
                                    # This might repeat content if the full message is sent multiple times
                                    # A better approach relies on LangChain's streaming format if available directly
                                    # Let's assume the 'generate_response' node output might be the direct chunk
                                    pass  # Avoid complex message diffing for now

                # Specific check for the likely response generation node
                # Replace 'generate_response_node_name' with the actual name of your LLM call node
                generate_node_name = "generate_response"  # Assuming this is the node name
                if generate_node_name in event:
                    node_output = event[generate_node_name]
                    # Check if the output is directly the AIMessageChunk or similar streaming object
                    if hasattr(node_output, 'content'):
                        response_chunk = node_output.content
                        if response_chunk:
                            full_response += response_chunk  # Accumulate here if chunks are delta
                    # Fallback check if node output is a dict containing the response
                    elif isinstance(node_output, dict) and "response" in node_output:
                        # This logic assumes the full response is sent each time, calculate delta
                        current_full = node_output["response"]
                        if isinstance(current_full, str) and current_full != full_response:
                            new_part = current_full[len(full_response):]
                            if new_part:
                                response_chunk = new_part
                                full_response = current_full  # Update tracked full response

                # Fallback: If the event itself is a string (less likely with LangGraph state updates)
                elif isinstance(event, str):
                    response_chunk = event

                # If a chunk was identified, process and callback
                if response_chunk:
                    # full_response += response_chunk # Accumulate only if chunk represents new part
                    if callback:
                        try:
                            # Ensure callback runs in the correct context if needed
                            # loop = asyncio.get_running_loop()
                            # loop.call_soon_threadsafe(callback, response_chunk) # If callback needs main thread
                            # Direct call if callback is thread-safe/async-safe
                            callback(response_chunk)
                        except Exception as cb_err:
                            logging.error(
                                f"Error in stream callback: {cb_err}")

            logging.debug("Stream finished.")
            return full_response
        except Exception as e:
            logging.exception(f"Error processing LLM stream: {e}")
            if callback:
                try:
                    callback(f"Error during streaming: {e}")
                except Exception as cb_err:
                    logging.error(
                        f"Error calling callback with stream error message: {cb_err}")
            return full_response  # Return whatever was accumulated before the error

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

            # Check if we have a detected language that would suggest a better extension
            file_extension = ".md"  # Default extension
            extension_hint = ""

            if self.detected_language:
                # Map language to file extension
                extension_map = {
                    "python": ".py",
                    "py": ".py",
                    "javascript": ".js",
                    "js": ".js",
                    "typescript": ".ts",
                    "ts": ".ts",
                    "java": ".java",
                    "c": ".c",
                    "cpp": ".cpp",
                    "c++": ".cpp",
                    "csharp": ".cs",
                    "c#": ".cs",
                    "go": ".go",
                    "rust": ".rs",
                    "ruby": ".rb",
                    "php": ".php",
                    "swift": ".swift",
                    "kotlin": ".kt",
                    "html": ".html",
                    "css": ".css",
                    "sql": ".sql",
                    "shell": ".sh",
                    "bash": ".sh",
                    "json": ".json",
                    "xml": ".xml",
                    "yaml": ".yaml",
                    "yml": ".yml",
                    "markdown": ".md",
                    "md": ".md",
                    "text": ".txt",
                    "plaintext": ".txt",
                }

                if self.detected_language.lower() in extension_map:
                    file_extension = extension_map[self.detected_language.lower(
                    )]
                    extension_hint = f"(use {file_extension} extension for this {self.detected_language} code)"

            # Create the prompt for filename suggestion using the template from prompts hub
            filename_query = FILENAME_SUGGESTION_TEMPLATE.format(
                file_extension=file_extension,
                extension_hint=extension_hint,
                recent_query=recent_query,
                content=content[:500]
            )

            # Create direct message list
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=filename_query)
            ]

            # Invoke the LLM directly
            response = self.llm.invoke(messages)
            suggested_filename = response.content.strip().strip('"').strip("'").strip()

            # Ensure correct extension
            if not suggested_filename.endswith(file_extension):
                if '.' in suggested_filename:
                    suggested_filename = suggested_filename.split('.')[0]
                suggested_filename += file_extension

            # Reset detected language
            self.detected_language = None

            return suggested_filename

        except Exception as e:
            logging.error(
                f"Error suggesting filename: {str(e)}", exc_info=True)
            # Return default filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Use stored language for extension if available
            extension = ".md"
            # Simplified extension logic based on potential language hints
            lang_lower = (self.detected_language or "").lower()
            if lang_lower in ["python", "py"]:
                extension = ".py"
            elif lang_lower in ["javascript", "js"]:
                extension = ".js"
            elif lang_lower in ["typescript", "ts"]:
                extension = ".ts"
            elif lang_lower in ["html"]:
                extension = ".html"
            elif lang_lower in ["css"]:
                extension = ".css"
            elif lang_lower in ["json"]:
                extension = ".json"
            elif lang_lower in ["yaml", "yml"]:
                extension = ".yaml"
            elif lang_lower in ["shell", "bash", "sh"]:
                extension = ".sh"
            elif lang_lower in ["sql"]:
                extension = ".sql"
            # Add other common languages as needed
            elif lang_lower in ["text", "plaintext"]:
                extension = ".txt"

            # Reset detected language
            self.detected_language = None

            return f"dasi_response_{timestamp}{extension}"
