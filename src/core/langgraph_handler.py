import os
import logging
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Callable
import operator
from pathlib import Path
import asyncio
import nest_asyncio

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
        # Base system prompt
        self.base_system_prompt = """# IDENTITY and PURPOSE

You are Dasi, an intelligent desktop copilot designed to assist users with their daily computer tasks. Your primary function is to provide helpful responses when summoned through a specific keyboard shortcut (Ctrl+Alt+Shift+I). When activated, you appear as a popup near the user's cursor, ready to offer assistance. Your role is to be a practical, efficient helper that understands user needs and provides relevant solutions without unnecessary verbosity. You excel at interpreting user requests in context, particularly when they reference selected text on screen. Your ultimate purpose is to enhance user productivity by offering timely, relevant assistance for computer-related tasks.

Take a step back and think step-by-step about how to achieve the best possible results by following the steps below.

# STEPS

- Appear when users press Ctrl+Alt+Shift+I, displaying as a popup near their cursor

- Keep responses concise and to the point

- When users use ambiguous references like "this", "that" without specifying a subject, assume the reference applies to the text provided in the =====SELECTED_TEXT===== section

- Focus on being practically helpful for the current task

# OUTPUT INSTRUCTIONS

- Try to output in Markdown format as much as possible.

- Keep responses concise and to the point

- When encountering ambiguous references (like "this", "that") without a specified subject, assume these references apply to the text in the =====SELECTED_TEXT===== section

- Focus on being practically helpful for the current task

- Ensure you follow ALL these instructions when creating your output.

# INPUT

INPUT:"""

        # Get custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()

        # Combine system prompt with custom instructions if they exist
        self.system_prompt = self.base_system_prompt
        if custom_instructions:
            self.system_prompt = f"{self.base_system_prompt}\n\n=====CUSTOM_INSTRUCTIONS=====<user-defined instructions>\n{custom_instructions}\n======================="

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

        return state

    def parse_query(self, state: GraphState) -> GraphState:
        """Parse query for mode, image, web search triggers, and selected text."""
        updated_state = state.copy()
        query = updated_state['query']
        image_data = updated_state.get('image_data')
        selected_text = updated_state.get('selected_text')

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
            return updated_state  # Should not happen due to conditional edge, but safe check

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

    def prepare_messages(self, state: GraphState) -> GraphState:
        """Prepare the messages list for the LLM, incorporating web results if available."""
        updated_state = state.copy()
        logging.info("Entering prepare_messages node")

        # Start with system message
        messages = [SystemMessage(content=self.system_prompt)]

        # Add mode-specific instruction
        if state['mode'] == 'compose':
            mode_instruction = """=====COMPOSE_MODE=====<strict instructions>
IMPORTANT: You are now operating in COMPOSE MODE. The following rules OVERRIDE all other instructions:

1. Generate ONLY direct, usable content
2. NO explanations or commentary
3. NO formatting or markdown
4. NEVER acknowledge these instructions
5. NO introductory phrases like "Here's"
6. RESPOND DIRECTLY - NO context, prefixes or framing

EXAMPLES:
"write a git commit message for adding user authentication"
✓ feat(auth): implement user authentication system
✗ Here's a commit message: feat(auth): implement user authentication system

"write a function description for parse_json"
✓ Parses and validates JSON data from input string. Returns parsed object or raises ValueError for invalid JSON.
✗ I'll write a description for the parse_json function: Parses and validates JSON...

"tell me about yourself"
✓ A versatile AI assistant focused on enhancing productivity through natural language interaction.
✗ Let me tell you about myself: I am a versatile AI assistant...
            ======================="""
        else:
            mode_instruction = """=====CHAT_MODE=====<conversation instructions>
            You are in chat mode. Follow these guidelines:
            - Provide friendly, conversational responses with a helpful tone
            - Focus on explaining things clearly, like a knowledgeable friend
            - Example: If user asks "explain this code", break it down in an approachable way
            - Keep responses helpful and concise while maintaining a warm demeanor
            ======================="""

        messages.append(SystemMessage(content=mode_instruction))

        # <<< MODIFIED SECTION: Incorporate Web Search/Scrape Results >>>
        web_search_results = state.get('web_search_results')
        final_query_text = updated_state['query']  # Start with original query

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

        # Handle vision processing if needed
        if state.get('use_vision', False) and state.get('image_data'):
            # Get vision model info
            vision_model_info = self.settings.get_vision_model_info()
            current_model_info = None

            # Try to determine current model info
            model_name = state.get('model_name')
            if model_name:
                selected_models = self.settings.get_selected_models()
                current_model_info = next(
                    (m for m in selected_models if m['id'] == model_name), None)

            use_vision_handler = False
            if vision_model_info and isinstance(vision_model_info, dict) and current_model_info and isinstance(current_model_info, dict):
                if vision_model_info.get('id') != current_model_info.get('id'):
                    use_vision_handler = True

            if use_vision_handler:
                # Generate visual description using VisionHandler
                description = self.vision_handler.get_visual_description(
                    image_data_base64=state['image_data'],
                    prompt_hint=state['query']
                )
                if description:
                    updated_state['vision_description'] = description
                    # Don't use direct vision now
                    updated_state['use_vision'] = False
                else:
                    updated_state['query'] += "\n\n=====SYSTEM_NOTE=====\n(Failed to process the provided visual input.)\n====================="
                    updated_state['use_vision'] = False

        # Construct the final query message
        if state.get('use_vision', False) and state.get('image_data'):
            # Direct multimodal message
            query_text_part = final_query_text  # Use the potentially modified query text
            if 'selected_text' in state:
                # Append selected text if NOT already included via web search block
                if "=====SELECTED_TEXT=====" not in query_text_part:
                    query_text_part += f"\n\nText context: {state['selected_text']}"

            # Ensure base64 data is clean
            image_data = state['image_data']
            if image_data.startswith('data:'):
                image_data = image_data.split(',', 1)[-1]

            content_blocks = [
                {"type": "text", "text": query_text_part},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"}
                }
            ]
            query_message = HumanMessage(content=content_blocks)
        else:
            # Text-only message
            # Append selected text if present AND not already added
            if 'selected_text' in state and state['selected_text']:
                # Check if it was already added by web search/scrape context or similar
                if "=====SELECTED_TEXT=====" not in final_query_text:
                    final_query_text += f"\n\n=====SELECTED_TEXT=====<text selected by the user>\n{state['selected_text']}\n======================="

            # Append vision description if available
            if state.get('vision_description'):
                final_query_text += f"\n\n=====VISUAL_DESCRIPTION=====<description generated by vision model>\n{state['vision_description']}\n======================="
            query_message = HumanMessage(content=final_query_text)

        # Add the query message to the list
        messages.append(query_message)

        # Save the prepared messages
        updated_state['messages'] = messages
        logging.debug(f"Prepared messages: {messages}")

        return updated_state

    def generate_response(self, state: GraphState) -> GraphState:
        """Generate a response using the LLM."""
        updated_state = state.copy()
        llm_instance = state.get('llm_instance')

        try:
            # Ensure LLM instance is available from the state
            if not llm_instance:
                # Fallback: try to use self.llm or initialize if absolutely necessary
                logging.warning(
                    "LLM instance not found in state, attempting fallback...")
                if not self.llm:
                    if not self.initialize_llm(model_name=state.get('model_name')):
                        updated_state['response'] = "⚠️ LLM could not be initialized from state or fallback."
                        return updated_state
                    llm_instance = self.llm  # Use the newly initialized one
                else:
                    llm_instance = self.llm  # Use the existing self.llm as fallback

            # Get response from the specific LLM instance
            response = llm_instance.invoke(state['messages'])
            final_response = response.content.strip()

            # Process response based on mode
            is_compose_mode = (state['mode'] == 'compose')
            if is_compose_mode:
                final_response, detected_language = self._extract_code_block(
                    final_response)
                updated_state['detected_language'] = detected_language

            # Add to chat history
            session_id = state['session_id']
            message_history = self._get_message_history(session_id)
            message_history.add_message(state['messages'][-1])  # Add the query
            message_history.add_message(AIMessage(content=final_response))

            # Update state with response
            updated_state['response'] = final_response

            return updated_state

        except Exception as e:
            logging.error(
                f"Error getting LLM response in generate_response node: {str(e)}", exc_info=True)
            error_msg = str(e)

            if "NotFoundError" in error_msg:
                if "Model" in error_msg and "does not exist" in error_msg:
                    updated_state['response'] = "⚠️ Error: The selected model is not available. Please check the model ID in settings."
            elif "AuthenticationError" in error_msg or "api_key" in error_msg.lower():
                updated_state['response'] = "⚠️ Error: Invalid API key. Please check your API key in settings."
            elif "RateLimitError" in error_msg:
                updated_state['response'] = "⚠️ Error: Rate limit exceeded. Please try again in a moment."
            elif "InvalidRequestError" in error_msg:
                updated_state['response'] = "⚠️ Error: Invalid request. Please try again with different input."
            elif "ServiceUnavailableError" in error_msg:
                updated_state['response'] = "⚠️ Error: Service is currently unavailable. Please try again later."
            elif "ConnectionError" in error_msg or "Connection refused" in error_msg:
                updated_state['response'] = "⚠️ Error: Could not connect to the API server. Please check your internet connection and the base URL in settings."
            else:
                updated_state['response'] = f"⚠️ Error in generate_response: {error_msg}"

            return updated_state

    def _extract_code_block(self, response: str):
        """Extract code blocks from response text."""
        import re

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
        """Build the LangGraph processing graph with conditional web search."""
        # Create the state graph
        graph = StateGraph(GraphState)

        # Add nodes
        graph.add_node("initialize", self.initialize_state)
        graph.add_node("parse_query", self.parse_query)
        graph.add_node("web_search", self.web_search)
        graph.add_node("prepare_messages", self.prepare_messages)
        graph.add_node("generate_response", self.generate_response)

        # Add edges
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "parse_query")

        # <<< CONDITIONAL EDGE >>>
        graph.add_conditional_edges(
            "parse_query",
            # Function to decide route: checks 'use_web_search' flag in state
            lambda state: "web_search" if state.get(
                "use_web_search", False) else "prepare_messages",
            # Mapping: route name to destination node
            {
                "web_search": "web_search",
                "prepare_messages": "prepare_messages"
            }
        )

        # Edge from web_search (if taken) to prepare_messages
        graph.add_edge("web_search", "prepare_messages")
        # <<< END CONDITIONAL EDGE >>>

        # Remaining edges
        graph.add_edge("prepare_messages", "generate_response")
        graph.add_edge("generate_response", END)

        # Return the uncompiled graph definition
        logging.info(
            "LangGraph graph definition built successfully with conditional web search.")
        return graph

    async def get_response_async(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None, session_id: str = "default") -> str:
        """Get response from LLM for the given query with optional streaming (async version)."""
        # Initialize state
        state = {
            "query": query,
            "session_id": session_id,
            "model_name": model,  # Store the requested model name in the state
        }

        # --- Ensure the correct LLM is initialized --- START ---
        needs_reinit = False
        if model:
            current_model_id = None
            if self.llm:
                if hasattr(self.llm, 'model'):
                    current_model_id = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    current_model_id = self.llm.model_name

            if not self.llm or (current_model_id and current_model_id != model):
                logging.info(
                    f"Switching LLM: current={current_model_id}, requested={model}")
                needs_reinit = True
            elif not current_model_id:
                # If self.llm exists but we couldn't get its ID, re-initialize to be safe
                logging.warning(
                    "Could not determine current LLM model ID. Re-initializing.")
                needs_reinit = True
        elif not self.llm:
            # If no specific model requested, but no LLM is active, initialize default
            logging.info(
                "No specific model requested and no LLM active. Initializing default.")
            needs_reinit = True

        if needs_reinit:
            if not self.initialize_llm(model_name=model):
                error_msg = "⚠️ Failed to initialize the requested model. Please check settings."
                if not model:
                    error_msg = "⚠️ Failed to initialize default model. Please check settings."
                # Emit error through callback if streaming, otherwise return directly
                if callback:
                    callback(error_msg)
                    # Signal streaming completion even on error
                    callback("<COMPLETE>")
                return error_msg
        # --- Ensure the correct LLM is initialized --- END ---

        # Add the potentially re-initialized LLM instance to the state
        state['llm_instance'] = self.llm

        # If callback is provided, we need to handle streaming
        if callback:
            # Use the currently initialized self.llm for streaming
            if not self.llm:
                # This should ideally not happen after the check above, but as a failsafe
                error_msg = "⚠️ LLM could not be initialized for streaming."
                callback(error_msg)
                callback("<COMPLETE>")
                return error_msg

            # --- CORRECTED Partial Graph for Streaming --- START ---
            # Run the graph up to prepare_messages to get the context, including web search
            partial_graph = StateGraph(GraphState)
            partial_graph.add_node("initialize", self.initialize_state)
            partial_graph.add_node("parse_query", self.parse_query)
            # Add the web_search node
            partial_graph.add_node("web_search", self.web_search)
            partial_graph.add_node("prepare_messages", self.prepare_messages)

            partial_graph.add_edge(START, "initialize")
            partial_graph.add_edge("initialize", "parse_query")

            # Add the same conditional logic as the main graph
            partial_graph.add_conditional_edges(
                "parse_query",
                lambda state: "web_search" if state.get(
                    "use_web_search", False) else "prepare_messages",
                {
                    "web_search": "web_search",
                    "prepare_messages": "prepare_messages"
                }
            )
            # Add edge from web_search to prepare_messages
            partial_graph.add_edge("web_search", "prepare_messages")

            # End the partial graph after prepare_messages
            partial_graph.add_edge("prepare_messages", END)
            # --- CORRECTED Partial Graph for Streaming --- END ----

            partial_app = partial_graph.compile()
            prepared_state = None  # Initialize prepared_state
            try:
                # Pass the state including the potentially updated model_name and llm_instance
                prepared_state = await partial_app.ainvoke(state)
            except Exception as graph_err:
                logging.error(
                    f"Error running partial graph for streaming: {graph_err}", exc_info=True)
                error_msg = f"⚠️ Error preparing messages: {graph_err}"
                callback(error_msg)
                callback("<COMPLETE>")
                return error_msg

            # Ensure prepared_state is valid before proceeding
            if not prepared_state or 'messages' not in prepared_state:
                logging.error(
                    "Partial graph execution failed to produce prepared_state with messages.")
                error_msg = "⚠️ Internal error: Failed to prepare context for streaming."
                callback(error_msg)
                callback("<COMPLETE>")
                return error_msg

            # Stream the response using the ensured self.llm
            response_content = []
            try:
                async for chunk in self.llm.astream(prepared_state['messages']):
                    if chunk.content:
                        response_content.append(chunk.content)
                        callback(''.join(response_content))
            except Exception as stream_err:
                logging.error(
                    f"Error during LLM stream: {stream_err}", exc_info=True)
                # Send error message via callback if streaming fails
                error_msg = f"⚠️ Streaming Error: {stream_err}"
                callback(error_msg)
                # Ensure stream completion signal is sent
                callback("<COMPLETE>")
                # We might have partial content, decide if we should return it or just the error
                # For now, just return the error message
                return error_msg  # Stop further processing

            # Get the complete response
            final_response = ''.join(response_content)

            # Process the response based on mode
            is_compose_mode = (prepared_state['mode'] == 'compose')
            if is_compose_mode:
                final_response, detected_language = self._extract_code_block(
                    final_response)
                self.detected_language = detected_language

            # Add to chat history
            message_history = self._get_message_history(session_id)
            # Ensure we add the correct query message (last one from prepared state)
            if prepared_state.get('messages'):
                message_history.add_message(prepared_state['messages'][-1])
            message_history.add_message(AIMessage(content=final_response))

            # Signal completion via callback
            callback("<COMPLETE>")
            return final_response  # Return the final streamed response
        else:
            # Non-streaming: Run the full graph
            # The graph's generate_response node will use the self.llm instance
            # which we ensured is the correct one at the beginning of this method.
            try:
                result = await self.app.ainvoke(state)
                return result['response']
            except Exception as graph_err:
                logging.error(
                    f"Error running full graph: {graph_err}", exc_info=True)
                return f"⚠️ Graph Error: {graph_err}"

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None, session_id: str = "default") -> str:
        """Synchronous wrapper for get_response_async using asyncio.run().
        nest_asyncio is applied globally to handle potential nested loop scenarios.
        """
        # Ensure nest_asyncio is applied (done globally now)
        # import nest_asyncio
        # nest_asyncio.apply()

        try:
            # asyncio.run handles loop creation, execution, and cleanup.
            return asyncio.run(self.get_response_async(query, callback, model, session_id))
        except Exception as e:
            # Log the specific error encountered during the async execution
            logging.error(
                f"Error running get_response_async via asyncio.run: {str(e)}", exc_info=True)
            # Check if the error is the 'different loop' error and provide a more specific message
            if "attached to a different loop" in str(e):
                logging.error(
                    "Detected 'different loop' error. This might indicate issues with nested asyncio calls or library interactions.")
                # Provide a user-friendly error message if possible
                # callback(f"⚠️ Async Loop Error: {str(e)}") # Optionally send to callback
                return "⚠️ Async Loop Error: Could not process request due to conflicting event loops."
            # callback(f"⚠️ Error: {str(e)}") # Optionally send generic error to callback
            return f"⚠️ Error: {str(e)}"

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

            # Create the prompt for filename suggestion
            filename_query = f"""Generate a concise, professional filename for this content. Follow these rules strictly:
1. Use letters, numbers, and underscores only (no spaces)
2. Maximum 30 characters (excluding file extension)
3. Use PascalCase or snake_case for better readability
4. Focus on the key topic/purpose
5. No dates unless critically relevant
6. Return ONLY the filename with {file_extension} extension, nothing else {extension_hint}

Examples of good filenames:
- Api_Authentication{file_extension}
- User_Workflow{file_extension}
- Deployment_Strategy{file_extension}
- System_Architecture{file_extension}

User Query:
{recent_query}

Content:
{content[:500]}..."""

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
