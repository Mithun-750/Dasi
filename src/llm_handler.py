import os
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv


class LLMHandler:
    def __init__(self):
        """Initialize LLM handler with Gemini model."""
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found in environment variables")

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.7,
            google_api_key=api_key
        )

    def get_response(self, query: str) -> Optional[str]:
        """Get response from LLM for the given query."""
        try:
            response = self.llm.invoke([
                ("system", "You are a helpful AI assistant. "
                 "Provide clear, concise responses."),
                ("human", query)
            ])
            return response.content
        except Exception as e:
            print(f"Error getting LLM response: {e}")
            return None
