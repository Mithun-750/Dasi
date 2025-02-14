import os
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from ui.settings_window import Settings


class LLMHandler:
    def __init__(self):
        """Initialize LLM handler with Gemini model."""
        settings = Settings()
        api_key = settings.get('google_api_key')
        if not api_key:
            raise ValueError("Google API key not found in settings")

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.7,
            google_api_key=api_key
        )

        # Create prompt template for direct responses
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

    def get_response(self, query: str) -> Optional[str]:
        """Get response from LLM for the given query."""
        try:
            # Check if query contains selected text context
            if "Selected Text Context:" in query:
                context, actual_query = query.split("\n\nQuery:\n", 1)
                context = context.replace(
                    "Selected Text Context:\n", "").strip()

                # Create a special prompt for queries with context
                context_prompt = ChatPromptTemplate([
                    ("system", """
                    You are Dasi, an intelligent desktop copilot that helps users with their daily computer tasks. You appear when users press Ctrl+Alt+Shift+I, showing a popup near their cursor. You can see what text they've selected in any window or application when they activated you.

                    About the selected text:
                    - This is the exact text that was highlighted/selected when the user activated you
                    - It could be code, documentation, error messages, or any text from any application
                    - The text provides important context for understanding the user's question
                    - Consider the text's format, structure, and potential meaning in your response

                    IMPORTANT RULES:
                    - Never introduce yourself or add pleasantries
                    - Never explain what you're doing
                    - Never wrap responses in quotes or code blocks unless specifically requested
                    - Never say things like 'here's the response' or 'here's what I generated'
                    - Just provide the direct answer or content requested
                    - Keep responses concise and to the point
                    - Make sure your response takes into account both the selected text and the query
                    - If the selected text is code, consider providing code-specific suggestions
                    - If the selected text is an error, focus on troubleshooting
                    - If the selected text is documentation, help explain or apply it
                    
                    Selected Text:
                    {context}
                    """),
                    ("human", "{query}")
                ])

                # Format prompt with context and actual query
                messages = context_prompt.invoke({
                    "context": context,
                    "query": actual_query
                })
            else:
                # Use default prompt for queries without context
                messages = self.prompt.invoke({"query": query})

            # Get response
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            print(f"Error getting LLM response: {e}")
            return None
