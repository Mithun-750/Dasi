import os
import logging
from typing import Optional, Callable
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from ui.settings import Settings


class LLMHandler:
    def __init__(self):
        """Initialize LLM handler."""
        self.llm = None
        self.settings = Settings()
        self.current_provider = None
        self.prompt = ChatPromptTemplate([
            ("system", """
            You are Dasi, an intelligent desktop copilot that helps users with their daily computer tasks. You appear when users press Ctrl+Alt+Shift+I, showing a popup near their cursor. You help users with tasks like:
            - Understanding and troubleshooting code
            - Explaining error messages and logs
            - Providing quick answers and suggestions
            - Generating text, code, or commands
            - Explaining documentation and concepts

            IMPORTANT RULES:
            - Never introduce yourself or add pleasantries
            - Never explain what you're doing
            - Never wrap responses in quotes or code blocks unless specifically requested
            - Never say things like 'here's the response' or 'here's what I generated'
            - Just provide the direct answer or content requested
            - If asked to generate content (email, code, etc), output only the content
            - Keep responses concise and to the point
            - Focus on being practically helpful for the current task
            """),
            ("human", "{query}")
        ])
        self.initialize_llm()

    def initialize_llm(self, model_name: str = "gemini-pro") -> bool:
        """Initialize the LLM with the current API key and specified model. Returns True if successful."""
        try:
            # Get model info from settings
            selected_models = self.settings.get_selected_models()
            model_info = next(
                (m for m in selected_models if m['id'] == model_name), None)

            if not model_info:
                logging.warning(
                    f"Model {model_name} not found in selected models")
                return False

            provider = model_info['provider']
            model_id = model_info['id']

            # Get API key for the provider
            api_key = self.settings.get_api_key(provider)
            if not api_key:
                logging.warning(f"No API key found for {provider} in settings")
                return False

            # Initialize appropriate LLM based on provider
            if provider == 'google':
                # Clean up model name for Google models (remove 'models/' prefix if present)
                if model_id.startswith('models/'):
                    model_id = model_id.replace('models/', '', 1)

                self.llm = ChatGoogleGenerativeAI(
                    model=model_id,
                    google_api_key=api_key,
                    temperature=0.7,
                    convert_system_message_to_human=True
                )
            else:  # OpenRouter
                site_url = self.settings.get('general', 'openrouter_site_url')
                site_name = self.settings.get(
                    'general', 'openrouter_site_name')

                headers = {
                    'HTTP-Referer': site_url,
                    'X-Title': site_name,
                    'Content-Type': 'application/json'
                }

                self.llm = ChatOpenAI(
                    model=model_id,
                    temperature=0.7,
                    streaming=True,
                    openai_api_key=api_key,
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
            current_model = None
            if self.llm:
                if hasattr(self.llm, 'model'):
                    current_model = self.llm.model
                elif hasattr(self.llm, 'model_name'):
                    current_model = self.llm.model_name

            if not current_model or current_model != model:
                if not self.initialize_llm(model):
                    return "Please add the appropriate API key in settings to use this model."

        # Check if LLM is initialized, try to initialize if not
        if not self.llm and not self.initialize_llm():
            return "Please add your API key in settings to use Dasi."

        try:
            # Parse context and query
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

                # Create a special prompt for queries with context
                context_prompt = ChatPromptTemplate([
                    ("system", """
                    You are Dasi, an intelligent desktop copilot that helps users with their daily computer tasks.
                    You appear when users press Ctrl+Alt+Shift+I, showing a popup near their cursor.

                    Available Context:
                    {context_desc}

                    IMPORTANT RULES:
                    - Never introduce yourself or add pleasantries
                    - Never explain what you're doing
                    - Never wrap responses in quotes or code blocks unless specifically requested
                    - Never say things like 'here's the response' or 'here's what I generated'
                    - Just provide the direct answer or content requested
                    - Keep responses concise and to the point
                    - Consider ALL available context in your response
                    - If you see code, provide code-specific suggestions
                    - If you see errors, focus on troubleshooting
                    - If you see documentation, help explain or apply it
                    - If you see a previous response, maintain consistency with it
                    """),
                    ("human", "{query}")
                ])

                # Build context description
                context_desc = []
                if 'selected_text' in context:
                    context_desc.append(
                        f"Selected Text (what the user has highlighted):\n{context['selected_text']}")
                if 'last_response' in context:
                    context_desc.append(
                        f"Previous Response:\n{context['last_response']}")

                # Format prompt with context and actual query
                messages = context_prompt.invoke({
                    "context_desc": "\n\n".join(context_desc),
                    "query": actual_query
                })
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
            return f"Error: {str(e)}"
