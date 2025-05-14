import logging
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from .prompts_hub import FILENAME_SUGGESTION_TEMPLATE
from ui.settings import Settings
from .llm_factory import create_llm_instance


class FilenameSuggester:
    """Class to handle filename suggestions based on content and context."""

    def __init__(self, llm, system_prompt: str):
        """Initialize the FilenameSuggester.

        Args:
            llm: The language model instance to use for suggestions (fallback)
            system_prompt: The system prompt to use for the LLM
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.detected_language = None
        self.settings = Settings()

        # Initialize dedicated filename suggester model as None
        # This will be initialized on demand when needed
        self.filename_llm = None
        self.filename_model_info = None

        # Connect to settings models_changed signal to reset the model when settings change
        self.settings.models_changed.connect(self.reset_model)

    def reset_model(self):
        """Reset the filename model when settings change."""
        self.filename_llm = None
        self.filename_model_info = None

    def _initialize_filename_llm(self):
        """Initialize the dedicated filename suggester LLM if configured in settings.

        Returns:
            True if initialization successful and a model is available, False otherwise.
        """
        # Get the filename model info from settings
        self.filename_model_info = self.settings.get_filename_model_info()

        # If no model is configured, just use the default LLM
        if not self.filename_model_info:
            return False

        try:
            # Get provider and model_id from settings
            provider = self.filename_model_info.get('provider')
            model_id = self.filename_model_info.get('id')

            if not provider or not model_id:
                logging.warning("Incomplete filename model info in settings")
                return False

            # Use factory function to create LLM instance
            # Pass low temperature for filename generation
            temperature = 0.1
            logging.info(
                f"Creating filename suggester LLM using factory: {provider}/{model_id}")

            self.filename_llm = create_llm_instance(
                provider=provider,
                model_id=model_id,
                settings=self.settings,
                temperature=temperature,
                model_info=self.filename_model_info,
                # Don't pass tools - not needed for filename generation
                tools=None
            )

            if self.filename_llm:
                logging.info(
                    f"Successfully initialized filename model: {model_id}")
                return True
            else:
                logging.warning(
                    f"Failed to initialize filename model: {model_id}")
                return False

        except Exception as e:
            logging.error(
                f"Error initializing filename model: {str(e)}", exc_info=True)
            self.filename_llm = None
            return False

    def suggest_filename(self, content: str, recent_query: str = "") -> str:
        """Suggest a filename based on content and recent query, including extension.

        Args:
            content: The content to generate a filename for
            recent_query: Recent user query for context (optional)

        Returns:
            A suggested filename with appropriate extension as determined by the LLM
        """
        try:
            # Try to use dedicated filename model if configured
            if not self.filename_llm:
                self._initialize_filename_llm()

            # Use the dedicated model if available, otherwise fall back to the provided LLM
            llm_to_use = self.filename_llm if self.filename_llm else self.llm

            language_hint = self.detected_language if self.detected_language else "None"

            # Create the prompt for filename suggestion using the template
            filename_query = FILENAME_SUGGESTION_TEMPLATE.format(
                detected_language=language_hint,
                recent_query=recent_query,
                content=content[:500]  # Limit content length
            )

            # Create direct message list
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=filename_query)
            ]

            # Invoke the LLM directly
            response = llm_to_use.invoke(messages)
            suggested_filename = response.content.strip().strip('"').strip("'").strip()

            # Basic validation: check if there's likely an extension
            if '.' not in suggested_filename or suggested_filename.endswith('.'):
                logging.warning(
                    f"LLM suggested filename without extension: {suggested_filename}. Appending '.txt'.")
                suggested_filename += ".txt"  # Add a default extension if missing

            # Reset detected language after use
            self.detected_language = None

            return suggested_filename

        except Exception as e:
            logging.error(
                f"Error suggesting filename: {str(e)}", exc_info=True)
            # Return default filename with timestamp and best guess extension
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Use stored language for extension if available, otherwise default to .txt
            extension = ".txt"  # Default extension
            lang_lower = (self.detected_language or "").lower()

            # Simple extension mapping for fallback
            extension_map_fallback = {
                "python": ".py", "py": ".py", "javascript": ".js", "js": ".js",
                "typescript": ".ts", "ts": ".ts", "html": ".html", "css": ".css",
                "json": ".json", "yaml": ".yaml", "yml": ".yaml", "shell": ".sh",
                "bash": ".sh", "sql": ".sql", "markdown": ".md", "md": ".md"
                # Add other common ones if needed
            }
            if lang_lower in extension_map_fallback:
                extension = extension_map_fallback[lang_lower]

            # Reset detected language even on error
            self.detected_language = None

            return f"dasi_response_{timestamp}{extension}"

    def set_detected_language(self, language: Optional[str]):
        """Set the detected language for the next filename suggestion.

        Args:
            language: The detected programming language or None
        """
        self.detected_language = language
