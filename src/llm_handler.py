import os
import logging
from typing import Optional, Callable, List, Dict, Tuple
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_together import ChatTogether
from langchain_xai import ChatXAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from ui.settings import Settings
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from pathlib import Path
import re

# Import WebSearchHandler and VisionHandler
from web_search_handler import WebSearchHandler
from vision_handler import VisionHandler


class LLMHandler:
    def __init__(self):
        """Initialize LLM handler."""
        self.llm = None
        self.settings = Settings()
        self.current_provider = None
        # Store detected language from code blocks
        self.detected_language = None

        # Initialize database path
        self.db_path = str(Path(self.settings.config_dir) / 'chat_history.db')

        # Store message histories by session
        self.message_histories: Dict[str, BaseChatMessageHistory] = {}

        # Get chat history limit from settings or use default
        self.history_limit = self.settings.get(
            'general', 'chat_history_limit', default=20)

        # Initialize web search handler, passing this LLMHandler instance
        self.web_search_handler = WebSearchHandler(self)

        # Initialize Vision Handler
        self.vision_handler = VisionHandler(self.settings)

        # Fixed system prompt
        self.system_prompt = """# IDENTITY and PURPOSE

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

        # Store the base system prompt for later resets
        self.base_system_prompt = self.system_prompt

        # Get custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()

        # Combine system prompt with custom instructions if they exist
        if custom_instructions:
            self.system_prompt = f"{self.system_prompt}\n\n=====CUSTOM_INSTRUCTIONS=====<user-defined instructions>\n{custom_instructions}\n======================="

        # Create base prompt template with memory
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{query}")
        ])

        # Connect to settings changes
        self.settings.models_changed.connect(self.on_models_changed)
        self.settings.custom_instructions_changed.connect(
            self.on_custom_instructions_changed)
        self.settings.temperature_changed.connect(self.on_temperature_changed)
        self.initialize_llm()

    def on_models_changed(self):
        """Handle changes to the models list."""
        # Reload settings when models are changed
        self.settings.load_settings()

        # Update system prompt with any new custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()

        # Reset system prompt to original before adding custom instructions
        self.system_prompt = self.base_system_prompt

        if custom_instructions:
            self.system_prompt = f"{self.system_prompt}\n\n=====CUSTOM_INSTRUCTIONS=====<user-defined instructions>\n{custom_instructions}\n======================="
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{query}")
            ])

    def on_custom_instructions_changed(self):
        """Handle changes to custom instructions."""
        # Reload settings to get the latest custom instructions
        self.settings.load_settings()

        # Update system prompt with the new custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()

        # Reset system prompt to original before adding custom instructions
        self.system_prompt = self.base_system_prompt

        if custom_instructions:
            self.system_prompt = f"{self.system_prompt}\n\n=====CUSTOM_INSTRUCTIONS=====<user-defined instructions>\n{custom_instructions}\n======================="

        # Update the prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{query}")
        ])

    def on_temperature_changed(self):
        """Handle changes to temperature setting."""
        # Reload settings to get the latest temperature
        self.settings.load_settings()

        # Update temperature in the LLM if it's initialized
        if self.llm:
            try:
                # Get the new temperature value
                temperature = self.settings.get(
                    'general', 'temperature', default=0.7)

                # Update the LLM's temperature parameter if possible
                # This depends on the LLM implementation and may not work for all providers
                if hasattr(self.llm, 'temperature'):
                    self.llm.temperature = temperature
                elif hasattr(self.llm, 'model_kwargs') and isinstance(self.llm.model_kwargs, dict):
                    self.llm.model_kwargs['temperature'] = temperature

                logging.info(f"Updated LLM temperature to {temperature}")
            except Exception as e:
                logging.error(f"Error updating temperature: {str(e)}")

    def initialize_llm(self, model_name: str = None, model_info: dict = None) -> bool:
        """Initialize the LLM with the current API key and specified model/info. Returns True if successful."""
        try:
            # Reload settings to ensure we have the latest data
            self.settings.load_settings()

            # If model_info is provided, use it directly
            if model_info and isinstance(model_info, dict):
                logging.info(
                    f"Initializing LLM using provided model info: {model_info.get('id', 'N/A')}")
            # If no model_info, try to find model by name
            elif model_name:
                # Get model info from settings based on model_name
                selected_models = self.settings.get_selected_models()
                model_ids = [m['id'] for m in selected_models]
                logging.info(
                    f"Available selected model IDs for lookup: {model_ids}")

                # Find the model by exact ID match
                model_info = next(
                    (m for m in selected_models if m['id'] == model_name), None)

                # If not found, try partial match (backward compatibility)
                if not model_info and '/' in model_name:
                    base_name = model_name.split('/')[-1]
                    logging.info(
                        f"Model '{model_name}' not found by exact match. Trying base name: {base_name}")
                    for m in selected_models:
                        if m['id'].endswith(f"/{base_name}"):
                            model_info = m
                            logging.info(
                                f"Found model by partial match: {m['id']}")
                            break

                if not model_info:
                    logging.error(
                        f"Model '{model_name}' not found in selected models.")
                    return False
            # If neither model_name nor model_info is provided, use the default model
            else:
                default_model_id = self.settings.get('models', 'default_model')
                if not default_model_id:
                    # If no default model set, try first available selected model
                    selected_models = self.settings.get_selected_models()
                    if selected_models:
                        # Use the first one's info
                        model_info = selected_models[0]
                        logging.info(
                            f"No model specified, using first selected model: {model_info['id']}")
                    else:
                        logging.error(
                            "No default model set and no models selected.")
                        return False
                else:
                    # Find the default model's info in the selected list
                    selected_models = self.settings.get_selected_models()
                    model_info = next(
                        (m for m in selected_models if m['id'] == default_model_id), None)
                    if not model_info:
                        logging.error(
                            f"Default model '{default_model_id}' not found in the selected models list.")
                        # Fallback: Try using the first selected model if available
                        if selected_models:
                            model_info = selected_models[0]
                            logging.warning(
                                f"Default model not found, falling back to first selected model: {model_info['id']}")
                        else:
                            return False
                    else:
                        logging.info(
                            f"Using default model: {default_model_id}")

            # Proceed with initialization using the determined model_info
            provider = model_info['provider']
            model_id = model_info['id']

            logging.info(
                f"Initializing LLM with provider: {provider}, model: {model_id}")

            # Get temperature from settings
            temperature = self.settings.get(
                'general', 'temperature', default=0.7)

            # Initialize appropriate LLM based on provider
            if provider == 'google':
                # Keep the full model ID for Gemini models
                self.llm = ChatGoogleGenerativeAI(
                    model=model_id,  # Keep the full model ID including 'models/' prefix
                    google_api_key=self.settings.get_api_key('google'),
                    temperature=temperature,
                )
            elif provider == 'openai':
                # For GPT-4o and vision models, explicitly add vision capability
                if 'gpt-4o' in model_id.lower() or 'vision' in model_id.lower():
                    self.llm = ChatOpenAI(
                        model=model_id,
                        temperature=temperature,
                        streaming=True,
                        openai_api_key=self.settings.get_api_key('openai'),
                        max_tokens=4096,  # Set a reasonable limit for vision models
                    )
                    logging.info(
                        f"Initialized OpenAI model with vision capabilities: {model_id}")
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
                self.llm = ChatGroq(
                    model=model_id,
                    groq_api_key=self.settings.get_api_key('groq'),
                    temperature=temperature,
                )
            elif provider == 'anthropic':
                # For Claude models, explicitly support multimodal for Claude 3 models
                if 'claude-3' in model_id.lower():
                    self.llm = ChatAnthropic(
                        model=model_id,
                        anthropic_api_key=self.settings.get_api_key(
                            'anthropic'),
                        temperature=temperature,
                        streaming=True,
                        max_tokens=4096,  # Set a reasonable limit for vision requests
                    )
                    logging.info(
                        f"Initialized Claude model with vision capabilities: {model_id}")
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
                # Set environment variable for Deepseek
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
                # Initialize xAI (Grok) model
                self.llm = ChatXAI(
                    model=model_id,
                    xai_api_key=self.settings.get_api_key('xai'),
                    temperature=temperature,
                )
                logging.info(f"Successfully initialized xAI model: {model_id}")
            elif provider == 'custom_openai' or provider.startswith('custom_openai_'):
                # Get custom OpenAI settings
                base_url = self.settings.get('models', provider, 'base_url')
                if not base_url:
                    logging.error(
                        f"Base URL not found for custom OpenAI provider: {provider}")
                    return False

                # Get API key
                api_key = self.settings.get_api_key(provider)
                if not api_key:
                    logging.error(
                        f"API key not found for custom OpenAI provider: {provider}")
                    return False

                logging.info(
                    f"Initializing custom OpenAI model with base URL: {base_url}")

                # For custom OpenAI models, we might need to handle the model ID differently
                # Some models might have complex IDs like "accounts/perplexity/models/r1-1776"
                # which should be passed as-is to the API

                self.llm = ChatOpenAI(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                    openai_api_key=api_key,
                    base_url=base_url.rstrip('/') + '/v1',
                )

                logging.info(
                    f"Successfully initialized custom OpenAI model: {model_id}")
            else:  # OpenRouter
                # Use fixed OpenRouter settings
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
            return True

        except Exception as e:
            logging.error(f"Error initializing LLM: {str(e)}", exc_info=True)
            return False

    def _get_message_history(self, session_id: str) -> BaseChatMessageHistory:
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

    def _preformat(self, msg: str) -> str:
        """Allow {{key}} to be used for formatting in text that already uses curly braces.
        First switch existing double braces to temporary markers,
        then escape single braces by doubling them,
        finally restore the original double braces.
        """
        msg = msg.replace('{{', '<<<').replace('}}',
                                               '>>>')  # Preserve intended format strings
        # Escape unintended braces
        msg = msg.replace('{', '{{').replace('}', '}}')
        # Restore intended format strings
        msg = msg.replace('<<<', '{').replace('>>>', '}')
        return msg

    def _normalize_model_id(self, model_id: str) -> str:
        """Normalize model ID for comparison by removing common prefixes."""
        # For Google models, remove the 'models/' prefix
        if model_id.startswith('models/'):
            return model_id.replace('models/', '')
        return model_id

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None, session_id: str = "default") -> str:
        """Get response from LLM for the given query. If callback is provided, stream the response."""
        current_model_info = None  # Store the info of the model being used

        # Initialize with specified model if provided (by name/ID)
        if model:
            needs_init = True
            if self.llm:
                current_model_id = None
                if hasattr(self.llm, 'model'):
                    current_model_id = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    current_model_id = self.llm.model_name

                if current_model_id:
                    needs_init = (model != current_model_id)
                    logging.info(
                        f"Model comparison: requested={model}, current={current_model_id}, needs_init={needs_init}")

            if needs_init:
                logging.info(f"Initializing specified model by name: {model}")
                # Initialize by name, model_info will be looked up inside initialize_llm
                if not self.initialize_llm(model_name=model):
                    logging.error(f"Failed to initialize model: {model}")
                    return "⚠️ Please ensure the requested model is selected and its API key is configured in settings."
                else:
                    # Successfully initialized, store its info (we might need provider later)
                    # Find the info from selected models again (a bit redundant, but necessary)
                    selected_models = self.settings.get_selected_models()
                    current_model_info = next(
                        (m for m in selected_models if m['id'] == model), None)

        # If no specific model requested or initialization failed, ensure default is loaded
        if not self.llm:
            logging.info(
                "No LLM active or specified model failed, initializing default LLM.")
            if not self.initialize_llm():  # Initialize default (or first selected)
                logging.error("Failed to initialize default LLM")
                return "⚠️ Please add your API key and select a model in settings to use Dasi."
            else:
                # Get the info of the model that was just initialized (default or first selected)
                if hasattr(self.llm, 'model'):
                    current_model_id = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    current_model_id = self.llm.model_name
                selected_models = self.settings.get_selected_models()
                current_model_info = next(
                    (m for m in selected_models if m['id'] == current_model_id), None)

        # If we still don't have model info, try to get it from the active LLM instance
        if not current_model_info and self.llm:
            if hasattr(self.llm, 'model'):
                current_model_id = self.llm.model
            elif hasattr(self.llm, 'model_name'):
                current_model_id = self.llm.model_name
            # Try finding info in selected models OR vision model info
            selected_models = self.settings.get_selected_models()
            vision_model_info = self.settings.get_vision_model_info()

            current_model_info = next(
                (m for m in selected_models if m['id'] == current_model_id), None)
            if not current_model_info and vision_model_info and vision_model_info.get('id') == current_model_id:
                current_model_info = vision_model_info  # It might be the vision model

        try:
            # Get message history for this session
            message_history = self._get_message_history(session_id)

            # Parse context and query
            mode = 'chat'  # Default mode
            context = {}
            actual_query = query
            has_image = False
            image_data = None

            if "Context:" in query:
                context_section, actual_query = query.split("\n\nQuery:\n", 1)
                context_section = context_section.replace(
                    "Context:\n", "").strip()

                # Parse different types of context
                if "Selected Text:" in context_section:
                    selected_text = context_section.split(
                        "Selected Text:\n", 1)[1]
                    selected_text = selected_text.split("\n\n", 1)[0].strip()
                    context['selected_text'] = selected_text

                # Also support the new format with delimiters
                if "=====SELECTED_TEXT=====" in context_section:
                    selected_text = context_section.split(
                        "=====SELECTED_TEXT=====", 1)[1]
                    selected_text = selected_text.split(
                        "=======================", 1)[0].strip()
                    # Remove the metadata part if present
                    if "<" in selected_text and ">" in selected_text:
                        selected_text = selected_text.split(">", 1)[1].strip()
                    context['selected_text'] = selected_text

                # Check for image data in context
                if "=====IMAGE_DATA=====" in context_section:
                    image_data_text = context_section.split(
                        "=====IMAGE_DATA=====", 1)[1]
                    image_data_text = image_data_text.split(
                        "=======================", 1)[0].strip()
                    image_data = image_data_text
                    context['image_data'] = image_data
                    has_image = True
                    logging.info("Image data found in context")

                # Check for mode in context
                if "Mode:" in context_section:
                    mode = context_section.split("Mode:", 1)[1].split("\n", 1)[
                        0].strip().lower()
                    logging.info(f"Mode detected from context: {mode}")

                # Also support the new format for mode
                if "=====MODE=====" in context_section:
                    mode_text = context_section.split("=====MODE=====", 1)[1]
                    mode_text = mode_text.split(
                        "=======================", 1)[0].strip()
                    # Remove the metadata part if present
                    if "<" in mode_text and ">" in mode_text:
                        mode_text = mode_text.split(">", 1)[1].strip().lower()
                    mode = mode_text
                    logging.info(
                        f"Mode detected from delimited context: {mode}")

            # Build the messages list
            messages = []

            # Add system message first with base system prompt
            messages.append(SystemMessage(content=self.system_prompt))

            # Add mode instruction as a separate system message to ensure it takes precedence
            mode_instruction = ""
            if mode == 'compose':
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

            # Process web search and link scraping using WebSearchHandler
            process_result = self.web_search_handler.process_query_context(
                actual_query, context)

            # If web search or link scrape is needed, execute it
            if process_result['mode'] in ['web_search', 'link_scrape']:
                selected_text = context.get('selected_text')
                search_result = self.web_search_handler.execute_search_or_scrape(
                    process_result, selected_text)

                if search_result['status'] == 'error':
                    actual_query = f"I tried to {process_result['mode'].replace('_', ' ')} but encountered an error: {search_result['error']}. Please answer without the {process_result['mode'].replace('_', ' ')} results."
                else:
                    actual_query = search_result['query']
                    if search_result['system_instruction']:
                        messages.append(SystemMessage(
                            content=search_result['system_instruction']))

            # Add chat history (limited to configured number of messages)
            history_messages = message_history.messages[-self.history_limit:] if message_history.messages else [
            ]
            # Make sure history messages are correctly typed
            typed_history = []
            for msg in history_messages:
                if isinstance(msg, HumanMessage):
                    typed_history.append(msg)
                elif isinstance(msg, AIMessage):
                    typed_history.append(msg)
                elif isinstance(msg, SystemMessage):  # Shouldn't happen here, but check
                    typed_history.append(msg)
                # Handle dict representation maybe?
                elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                    if msg.type == 'human':
                        typed_history.append(HumanMessage(content=msg.content))
                    elif msg.type == 'ai':
                        typed_history.append(AIMessage(content=msg.content))

            messages.extend(typed_history)  # Use the typed history

            # ---> Vision Handling Logic <---
            generated_visual_description = None
            if has_image and image_data:
                # Get vision model and current model info
                vision_model_info = self.settings.get_vision_model_info()

                # Ensure current_model_info is set (it should be at this point)
                if not current_model_info:
                    logging.error(
                        "LLMHandler: Could not determine current model info before vision handling.")
                    # Fallback? Maybe try to get it again?
                    current_model_id = self.llm.model if hasattr(
                        self.llm, 'model') else getattr(self.llm, 'model_name', None)
                    if current_model_id:
                        selected_models = self.settings.get_selected_models()
                        current_model_info = next(
                            (m for m in selected_models if m['id'] == current_model_id), None)
                        if not current_model_info and vision_model_info and vision_model_info.get('id') == current_model_id:
                            current_model_info = vision_model_info

                use_vision_handler = False
                if vision_model_info and isinstance(vision_model_info, dict) and current_model_info and isinstance(current_model_info, dict):
                    if vision_model_info.get('id') != current_model_info.get('id'):
                        use_vision_handler = True
                        logging.info(
                            f"Vision model ({vision_model_info.get('id')}) differs from main LLM ({current_model_info.get('id')}). Using VisionHandler.")
                    else:
                        logging.info(
                            f"Vision model and main LLM are the same ({vision_model_info.get('id')}). Will attempt direct multimodal call.")
                elif not vision_model_info:
                    logging.info(
                        "No dedicated vision model configured. Will attempt direct multimodal call with main LLM.")
                else:  # current_model_info is missing?
                    logging.warning(
                        "Could not compare vision model and main LLM. Defaulting to direct multimodal call if possible.")

                # Scenario 1: Use VisionHandler to get description first
                if use_vision_handler:
                    logging.info(
                        "Generating detailed visual description using VisionHandler...")
                    description = self.vision_handler.get_visual_description(
                        image_data_base64=image_data,
                        prompt_hint=actual_query  # Pass user query as hint
                    )
                    if description:
                        generated_visual_description = description
                        # Prepare for text-only call to main LLM
                        has_image = False
                        image_data = None
                        logging.info(
                            "Successfully generated visual description.")
                    else:
                        # Failed to get description, proceed as text-only but add a note
                        logging.error(
                            "Failed to generate visual description from VisionHandler.")
                        actual_query += "\n\n=====SYSTEM_NOTE=====\n(Failed to process the provided visual input.)\n====================="
                        has_image = False
                        image_data = None

                # Scenario 2: Direct multimodal call (Vision model is same as main, or none is set)
                else:
                    logging.info(
                        "Proceeding with direct multimodal message construction.")
                    # We keep has_image = True and image_data as is
                    # Need to ensure the current LLM can handle it; Langchain models usually do if underlying API supports it.
                    # If current_model_info exists, we could add an explicit capability check here if needed,
                    # but for now, we rely on Langchain/API handling.
                    pass  # No changes needed here, the multimodal message will be constructed below if has_image is still True

            # --- End Vision Handling Logic ---

            # Construct the final query message based on whether we have image data or description
            if has_image and image_data:
                # Direct Multimodal Message (Scenario 2 or original flow)
                # Format selected text if available
                query_text_part = actual_query
                if 'selected_text' in context:
                    query_text_part = f"{actual_query}\n\nText context: {context['selected_text']}"

                # Ensure base64 data is clean
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
                logging.info("Constructed direct multimodal query message.")

            else:
                # Text-Only Message (No image initially, or VisionHandler used)
                final_query_text = actual_query
                # Append selected text if present
                if 'selected_text' in context:
                    final_query_text += f"\n\n=====SELECTED_TEXT=====<text selected by the user>\n{context['selected_text']}\n======================="
                # Append generated visual description if available (from Scenario 1)
                if generated_visual_description:
                    final_query_text += f"\n\n=====VISUAL_DESCRIPTION=====<description generated by vision model>\n{generated_visual_description}\n======================="

                query_message = HumanMessage(content=final_query_text)
                if generated_visual_description:
                    logging.info(
                        "Constructed text query message including generated visual description.")
                else:
                    logging.info("Constructed standard text query message.")

            # Add the message to the messages list
            messages.append(query_message)

            # Log the request
            provider = "unknown"
            model_name = "unknown"
            if current_model_info:  # Use the stored info
                provider = current_model_info.get('provider', 'unknown')
                model_name = current_model_info.get('id', 'unknown')
            elif self.llm:  # Fallback to getting from llm instance if info somehow missing
                if hasattr(self.llm, 'model'):
                    model_name = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    model_name = self.llm.model_name
                # Provider might be harder to get directly, use self.current_provider if set
                if self.current_provider:
                    provider = self.current_provider

            logging.info(f"Sending request to {provider} model: {model_name}")
            if has_image:
                logging.info("Request includes an image")

            # Get response
            if callback:
                # Stream response
                logging.info("Streaming response...")
                response_content = []
                for chunk in self.llm.stream(messages):
                    if chunk.content:
                        response_content.append(chunk.content)
                        # Stream the raw response to the user without processing backticks
                        callback(''.join(response_content))
                # Get the complete response after streaming is done
                final_response = ''.join(response_content)
                logging.info(
                    f"Streaming complete, total response length: {len(final_response)}")
            else:
                # Get response all at once
                logging.info("Getting response all at once...")
                response = self.llm.invoke(messages)
                final_response = response.content.strip()
                logging.info(
                    f"Response received, length: {len(final_response)}")

            # Check if in compose mode for proper code block handling
            is_compose_mode = (mode == 'compose')
            logging.info(
                f"Processing response in mode: {mode} (compose mode: {is_compose_mode})")

            # Extract any code blocks from the response - only in compose mode
            # This happens only after the complete response is generated
            if is_compose_mode:
                logging.info(
                    f"Original response before processing: '{final_response[:50]}...'")
                final_response, detected_language = self._extract_code_block(
                    final_response)
                logging.info(f"Processed response: '{final_response[:50]}...'")
                # Store the detected language for later use
                self.detected_language = detected_language
                logging.info(
                    f"Detected language from code block: {detected_language}")
            else:
                # For chat mode, keep the backticks (for proper markdown rendering)
                self.detected_language = None
                logging.info(
                    "In chat mode - preserving code blocks with backticks for markdown rendering")

            # Add the exchange to history
            message_history.add_message(query_message)
            message_history.add_message(AIMessage(content=final_response))

            return final_response

        except Exception as e:
            logging.error(
                f"Error getting LLM response: {str(e)}", exc_info=True)
            error_msg = str(e)

            # Format error messages...
            if "NotFoundError" in error_msg:
                if "Model" in error_msg and "does not exist" in error_msg:
                    return "⚠️ Error: The selected model is not available. Please check the model ID in settings."
            elif "AuthenticationError" in error_msg or "api_key" in error_msg.lower():
                return "⚠️ Error: Invalid API key. Please check your API key in settings."
            elif "RateLimitError" in error_msg:
                return "⚠️ Error: Rate limit exceeded. Please try again in a moment."
            elif "InvalidRequestError" in error_msg:
                return "⚠️ Error: Invalid request. Please try again with different input."
            elif "ServiceUnavailableError" in error_msg:
                return "⚠️ Error: Service is currently unavailable. Please try again later."
            elif "ConnectionError" in error_msg or "Connection refused" in error_msg:
                return "⚠️ Error: Could not connect to the API server. Please check your internet connection and the base URL in settings."

            return f"⚠️ Error: {error_msg}"

    def _extract_code_block(self, response: str) -> Tuple[str, Optional[str]]:
        """
        Extract code blocks from response text.

        IMPORTANT: This method is called only after the complete response is generated,
        not during streaming, to ensure we properly detect full code blocks.

        In compose mode, the backticks are removed to provide clean code.
        In chat mode, the backticks are preserved for markdown rendering.

        Args:
            response: The complete response text from LLM

        Returns:
            Tuple containing:
                - The response with code blocks unwrapped (if it was a single code block)
                - The detected language if found, otherwise None
        """
        # Strip whitespace for more reliable pattern matching
        stripped_response = response.strip()

        # Direct method for robust detection and removal of triple backticks
        # This should handle any formatting variations

        # Check if response starts with triple backticks and ends with triple backticks
        if stripped_response.startswith("```") and stripped_response.endswith("```"):
            logging.info("Detected code block with backticks at start and end")

            # Find the first newline to extract language
            first_line_end = stripped_response.find("\n")
            if first_line_end > 3:  # We have a language identifier
                language = stripped_response[3:first_line_end].strip().lower()
                # Remove the starting line with backticks and language
                content = stripped_response[first_line_end+1:-3].strip()
                logging.info(f"Extracted language: {language}")
                return content, language
            else:
                # No language specified
                content = stripped_response[4:-3].strip()
                logging.info("No language specified in code block")
                return content, None

        # Fallback to regex for more complex patterns
        # This pattern matches:
        # 1. Start of string with optional whitespace
        # 2. Three backticks followed by an optional language identifier
        # 3. Optional whitespace and newline
        # 4. Any content (non-greedy)
        # 5. Three backticks at the end with optional whitespace
        # 6. End of string
        code_block_pattern = r'^\s*```(\w*)\s*\n([\s\S]*?)\n\s*```\s*$'
        match = re.match(code_block_pattern, stripped_response)

        if match:
            # The entire response is a code block
            language = match.group(1).strip().lower() or None
            code_content = match.group(2)

            logging.info(f"Detected code block with language: {language}")
            # Return the content without backticks and the detected language
            return code_content, language

        # Additional check: if the response contains triple backticks at beginning and end
        # but with some extra text/whitespace that the regex missed
        if "```" in stripped_response:
            lines = stripped_response.split("\n")
            # Check if first line has backticks
            if any(line.strip().startswith("```") for line in lines[:2]):
                # Check if last line has backticks
                if any(line.strip().endswith("```") for line in lines[-2:]):
                    logging.info(
                        "Detected code block with non-standard formatting")

                    # Find the first line with backticks
                    for i, line in enumerate(lines):
                        if "```" in line:
                            # Extract language if present
                            language_part = line.strip()[3:].strip()
                            # Extract remaining content after first line until last backticks
                            content_lines = []
                            backtick_found = False
                            for j in range(i+1, len(lines)):
                                if "```" in lines[j]:
                                    backtick_found = True
                                    break
                                content_lines.append(lines[j])

                            if backtick_found and content_lines:
                                content = "\n".join(content_lines)
                                return content, language_part if language_part else None
                            break

        # If we get here, it wasn't a code block or the pattern didn't match
        logging.info("No code block detected in the response")
        return response, None

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
                logging.info(
                    f"Using detected language for filename suggestion: {self.detected_language}")
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
                    logging.info(
                        f"Using file extension: {file_extension} for detected language: {self.detected_language}")

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
{content[:500]}..."""  # Send first 500 chars to keep query concise

            # Get response without adding to history
            # Create a direct message list instead of using the chain
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=filename_query)
            ]

            # Invoke the LLM directly with these messages
            response = self.llm.invoke(messages)

            # Extract the content from the response
            suggested_filename = response.content.strip().strip('"').strip("'").strip()

            # Ensure it has the correct extension
            if not suggested_filename.endswith(file_extension):
                # Remove any existing extension
                if '.' in suggested_filename:
                    suggested_filename = suggested_filename.split('.')[0]
                suggested_filename += file_extension

            # Reset the detected language after using it
            self.detected_language = None

            return suggested_filename

        except Exception as e:
            logging.error(
                f"Error suggesting filename: {str(e)}", exc_info=True)
            # Return a default filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Use the stored language for extension if available
            extension = ".md"
            if self.detected_language in ["python", "py"]:
                extension = ".py"
            elif self.detected_language in ["javascript", "js"]:
                extension = ".js"

            # Reset the detected language
            self.detected_language = None

            return f"dasi_response_{timestamp}{extension}"
