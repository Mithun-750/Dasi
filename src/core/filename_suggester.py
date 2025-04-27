import logging
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from .prompts_hub import FILENAME_SUGGESTION_TEMPLATE


class FilenameSuggester:
    """Class to handle filename suggestions based on content and context."""

    def __init__(self, llm, system_prompt: str):
        """Initialize the FilenameSuggester.

        Args:
            llm: The language model instance to use for suggestions
            system_prompt: The system prompt to use for the LLM
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.detected_language = None

    def suggest_filename(self, content: str, recent_query: str = "") -> str:
        """Suggest a filename based on content and recent query.

        Args:
            content: The content to generate a filename for
            recent_query: Recent user query for context (optional)

        Returns:
            A suggested filename with appropriate extension
        """
        try:
            # Default extension and hint
            file_extension = ".md"
            extension_hint = ""

            # Check if we have a detected language that would suggest a better extension
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

            # Create the prompt for filename suggestion using the template
            filename_query = FILENAME_SUGGESTION_TEMPLATE.format(
                file_extension=file_extension,
                extension_hint=extension_hint,
                recent_query=recent_query,
                content=content[:500]  # Limit content length
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
            elif lang_lower in ["text", "plaintext"]:
                extension = ".txt"

            # Reset detected language
            self.detected_language = None

            return f"dasi_response_{timestamp}{extension}"

    def set_detected_language(self, language: str):
        """Set the detected language for the next filename suggestion.

        Args:
            language: The detected programming language
        """
        self.detected_language = language
