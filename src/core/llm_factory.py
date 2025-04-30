import os
import logging
from typing import Optional, Dict, Any, List

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_together import ChatTogether
from langchain_xai import ChatXAI

# Local imports
from ui.settings import Settings


def create_llm_instance(
    provider: str,
    model_id: str,
    settings: Settings,
    temperature: float,
    model_info: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Any]:
    """
    Factory function to create and return an LLM instance based on the provider.

    Args:
        provider: The name of the LLM provider (e.g., 'google', 'openai').
        model_id: The specific model ID to use.
        settings: The application settings object.
        temperature: The temperature setting for the LLM.
        model_info: Optional dictionary containing model information (e.g., base_url).
        tools: Optional list of tools to bind to the LLM.

    Returns:
        An initialized LangChain LLM instance or None if initialization fails.
    """
    try:
        api_key = settings.get_api_key(provider)

        # Define available tools
        available_tools = []
        if tools:
            available_tools = tools
            logging.info(f"Binding {len(available_tools)} tools to the LLM")

        llm_instance = None

        if provider == 'google':
            logging.info(f"Creating Google Gemini model: {model_id}")
            llm_instance = ChatGoogleGenerativeAI(
                model=model_id,
                google_api_key=api_key,
                temperature=temperature,
            )
        elif provider == 'openai':
            if 'gpt-4o' in model_id.lower() or 'vision' in model_id.lower():
                llm_instance = ChatOpenAI(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                    openai_api_key=api_key,
                    max_tokens=4096,
                )
            else:
                llm_instance = ChatOpenAI(
                    model=model_id,
                    temperature=temperature,
                    streaming=True,
                    openai_api_key=api_key,
                )
        elif provider == 'ollama':
            llm_instance = ChatOllama(
                model=model_id,
                temperature=temperature,
                base_url="http://localhost:11434",  # TODO: Make base_url configurable
            )
        elif provider == 'groq':
            logging.info(f"Creating Groq model: {model_id}")
            llm_instance = ChatGroq(
                model=model_id,
                groq_api_key=api_key,
                temperature=temperature,
                streaming=True,
            )
        elif provider == 'anthropic':
            if 'claude-3' in model_id.lower():
                llm_instance = ChatAnthropic(
                    model=model_id,
                    anthropic_api_key=api_key,
                    temperature=temperature,
                    streaming=True,
                    max_tokens=4096,
                )
            else:
                llm_instance = ChatAnthropic(
                    model=model_id,
                    anthropic_api_key=api_key,
                    temperature=temperature,
                    streaming=True,
                )
        elif provider == 'deepseek':
            # DeepSeek SDK might read directly from env var
            os.environ["DEEPSEEK_API_KEY"] = api_key if api_key else ""
            llm_instance = ChatDeepSeek(
                model=model_id,
                temperature=temperature,
                streaming=True,
                api_key=api_key  # Pass explicitly too if needed by specific versions
            )
        elif provider == 'together':
            llm_instance = ChatTogether(
                model=model_id,
                together_api_key=api_key,
                temperature=temperature,
                streaming=True,
            )
        elif provider == 'xai':
            llm_instance = ChatXAI(
                model=model_id,
                xai_api_key=api_key,
                temperature=temperature,
                streaming=True,
            )
        elif provider.startswith('custom_openai'):
            # Custom OpenAI provider logic
            base_url = settings.get('models', provider, 'base_url')
            if not base_url or not api_key:
                logging.error(
                    f"Missing configuration for custom OpenAI provider: {provider}")
                return None
            llm_instance = ChatOpenAI(
                model=model_id,
                temperature=temperature,
                streaming=True,
                openai_api_key=api_key,
                base_url=base_url,
            )
        elif provider == 'openrouter':  # Assuming OpenRouter is handled as a distinct provider
            headers = {
                'HTTP-Referer': 'https://github.com/mithuns/dasi',
                'X-Title': 'Dasi',
                'Content-Type': 'application/json'
            }
            llm_instance = ChatOpenAI(
                model=model_id,
                temperature=temperature,
                streaming=True,
                openai_api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers=headers
            )
        else:
            logging.error(f"Unsupported LLM provider: {provider}")
            return None

        # Bind tools to the LLM instance if tools are provided
        if llm_instance and available_tools:
            try:
                logging.info(
                    f"Binding {len(available_tools)} tools to {provider} LLM")
                llm_instance = llm_instance.bind_tools(available_tools)
            except Exception as e:
                logging.error(
                    f"Error binding tools to LLM: {str(e)}", exc_info=True)

        return llm_instance

    except Exception as e:
        logging.error(
            f"Error creating LLM instance for {provider} ({model_id}): {str(e)}", exc_info=True)
        return None
