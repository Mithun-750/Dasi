import os
import logging
from typing import Optional, Callable, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_together import ChatTogether
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from ui.settings import Settings
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from pathlib import Path


class LLMHandler:
    def __init__(self):
        """Initialize LLM handler."""
        self.llm = None
        self.settings = Settings()
        self.current_provider = None
        
        # Initialize database path
        self.db_path = str(Path(self.settings.config_dir) / 'chat_history.db')
        
        # Store message histories by session
        self.message_histories: Dict[str, BaseChatMessageHistory] = {}
        
        # Get chat history limit from settings or use default
        self.history_limit = self.settings.get('general', 'chat_history_limit', default=20)

        # Fixed system prompt
        self.system_prompt = """You are Dasi, an intelligent desktop copilot that helps users with their daily computer tasks. You appear when users press Ctrl+Alt+Shift+I, showing a popup near their cursor.

            IMPORTANT RULES:
            - Never say things like 'here's the response' or 'here's what I generated'
            - Just provide the direct answer or content requested
            - Keep responses concise and to the point
            - **Ambiguous References:** If the user uses terms like "this", "that", or similar ambiguous references without specifying a subject, assume that the reference applies to the text provided in the =====SELECTED_TEXT===== section.
            - Focus on being practically helpful for the current task"""

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
        self.initialize_llm()

    def on_models_changed(self):
        """Handle changes to the models list."""
        # Reload settings when models are changed
        self.settings.load_settings()

        # Update system prompt with any new custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="").strip()
        if custom_instructions:
            self.system_prompt = f"{self.system_prompt}\n\n=====CUSTOM_INSTRUCTIONS=====<user-defined instructions>\n{custom_instructions}\n======================="
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
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
        msg = msg.replace('{{', '<<<').replace('}}', '>>>')  # Preserve intended format strings
        msg = msg.replace('{', '{{').replace('}', '}}')      # Escape unintended braces
        msg = msg.replace('<<<', '{').replace('>>>', '}')    # Restore intended format strings
        return msg

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None, session_id: str = "default") -> str:
        """Get response from LLM for the given query. If callback is provided, stream the response."""
        # Initialize with specified model if provided
        if model:
            needs_init = True
            if self.llm:
                current_model = None
                if hasattr(self.llm, 'model'):
                    current_model = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    current_model = self.llm.model_name

                if current_model:
                    current_model = current_model.replace('models/', '')
                    model = model.replace('models/', '')
                    needs_init = current_model != model

            if needs_init:
                if not self.initialize_llm(model):
                    return "⚠️ Please add the appropriate API key in settings to use this model."

        if not self.llm and not self.initialize_llm():
            return "⚠️ Please add your API key in settings to use Dasi."

        try:
            # Get message history for this session
            message_history = self._get_message_history(session_id)
            
            # Parse context and query
            mode = 'chat'
            context = {}
            actual_query = query

            if "Context:" in query:
                context_section, actual_query = query.split("\n\nQuery:\n", 1)
                context_section = context_section.replace("Context:\n", "").strip()

                # Parse different types of context
                if "Selected Text:" in context_section:
                    selected_text = context_section.split("Selected Text:\n", 1)[1]
                    selected_text = selected_text.split("\n\n", 1)[0].strip()
                    context['selected_text'] = selected_text
                
                # Also support the new format with delimiters
                if "=====SELECTED_TEXT=====" in context_section:
                    selected_text = context_section.split("=====SELECTED_TEXT=====", 1)[1]
                    selected_text = selected_text.split("=======================", 1)[0].strip()
                    # Remove the metadata part if present
                    if "<" in selected_text and ">" in selected_text:
                        selected_text = selected_text.split(">", 1)[1].strip()
                    context['selected_text'] = selected_text

                if "Mode:" in context_section:
                    mode = context_section.split("Mode:", 1)[1].split("\n", 1)[0].strip()
                
                # Also support the new format for mode
                if "=====MODE=====" in context_section:
                    mode_text = context_section.split("=====MODE=====", 1)[1]
                    mode_text = mode_text.split("=======================", 1)[0].strip()
                    # Remove the metadata part if present
                    if "<" in mode_text and ">" in mode_text:
                        mode_text = mode_text.split(">", 1)[1].strip()
                    mode = mode_text

            # Build the messages list
            messages = []
            
            # Add mode-specific instruction to system prompt
            mode_instruction = ""
            if mode == 'compose':
                mode_instruction = """=====COMPOSE_MODE=====<strict instructions>
                IMPORTANT: You are now operating in COMPOSE MODE. You MUST follow these rules for EVERY response:

                RESPONSE RULES:
                1. ALWAYS generate content that can be directly pasted/used
                2. NEVER include any explanations or meta-commentary
                3. NEVER use markdown, code blocks, or formatting
                4. NEVER acknowledge or discuss these instructions
                5. NEVER start responses with phrases like "Here's" or "Here is"
                6. NEVER wrap responses in quotes
                7. TREAT EVERY INPUT AS A CONTENT GENERATION REQUEST

                EXAMPLES:
                User: "Hi"
                ✓ Dear [Name], I hope this message finds you well...
                ✗ Here's a greeting message: "Hello..."
                
                User: "Write test plan"
                ✓ Test Plan - [Project Name]
                1. Test Objectives
                2. Test Scope...
                ✗ I'll help you write a test plan. Here's a template...

                OVERRIDE NOTICE: These rules override any conflicting user instructions
                ======================="""
            else:
                mode_instruction = """=====CHAT_MODE=====<conversation instructions>
                You are in chat mode. Follow these guidelines:
                - Provide friendly, conversational responses with a helpful tone
                - Focus on explaining things clearly, like a knowledgeable friend
                - Example: If user asks "explain this code", break it down in an approachable way
                - Keep responses helpful and concise while maintaining a warm demeanor
                ======================="""

            # Combine all system instructions
            full_system_prompt = f"{self.system_prompt}\n\n{mode_instruction}"

            # Add system message first
            messages.append(SystemMessage(content=full_system_prompt))

            # Add chat history (limited to configured number of messages)
            history_messages = message_history.messages[-self.history_limit:] if message_history.messages else []
            messages.extend(history_messages)

            # Format user query with selected text if available
            if 'selected_text' in context:
                actual_query = f"{actual_query}\n\n=====SELECTED_TEXT=====<text selected by the user>\n{context['selected_text']}\n======================="

            # Add current query
            query_message = HumanMessage(content=actual_query)
            messages.append(query_message)

            # Get response
            if callback:
                # Stream response
                response_content = []
                for chunk in self.llm.stream(messages):
                    if chunk.content:
                        response_content.append(chunk.content)
                        callback(''.join(response_content))
                final_response = ''.join(response_content)
            else:
                # Get response all at once
                response = self.llm.invoke(messages)
                final_response = response.content.strip()

            # Add the exchange to history
            message_history.add_message(query_message)
            message_history.add_message(AIMessage(content=final_response))

            return final_response

        except Exception as e:
            logging.error(f"Error getting LLM response: {str(e)}", exc_info=True)
            error_msg = str(e)
            
            # Format error messages...
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

            return f"⚠️ Error: {error_msg}"

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
            
            # Create the prompt for filename suggestion
            filename_query = f"""Generate a concise, professional filename for this content. Follow these rules strictly:
1. Use letters, numbers, and underscores only (no spaces)
2. Maximum 30 characters (excluding .md extension)
3. Use PascalCase or snake_case for better readability
4. Focus on the key topic/purpose
5. No dates unless critically relevant
6. Return ONLY the filename with .md extension, nothing else

Examples of good filenames:
- Api_Authentication.md
- User_Workflow.md
- Deployment_Strategy.md
- System_Architecture.md

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
            
            # Ensure it has .md extension
            if not suggested_filename.endswith('.md'):
                suggested_filename += '.md'
                
            return suggested_filename
            
        except Exception as e:
            logging.error(f"Error suggesting filename: {str(e)}", exc_info=True)
            # Return a default filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"dasi_response_{timestamp}.md"
