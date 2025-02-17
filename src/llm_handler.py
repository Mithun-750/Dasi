import os
import logging
from typing import Optional, Callable
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_together import ChatTogether
from langchain_core.prompts import ChatPromptTemplate
from ui.settings import Settings


class LLMHandler:
    def __init__(self):
        """Initialize LLM handler."""
        self.llm = None
        self.settings = Settings()
        self.current_provider = None

        # Fixed system prompt
        self.system_prompt = """You are Dasi, an intelligent desktop copilot that helps users with their daily computer tasks. You appear when users press Ctrl+Alt+Shift+I, showing a popup near their cursor.

            IMPORTANT RULES:
            - Never wrap responses in quotes or code blocks unless specifically requested
            - Never say things like 'here's the response' or 'here's what I generated'
            - Just provide the direct answer or content requested
            - Keep responses concise and to the point
            - **Ambiguous References:** If the user uses terms like "this", "that", or similar ambiguous references without specifying a subject, assume that the reference applies to the "Selected Text" provided in the context.
            - Focus on being practically helpful for the current task"""

        # Get custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()

        # Combine system prompt with custom instructions if they exist
        if custom_instructions:
            self.system_prompt = f"{self.system_prompt}\n\nCustom Instructions:\n{custom_instructions}"

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{query}")
        ])
        # Connect to settings changes
        self.settings.models_changed.connect(self.on_models_changed)
        self.initialize_llm()

    def on_models_changed(self):
        """Handle changes to the models list."""
        # Reload settings when models are changed
        self.settings.load_settings()

        # Update system prompt with any new custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()
        if custom_instructions:
            self.system_prompt = f"{self.system_prompt}\n\nCustom Instructions:\n{custom_instructions}"
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt),
                ("human", "{query}")
            ])

    def initialize_llm(self, model_name: str = None) -> bool:
        """Initialize the LLM with the current API key and specified model. Returns True if successful."""
        try:
            # Reload settings to ensure we have the latest data
            self.settings.load_settings()

            # If no model specified, use default model from settings
            if model_name is None:
                model_name = self.settings.get('models', 'default_model')
                if not model_name:
                    # If no default model set, use first available model
                    selected_models = self.settings.get_selected_models()
                    if selected_models:
                        model_name = selected_models[0]['id']
                    else:
                        return False

            # Get model info from settings
            selected_models = self.settings.get_selected_models()
            model_info = next(
                (m for m in selected_models if m['id'] == model_name), None)

            if not model_info:
                return False

            provider = model_info['provider']
            model_id = model_info['id']

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
                self.llm = ChatAnthropic(
                    model=model_id,
                    anthropic_api_key=self.settings.get_api_key('anthropic'),
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
            elif provider == 'custom_openai':
                # Get custom OpenAI settings
                base_url = self.settings.get(
                    'models', 'custom_openai', 'base_url')
                if not base_url:
                    return False

                self.llm = ChatOpenAI(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                    openai_api_key=self.settings.get_api_key('custom_openai'),
                    base_url=base_url.rstrip('/') + '/v1',
                )
            elif provider == 'together':
                self.llm = ChatTogether(
                    model=model_id,
                    together_api_key=self.settings.get_api_key('together'),
                    temperature=temperature,
                )
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

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None) -> str:
        """Get response from LLM for the given query. If callback is provided, stream the response."""
        # Initialize with specified model if provided
        if model:
            needs_init = True
            if self.llm:
                current_model = None
                # Try different ways to get the current model name
                if hasattr(self.llm, 'model'):
                    current_model = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    current_model = self.llm.model_name

                # Clean up model names for comparison
                if current_model:
                    # Remove any 'models/' prefix
                    current_model = current_model.replace('models/', '')
                    model = model.replace('models/', '')
                    needs_init = current_model != model

            if needs_init:
                if not self.initialize_llm(model):
                    return "⚠️ Please add the appropriate API key in settings to use this model."

        # Check if LLM is initialized, try to initialize if not
        if not self.llm and not self.initialize_llm():
            return "⚠️ Please add your API key in settings to use Dasi."

        try:
            # Parse context and query
            mode = 'chat'  # Default mode
            if "Context:" in query:
                context_section, actual_query = query.split("\n\nQuery:\n", 1)
                context_section = context_section.replace(
                    "Context:\n", "").strip()

                # Parse different types of context
                context = {}
                if "Selected Text:" in context_section:
                    selected_text = context_section.split(
                        "Selected Text:\n", 1)[1]
                    selected_text = selected_text.split("\n\n", 1)[0].strip()
                    context['selected_text'] = selected_text

                if "Last Response:" in context_section:
                    last_response = context_section.split(
                        "Last Response:\n", 1)[1]
                    last_response = last_response.split("\n\n", 1)[0].strip()
                    context['last_response'] = last_response

                if "Mode:" in context_section:
                    mode = context_section.split("Mode:", 1)[1].split("\n", 1)[0].strip()

                # Create a special prompt for queries with context
                mode_instruction = ""
                if mode == 'compose':
                    mode_instruction = """You are in COMPOSE MODE:
                    - Generate content that can be directly pasted somewhere
                    - Treat every input as a request to compose/generate content
                    - Example: If user says "Hi", generate a proper greeting email/message
                    - Focus on producing polished, ready-to-use content
                    - No explanations or meta-commentary, just the content"""
                else:
                    mode_instruction = """You are in CHAT MODE:
                    - Provide friendly, conversational responses with a helpful tone
                    - Focus on explaining things clearly, like a knowledgeable friend
                    - Example: If user asks "explain this code", break it down in an approachable way
                    - Keep responses helpful and concise while maintaining a warm demeanor"""

                context_prompt = ChatPromptTemplate.from_messages([
                    ("system", f"""{self.system_prompt}

                    {mode_instruction}

                    Available Context:
{self._format_context(context)}"""),
                    ("human", "{query}")
                ])

                # Format prompt with actual query
                messages = context_prompt.invoke({"query": actual_query})
            else:
                # Use default prompt for queries without context
                messages = self.prompt.invoke({"query": query})

            # Get response
            if callback:
                # Stream response
                response_content = []
                for chunk in self.llm.stream(messages):
                    if chunk.content:
                        response_content.append(chunk.content)
                        callback(''.join(response_content))
                return ''.join(response_content)
            else:
                # Get response all at once
                response = self.llm.invoke(messages)
                return response.content.strip()
        except Exception as e:
            logging.error(
                f"Error getting LLM response: {str(e)}", exc_info=True)

            # Format error message for UI
            error_msg = str(e)
            if "NotFoundError" in error_msg:
                if "Model" in error_msg and "does not exist" in error_msg:
                    return "⚠️ Error: The selected model is not available. Please choose a different model in settings."
            elif "AuthenticationError" in error_msg:
                return "⚠️ Error: Invalid API key. Please check your API key in settings."
            elif "RateLimitError" in error_msg:
                return "⚠️ Error: Rate limit exceeded. Please try again in a moment."
            elif "InvalidRequestError" in error_msg:
                return "⚠️ Error: Invalid request. Please try again with different input."
            elif "ServiceUnavailableError" in error_msg:
                return "⚠️ Error: Service is currently unavailable. Please try again later."

            # For other errors, provide a cleaner message
            return f"⚠️ Error: {error_msg}"

    def _preformat(self, msg: str) -> str:
        """Allow {{key}} to be used for formatting in text that already uses curly braces.
        First switch existing double braces to temporary markers,
        then escape single braces by doubling them,
        finally restore the original double braces.
        """
        msg = msg.replace('{{', '<<<').replace('}}', '>>>')  # Preserve intended format strings
        msg = msg.replace('{', '{{').replace('}', '}}')      # Escape unintended braces
        msg = msg.replace('<<<', '{').replace('>>>', '}')    # Restore intended format strings
        return msg

    def _format_context(self, context: dict) -> str:
        """Format context dictionary into a string, safely handling curly braces."""
        context_parts = []
        if 'selected_text' in context:
            text = self._preformat(context['selected_text'])
            context_parts.append(f"Selected Text (what the user has highlighted):\n{text}")
        if 'last_response' in context:
            text = self._preformat(context['last_response'])
            context_parts.append(f"Previous Response:\n{text}")
        return "\n\n".join(context_parts)
