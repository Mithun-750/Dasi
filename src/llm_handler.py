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

    def get_response(self, query: str, callback=None) -> Optional[str]:
        """Get response from LLM for the given query. If callback is provided, stream the response."""
        try:
            # Parse context and query
            if "Context:" in query:
                context_section, actual_query = query.split("\n\nQuery:\n", 1)
                context_section = context_section.replace("Context:\n", "").strip()
                
                # Parse different types of context
                context = {}
                if "Selected Text:" in context_section:
                    selected_text = context_section.split("Selected Text:\n", 1)[1]
                    selected_text = selected_text.split("\n\n", 1)[0].strip()
                    context['selected_text'] = selected_text
                
                if "Last Response:" in context_section:
                    last_response = context_section.split("Last Response:\n", 1)[1]
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
                    context_desc.append(f"Selected Text (what the user has highlighted):\n{context['selected_text']}")
                if 'last_response' in context:
                    context_desc.append(f"Previous Response:\n{context['last_response']}")
                
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
            print(f"Error getting LLM response: {e}")
            return None
