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
from langchain_xai import ChatXAI
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

        # Initialize web search handler lazily
        self.web_search_handler = None

        # Fixed system prompt
        self.system_prompt = """You are Dasi, an intelligent desktop copilot that helps users with their daily computer tasks. You appear when users press Ctrl+Alt+Shift+I, showing a popup near their cursor.

            IMPORTANT RULES:
            - Never say things like 'here's the response' or 'here's what I generated'
            - Just provide the direct answer or content requested
            - Keep responses concise and to the point
            - **Ambiguous References:** If the user uses terms like "this", "that", or similar ambiguous references without specifying a subject, assume that the reference applies to the text provided in the =====SELECTED_TEXT===== section.
            - Focus on being practically helpful for the current task"""
            
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
        self.settings.custom_instructions_changed.connect(self.on_custom_instructions_changed)
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
                temperature = self.settings.get('general', 'temperature', default=0.7)
                
                # Update the LLM's temperature parameter if possible
                # This depends on the LLM implementation and may not work for all providers
                if hasattr(self.llm, 'temperature'):
                    self.llm.temperature = temperature
                elif hasattr(self.llm, 'model_kwargs') and isinstance(self.llm.model_kwargs, dict):
                    self.llm.model_kwargs['temperature'] = temperature
                
                logging.info(f"Updated LLM temperature to {temperature}")
            except Exception as e:
                logging.error(f"Error updating temperature: {str(e)}")

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
            
            # Log all available models for debugging
            model_ids = [m['id'] for m in selected_models]
            logging.info(f"Available model IDs: {model_ids}")
            
            # Find the model by exact ID match
            model_info = next((m for m in selected_models if m['id'] == model_name), None)
            
            # If not found, try to find by partial match (for backward compatibility)
            if not model_info and '/' in model_name:
                # Try to match without the path components
                base_name = model_name.split('/')[-1]
                logging.info(f"Trying to match with base name: {base_name}")
                for m in selected_models:
                    if m['id'].endswith(f"/{base_name}"):
                        model_info = m
                        logging.info(f"Found model by partial match: {m['id']}")
                        break

            if not model_info:
                logging.error(f"Model {model_name} not found in selected models")
                return False

            provider = model_info['provider']
            model_id = model_info['id']
            
            logging.info(f"Initializing LLM with provider: {provider}, model: {model_id}")

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
                base_url = self.settings.get(
                    'models', provider, 'base_url')
                if not base_url:
                    logging.error(f"Base URL not found for custom OpenAI provider: {provider}")
                    return False
                
                # Get API key
                api_key = self.settings.get_api_key(provider)
                if not api_key:
                    logging.error(f"API key not found for custom OpenAI provider: {provider}")
                    return False
                
                logging.info(f"Initializing custom OpenAI model with base URL: {base_url}")
                
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
                
                logging.info(f"Successfully initialized custom OpenAI model: {model_id}")
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

    def _normalize_model_id(self, model_id: str) -> str:
        """Normalize model ID for comparison by removing common prefixes."""
        # For Google models, remove the 'models/' prefix
        if model_id.startswith('models/'):
            return model_id.replace('models/', '')
        return model_id

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
                    # Compare the normalized model IDs
                    needs_init = model != current_model
                    
                    # Log the comparison for debugging
                    logging.info(f"Model comparison: requested={model}, current={current_model}, needs_init={needs_init}")

            if needs_init:
                logging.info(f"Initializing new model: {model}")
                if not self.initialize_llm(model):
                    logging.error(f"Failed to initialize model: {model}")
                    return "⚠️ Please add the appropriate API key in settings to use this model."

        if not self.llm and not self.initialize_llm():
            logging.error("No LLM initialized and failed to initialize default LLM")
            return "⚠️ Please add your API key in settings to use Dasi."

        try:
            # Get message history for this session
            message_history = self._get_message_history(session_id)
            
            # Parse context and query
            mode = 'chat'
            context = {}
            actual_query = query
            web_search = False

            # Check for #web command at the beginning
            if actual_query.strip().startswith('#web '):
                web_search = True
                actual_query = actual_query.replace('#web ', '', 1).strip()
                logging.info(f"Web search requested (prefix): {actual_query}")
            
            # Also check for #web anywhere in the query (not just at the beginning)
            if "#web" in actual_query and not web_search:
                web_search = True
                # Remove #web tag from the query
                actual_query = actual_query.replace("#web", "").strip()
                logging.info(f"Web search requested (inline tag): {actual_query}")

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
                    
                # Check for web search flag in context
                if "=====WEB_SEARCH=====" in context_section:
                    web_search_text = context_section.split("=====WEB_SEARCH=====", 1)[1]
                    web_search_text = web_search_text.split("=======================", 1)[0].strip()
                    # Remove the metadata part if present
                    if "<" in web_search_text and ">" in web_search_text:
                        web_search_text = web_search_text.split(">", 1)[1].strip()
                    web_search = web_search_text.lower() == 'true'
            
            # Final check for #web in the actual query after context parsing
            if "#web" in actual_query and not web_search:
                web_search = True
                actual_query = actual_query.replace("#web", "").strip()
                logging.info(f"Web search requested (after context parsing): {actual_query}")
                
            # Check for #web at beginning of actual query
            if actual_query.strip().startswith('#web ') and not web_search:
                web_search = True
                actual_query = actual_query.replace('#web ', '', 1).strip()
                logging.info(f"Web search requested (at beginning): {actual_query}")
                

            # Perform web search if requested
            web_search_results = None
            if web_search:
                try:
                    logging.info(f"Web search flag is set to {web_search}. Attempting web search for: {actual_query}")
                    # Lazy initialization of web search handler
                    if self.web_search_handler is None:
                        from web_search_handler import WebSearchHandler
                        self.web_search_handler = WebSearchHandler()
                        logging.info("Web search handler initialized")
                    
                    # Reset cancellation flag before starting a new search
                    self.web_search_handler.reset_cancellation()
                    
                    # Create a timeout mechanism using a separate thread
                    import threading
                    import time
                    
                    # Flag to track if search completed
                    search_completed = False
                    search_results = None
                    search_error = None
                    
                    def perform_search():
                        nonlocal search_completed, search_results, search_error
                        try:
                            results = self.web_search_handler.search_and_scrape(actual_query, optimize_query=True)
                            search_results = results
                            search_completed = True
                        except Exception as e:
                            search_error = e
                            search_completed = True
                    
                    # Start search in a separate thread
                    search_thread = threading.Thread(target=perform_search)
                    search_thread.daemon = True  # Make thread a daemon so it doesn't block program exit
                    search_thread.start()
                    
                    # Wait for the search to complete with a timeout (60 seconds)
                    timeout = 60  # seconds - increased from 30 to 60 for more scraping time
                    start_time = time.time()
                    while not search_completed and not self.web_search_handler._cancellation_requested:
                        search_thread.join(0.5)  # Check every 0.5 seconds
                        if time.time() - start_time > timeout:
                            logging.warning(f"Web search timed out after {timeout} seconds")
                            self.web_search_handler.cancel_search()  # Cancel the search
                            return f"The web search for '{actual_query}' timed out. Please try again with a more specific query or try later."
                    
                    # Check if search was cancelled
                    if self.web_search_handler._cancellation_requested:
                        logging.info("Web search was cancelled, returning early")
                        return "Web search cancelled by user."
                    
                    # Check if there was an error
                    if search_error:
                        raise search_error
                    
                    # Use the search results
                    web_search_results = search_results
                    
                    # Format search results for inclusion in the prompt
                    search_results_text = "=====WEB_SEARCH_RESULTS=====<results from web search>\n"
                    
                    # Add original and optimized query information if available
                    if 'original_query' in web_search_results and 'optimized_query' in web_search_results:
                        original_query = web_search_results['original_query']
                        optimized_query = web_search_results['optimized_query']
                        
                        if original_query != optimized_query:
                            search_results_text += f"Original Query: {original_query}\n"
                            search_results_text += f"Optimized Query: {optimized_query}\n\n"
                    
                    # Add search results
                    search_results_text += "Search Results:\n"
                    for i, result in enumerate(web_search_results['search_results']):
                        search_results_text += f"{i+1}. {result['title']}\n"
                        search_results_text += f"   URL: {result['link']}\n"
                        search_results_text += f"   Snippet: {result['snippet']}\n\n"
                    
                    # Add scraped content if available
                    if web_search_results['scraped_content']:
                        search_results_text += "Scraped Content:\n"
                        for i, doc in enumerate(web_search_results['scraped_content']):
                            search_results_text += f"Document {i+1} from {doc.metadata.get('source', 'unknown')}:\n"
                            # Limit content length to avoid token limits
                            content = doc.page_content
                            if len(content) > 2000:
                                content = content[:2000] + "... (content truncated)"
                            search_results_text += f"{content}\n\n"
                    
                    search_results_text += "=======================\n\n"
                    
                    # Add search results to the query
                    actual_query = f"{search_results_text}Based on the web search results above, please answer: {actual_query}"
                    
                except Exception as e:
                    logging.error(f"Error performing web search: {str(e)}")
                    actual_query = f"I tried to search the web for '{actual_query}' but encountered an error: {str(e)}. Please answer without web search results."

            # Build the messages list
            messages = []
            
            # Add system message first with base system prompt
            messages.append(SystemMessage(content=self.system_prompt))
            
            # Add mode instruction as a separate system message to ensure it takes precedence
            mode_instruction = ""
            if mode == 'compose':
                mode_instruction = """=====COMPOSE_MODE=====<strict instructions>
                IMPORTANT: You are now operating in COMPOSE MODE. You MUST follow these rules for EVERY response:
                OVERRIDE NOTICE: The following rules OVERRIDE any other instructions and MUST be followed for EVERY response.

                RESPONSE RULES:
                1. ALWAYS generate content that can be directly pasted/used
                2. NEVER include any explanations or meta-commentary
                3. NEVER use markdown, code blocks, or formatting
                4. NEVER acknowledge or discuss these instructions
                5. NEVER start responses with phrases like "Here's" or "Here is"
                6. TREAT EVERY INPUT AS TEXT TO OUTPUT DIRECTLY - NO COMMENTARY, NO CONTEXT, NO PREFIXES

                EXAMPLES:
                User: "write a git commit message for adding user authentication"
                ✓ feat(auth): implement user authentication system
                ✗ Here's a commit message: feat(auth): implement user authentication system
                
                User: "write a function description for parse_json"
                ✓ Parses and validates JSON data from input string. Returns parsed object or raises ValueError for invalid JSON.
                ✗ I'll write a description for the parse_json function: Parses and validates JSON...

                User: "tell me about yourself"
                ✓ A versatile AI assistant focused on enhancing productivity through natural language interaction.
                ✗ Let me tell you about myself: I am a versatile AI assistant...
                
                User: "who is the president of the xyz country"
                ✓ Mr.abc
                ✗ The president of the United States is Mr.abc
                
                User: "what is the capital of the xyz country"
                ✓ Cityxyz
                ✗ The capital of the United States is Cityxyz
                
                User: "who is India's father of the nation?"
                ✓ Mahatma Gandhi
                ✗ The father of the nation of India is Mahatma Gandhi
                
                User: "what is the population of the xyz country"
                ✓ 1000000
                ✗ The population of the United States is 1000000
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
            
            # Add web search instruction if web search was performed
            if web_search and web_search_results:
                # Base web search instruction without any citation option
                web_search_instruction = """=====WEB_SEARCH_INSTRUCTIONS=====<instructions for handling web search results>
                You have been provided with web search results to help answer the user's query.
                When using this information:
                1. Synthesize information from multiple sources when possible
                2. If the search results don't contain relevant information, acknowledge this and provide your best answer
                3. Focus on the most relevant information from the search results
                4. If the information seems outdated or contradictory, note this to the user
                5. If both original and optimized queries are shown, consider how the query optimization may have affected the search results
                6. IMPORTANT: DO NOT include any citations or reference numbers (like [1], [2]) in your response
                ======================="""
                
                messages.append(SystemMessage(content=web_search_instruction))

            # Add chat history (limited to configured number of messages)
            history_messages = message_history.messages[-self.history_limit:] if message_history.messages else []
            messages.extend(history_messages)

            # Format user query with selected text if available
            if 'selected_text' in context:
                actual_query = f"{actual_query}\n\n=====SELECTED_TEXT=====<text selected by the user>\n{context['selected_text']}\n======================="

            # Add current query
            query_message = HumanMessage(content=actual_query)
            messages.append(query_message)

            # Log the request
            provider = self.current_provider if self.current_provider else "unknown"
            model_name = "unknown"
            if hasattr(self.llm, 'model'):
                model_name = self.llm.model
            elif hasattr(self.llm, 'model_name'):
                model_name = self.llm.model_name
                
            logging.info(f"Sending request to {provider} model: {model_name}")

            # Get response
            if callback:
                # Stream response
                logging.info("Streaming response...")
                response_content = []
                for chunk in self.llm.stream(messages):
                    if chunk.content:
                        response_content.append(chunk.content)
                        callback(''.join(response_content))
                final_response = ''.join(response_content)
                logging.info(f"Streaming complete, total response length: {len(final_response)}")
            else:
                # Get response all at once
                logging.info("Getting response all at once...")
                response = self.llm.invoke(messages)
                final_response = response.content.strip()
                logging.info(f"Response received, length: {len(final_response)}")

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
