import os
import logging
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Callable
import operator
from pathlib import Path

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
from web_search_handler import WebSearchHandler
from vision_handler import VisionHandler


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
    web_search_results: Optional[Dict]
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
        """Initialize the LLM with the current API key and specified model/info."""
        try:
            # Reload settings
            self.settings.load_settings()

            # Determine model info based on inputs
            if model_info and isinstance(model_info, dict):
                logging.info(
                    f"Initializing LLM using provided model info: {model_info.get('id', 'N/A')}, provider: {model_info.get('provider', 'N/A')}")
            elif model_name:
                selected_models = self.settings.get_selected_models()
                # Log available models for debugging
                model_ids = [m['id'] for m in selected_models]
                logging.info(f"Available selected model IDs: {model_ids}")

                # Find model by exact ID match
                model_info = next(
                    (m for m in selected_models if m['id'] == model_name), None)

                # If model not found and it's a Google model with 'models/' prefix
                if not model_info and model_name.startswith('models/'):
                    # Try to find by full path for Google models
                    logging.info(
                        f"Looking up Google model by full path: {model_name}")
                    model_info = next(
                        (m for m in selected_models if m['id'] == model_name), None)

                # If still not found, try partial match
                if not model_info and '/' in model_name:
                    base_name = model_name.split('/')[-1]
                    logging.info(
                        f"Model '{model_name}' not found by exact match. Trying base name: {base_name}")
                    for m in selected_models:
                        if m['id'].endswith(f"/{base_name}"):
                            model_info = m
                            logging.info(
                                f"Found model by partial match: {m['id']}, provider: {m['provider']}")
                            break

                if not model_info:
                    logging.error(
                        f"Model '{model_name}' not found in selected models.")
                    return False

                logging.info(f"Selected model info: {model_info}")
            else:
                default_model_id = self.settings.get('models', 'default_model')
                if not default_model_id:
                    selected_models = self.settings.get_selected_models()
                    if selected_models:
                        model_info = selected_models[0]
                        logging.info(
                            f"Using first selected model as default: {model_info['id']}, provider: {model_info['provider']}")
                    else:
                        logging.error(
                            "No default model set and no models selected.")
                        return False
                else:
                    selected_models = self.settings.get_selected_models()
                    model_info = next(
                        (m for m in selected_models if m['id'] == default_model_id), None)
                    if not model_info:
                        if selected_models:
                            model_info = selected_models[0]
                            logging.info(
                                f"Default model not found, using first model: {model_info['id']}, provider: {model_info['provider']}")
                        else:
                            return False

            # Get provider and model ID
            provider = model_info['provider']
            model_id = model_info['id']

            # Additional logging for debugging
            logging.info(
                f"Initializing LLM with provider: {provider}, model: {model_id}")

            # Get temperature
            temperature = self.settings.get(
                'general', 'temperature', default=0.7)

            # Initialize appropriate LLM based on provider
            if provider == 'google':
                logging.info(f"Creating Google Gemini model: {model_id}")
                self.llm = ChatGoogleGenerativeAI(
                    model=model_id,
                    google_api_key=self.settings.get_api_key('google'),
                    temperature=temperature,
                )
            elif provider == 'openai':
                if 'gpt-4o' in model_id.lower() or 'vision' in model_id.lower():
                    self.llm = ChatOpenAI(
                        model=model_id,
                        temperature=temperature,
                        streaming=True,
                        openai_api_key=self.settings.get_api_key('openai'),
                        max_tokens=4096,
                    )
                else:
                    self.llm = ChatOpenAI(
                        model=model_id,
                        temperature=temperature,
                        streaming=True,
                        openai_api_key=self.settings.get_api_key('openai'),
                    )
            elif provider == 'ollama':
                self.llm = ChatOllama(
                    model=model_id,
                    temperature=temperature,
                    base_url="http://localhost:11434",
                )
            elif provider == 'groq':
                logging.info(f"Creating Groq model: {model_id}")
                self.llm = ChatGroq(
                    model=model_id,
                    groq_api_key=self.settings.get_api_key('groq'),
                    temperature=temperature,
                )
            elif provider == 'anthropic':
                if 'claude-3' in model_id.lower():
                    self.llm = ChatAnthropic(
                        model=model_id,
                        anthropic_api_key=self.settings.get_api_key(
                            'anthropic'),
                        temperature=temperature,
                        streaming=True,
                        max_tokens=4096,
                    )
                else:
                    self.llm = ChatAnthropic(
                        model=model_id,
                        anthropic_api_key=self.settings.get_api_key(
                            'anthropic'),
                        temperature=temperature,
                        streaming=True,
                    )
            elif provider == 'deepseek':
                api_key = self.settings.get_api_key('deepseek')
                os.environ["DEEPSEEK_API_KEY"] = api_key
                self.llm = ChatDeepSeek(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                )
            elif provider == 'together':
                self.llm = ChatTogether(
                    model=model_id,
                    together_api_key=self.settings.get_api_key('together'),
                    temperature=temperature,
                )
            elif provider == 'xai':
                self.llm = ChatXAI(
                    model=model_id,
                    xai_api_key=self.settings.get_api_key('xai'),
                    temperature=temperature,
                )
            elif provider == 'custom_openai' or provider.startswith('custom_openai_'):
                base_url = self.settings.get('models', provider, 'base_url')
                api_key = self.settings.get_api_key(provider)

                if not base_url or not api_key:
                    logging.error(
                        f"Missing configuration for custom OpenAI provider: {provider}")
                    return False

                self.llm = ChatOpenAI(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                    openai_api_key=api_key,
                    base_url=base_url,
                )
            else:  # OpenRouter
                headers = {
                    'HTTP-Referer': 'https://github.com/mithuns/dasi',
                    'X-Title': 'Dasi',
                    'Content-Type': 'application/json'
                }

                self.llm = ChatOpenAI(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                    openai_api_key=self.settings.get_api_key('openrouter'),
                    base_url="https://openrouter.ai/api/v1",
                    default_headers=headers
                )

            self.current_provider = provider
            logging.info(
                f"Successfully initialized {provider} model: {model_id}")
            return True

        except Exception as e:
            logging.error(f"Error initializing LLM: {str(e)}", exc_info=True)
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
        """Parse the input query and extract context information."""
        query = state['query']
        parsed_state = state.copy()

        # Check for web search commands
        if query.strip().startswith('#web ') or "#web" in query:
            parsed_state['use_web_search'] = True
            logging.info(f"Web search detected in query: {query}")

        # Check if query contains context information
        if "Context:" in query:
            context_section, actual_query = query.split("\n\nQuery:\n", 1)
            context_section = context_section.replace("Context:\n", "").strip()

            # Parse selected text
            if "Selected Text:" in context_section:
                selected_text = context_section.split("Selected Text:\n", 1)[1]
                selected_text = selected_text.split("\n\n", 1)[0].strip()
                parsed_state['selected_text'] = selected_text

            # Parse selected text with delimiters
            if "=====SELECTED_TEXT=====" in context_section:
                selected_text = context_section.split(
                    "=====SELECTED_TEXT=====", 1)[1]
                selected_text = selected_text.split(
                    "=======================", 1)[0].strip()
                if "<" in selected_text and ">" in selected_text:
                    selected_text = selected_text.split(">", 1)[1].strip()
                parsed_state['selected_text'] = selected_text

            # Parse image data
            if "=====IMAGE_DATA=====" in context_section:
                image_data = context_section.split(
                    "=====IMAGE_DATA=====", 1)[1]
                image_data = image_data.split(
                    "=======================", 1)[0].strip()
                parsed_state['image_data'] = image_data
                parsed_state['use_vision'] = True

            # Parse mode
            if "Mode:" in context_section:
                mode = context_section.split("Mode:", 1)[1].split("\n", 1)[
                    0].strip().lower()
                parsed_state['mode'] = mode

            # Parse mode with delimiters
            if "=====MODE=====" in context_section:
                mode_text = context_section.split("=====MODE=====", 1)[1]
                mode_text = mode_text.split(
                    "=======================", 1)[0].strip()
                if "<" in mode_text and ">" in mode_text:
                    mode_text = mode_text.split(">", 1)[1].strip().lower()
                parsed_state['mode'] = mode_text

            # Parse web search flag in context
            if "Web Search:" in context_section or "=====WEB_SEARCH=====" in context_section:
                parsed_state['use_web_search'] = True
                logging.info("Web search flag detected in context section")

            # Update query to actual query
            parsed_state['query'] = actual_query

        return parsed_state

    def prepare_messages(self, state: GraphState) -> GraphState:
        """Prepare the messages list for the LLM."""
        updated_state = state.copy()

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

        # Process web search if needed
        if state.get('use_web_search', False):
            process_result = self.web_search_handler.process_query_context(
                state['query'],
                {'selected_text': state.get('selected_text')}
            )

            if process_result['mode'] in ['web_search', 'link_scrape']:
                selected_text = state.get('selected_text')
                search_result = self.web_search_handler.execute_search_or_scrape(
                    process_result, selected_text
                )

                if search_result['status'] == 'error':
                    updated_state['query'] = f"I tried to {process_result['mode'].replace('_', ' ')} but encountered an error: {search_result['error']}. Please answer without the {process_result['mode'].replace('_', ' ')} results."
                else:
                    updated_state['query'] = search_result['query']
                    if search_result['system_instruction']:
                        messages.append(SystemMessage(
                            content=search_result['system_instruction']))

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
            query_text_part = updated_state['query']
            if 'selected_text' in state:
                query_text_part = f"{updated_state['query']}\n\nText context: {state['selected_text']}"

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
            final_query_text = updated_state['query']

            # Append selected text if present
            if 'selected_text' in state:
                final_query_text += f"\n\n=====SELECTED_TEXT=====<text selected by the user>\n{state['selected_text']}\n======================="

            # Append vision description if available
            if state.get('vision_description'):
                final_query_text += f"\n\n=====VISUAL_DESCRIPTION=====<description generated by vision model>\n{state['vision_description']}\n======================="

            query_message = HumanMessage(content=final_query_text)

        # Add the query message to the list
        messages.append(query_message)

        # Save the prepared messages
        updated_state['messages'] = messages

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

            # Run the graph without generate_response to prepare messages
            partial_graph = StateGraph(GraphState)
            partial_graph.add_node("initialize", self.initialize_state)
            partial_graph.add_node("parse_query", self.parse_query)
            partial_graph.add_node("prepare_messages", self.prepare_messages)
            partial_graph.add_edge(START, "initialize")
            partial_graph.add_edge("initialize", "parse_query")
            partial_graph.add_edge("parse_query", "prepare_messages")
            partial_graph.add_edge("prepare_messages", END)

            partial_app = partial_graph.compile()
            try:
                # Pass the state including the potentially updated model_name
                prepared_state = await partial_app.ainvoke(state)
            except Exception as graph_err:
                logging.error(
                    f"Error running partial graph for streaming: {graph_err}", exc_info=True)
                error_msg = f"⚠️ Error preparing messages: {graph_err}"
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
        """Synchronous wrapper for get_response_async."""
        import asyncio

        try:
            # Create a new event loop if one doesn't exist in this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the async method in the event loop
            if loop.is_running():
                # If we're already in an event loop, we need to use a different approach
                import nest_asyncio
                nest_asyncio.apply()

            return loop.run_until_complete(self.get_response_async(query, callback, model, session_id))
        except Exception as e:
            logging.error(
                f"Error in synchronous get_response: {str(e)}", exc_info=True)
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
            if self.detected_language in ["python", "py"]:
                extension = ".py"
            elif self.detected_language in ["javascript", "js"]:
                extension = ".js"

            # Reset detected language
            self.detected_language = None

            return f"dasi_response_{timestamp}{extension}"
