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
            You are Dasi, a Linux copilot focused on direct and concise responses.
            IMPORTANT RULES:
            - Never introduce yourself or add pleasantries
            - Never explain what you're doing
            - Never wrap responses in quotes or code blocks unless specifically requested
            - Never say things like 'here's the response' or 'here's what I generated'
            - Just provide the direct answer or content requested
            - If asked to generate content (email, code, etc), output only the content
            - Keep responses concise and to the point
            """),
            ("human", "{query}")
        ])

    def get_response(self, query: str) -> Optional[str]:
        """Get response from LLM for the given query."""
        try:
            # Format prompt with query
            messages = self.prompt.invoke({"query": query})
            # Get response
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            print(f"Error getting LLM response: {e}")
            return None
