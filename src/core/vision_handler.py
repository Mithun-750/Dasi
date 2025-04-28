import logging
import os
from typing import Optional, Dict
import base64

from langchain_core.messages import HumanMessage, SystemMessage
# Import necessary LangChain chat models that support vision
# We need to anticipate which providers might be used as vision models
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
# If Ollama or Groq support vision and are configured, add imports here
# from langchain_ollama import ChatOllama
# from langchain_groq import ChatGroq

from ui.settings import Settings
from .prompts_hub import VISION_SYSTEM_PROMPT

# Note: We're removing the VISION_USER_PROMPT import since we'll use the actual user query


class VisionHandler:
    """Handles generating detailed text descriptions from visual input using a dedicated vision model."""

    def __init__(self, settings: Settings):
        self.settings = settings
        # We'll initialize the LLM on demand to avoid loading it if not needed
        self.vision_llm = None
        self.vision_model_info = None
        self._is_initialized = False

        # Connect to settings models_changed signal to reload vision model
        self.settings.models_changed.connect(self.refresh_settings)

        # Load initial model
        self.refresh_settings()

    def refresh_settings(self):
        """Reload settings and vision model configuration."""
        logging.info("Refreshing vision model settings")
        # Clear current model to force reload on next use
        self.vision_llm = None
        self._is_initialized = False

    def has_vision_model_configured(self) -> bool:
        """Check if a vision model is configured in settings."""
        model_info = self.settings.get_vision_model_info()
        return model_info is not None and isinstance(model_info, dict) and bool(model_info.get('id'))

    def _initialize_vision_llm(self) -> bool:
        """Initialize the specific vision LLM based on settings. Returns True on success."""
        if self._is_initialized:  # Avoid re-initialization if already done
            return self.vision_llm is not None

        self.vision_model_info = self.settings.get_vision_model_info()
        if not self.vision_model_info or not isinstance(self.vision_model_info, dict):
            logging.error(
                "VisionHandler: No valid vision model configured in settings.")
            self.vision_llm = None
            self._is_initialized = True  # Mark as initialized (failed)
            return False

        provider = self.vision_model_info.get('provider')
        model_id = self.vision_model_info.get('id')

        # Determine API key source, handling custom providers
        api_key_provider = provider
        if provider and provider.startswith('custom_openai_'):
            # For custom_openai_N, the key is stored under 'custom_openai_N'
            api_key_provider = provider
        elif provider == 'custom_openai':
            # For the original custom_openai, key is stored under 'custom_openai'
            api_key_provider = 'custom_openai'
        # Add other potential provider key mappings if needed

        api_key = self.settings.get_api_key(api_key_provider)

        if not provider or not model_id:
            logging.error(
                f"VisionHandler: Vision model info is incomplete: {self.vision_model_info}")
            self.vision_llm = None
            self._is_initialized = True  # Mark as initialized (failed)
            return False

        # Ollama might not need a key
        if not api_key and provider not in ['ollama']:
            logging.error(
                f"VisionHandler: API key for vision provider '{api_key_provider}' not found.")
            self.vision_llm = None
            self._is_initialized = True
            return False

        # Use a fixed, low temperature for descriptive task; reasonable max tokens
        temperature = 0.1
        max_tokens = 1536  # Increased token limit for potentially very detailed descriptions

        try:
            logging.info(
                f"VisionHandler: Initializing vision LLM - Provider: {provider}, Model: {model_id}")

            if provider == 'google':
                self.vision_llm = ChatGoogleGenerativeAI(
                    model=model_id,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            elif provider == 'openai':
                self.vision_llm = ChatOpenAI(
                    model=model_id,
                    openai_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            elif provider == 'anthropic':
                self.vision_llm = ChatAnthropic(
                    model=model_id,
                    anthropic_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            elif provider.startswith('custom_openai'):
                # Includes 'custom_openai' and 'custom_openai_N'
                base_url = self.settings.get('models', provider, 'base_url')
                if not base_url:
                    logging.error(
                        f"VisionHandler: Base URL for custom OpenAI provider '{provider}' not found.")
                    self.vision_llm = None
                    self._is_initialized = True
                    return False
                self.vision_llm = ChatOpenAI(
                    model=model_id,
                    openai_api_key=api_key,
                    base_url=base_url.rstrip('/') + '/v1',
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            # Add Ollama if needed and supported
            # elif provider == 'ollama':
            #     self.vision_llm = ChatOllama(
            #         model=model_id,
            #         temperature=temperature,
            #         # Add other Ollama specific params if needed
            #     )
            else:
                logging.error(
                    f"VisionHandler: Vision provider '{provider}' is not supported for visual analysis.")
                self.vision_llm = None
                self._is_initialized = True
                return False

            logging.info(
                f"VisionHandler: Successfully initialized vision LLM: {model_id}")
            self._is_initialized = True
            return True

        except Exception as e:
            logging.error(
                f"VisionHandler: Error initializing vision LLM '{model_id}': {str(e)}", exc_info=True)
            self.vision_llm = None
            self._is_initialized = True  # Mark as initialized (failed)
            return False

    def get_visual_description(self, image_data_base64: str, prompt_hint: Optional[str] = None) -> Optional[str]:
        """
        Generates a detailed text description of the visual input using the configured vision model.

        If no vision model is configured, returns None, indicating image should be passed directly
        to the main model.

        Args:
            image_data_base64: The base64 encoded image data (without prefix).
            prompt_hint: Optional text from the user's query to guide the description focus.

        Returns:
            A detailed text description of the visual input, or None if an error occurs or no vision model is configured.
        """
        # Check if a vision model is actually configured
        if not self.has_vision_model_configured():
            logging.info(
                "No vision model configured, image will be passed directly to main model")
            return None

        logging.info(
            "Generating visual description using dedicated vision model")

        if not image_data_base64:
            logging.warning("No image data provided for vision processing")
            return None

        # If vision model is None, try to initialize it
        if self.vision_llm is None:
            self._initialize_vision_llm()

        # If still None after initialization attempt, return error
        if self.vision_llm is None:
            logging.error("Could not initialize vision model")
            return None

        if not self.vision_llm:
            logging.error("VisionHandler: Vision LLM is not available.")
            return None

        # Get system prompt from prompts_hub
        system_prompt = VISION_SYSTEM_PROMPT

        # Instead of using a fixed user prompt, use the actual user query if available
        if prompt_hint and prompt_hint.strip():
            # Use the user's actual query as the primary instruction
            user_prompt_text = f"Based on this query: '{prompt_hint.strip()}', analyze and describe the provided visual input."
            logging.info(
                f"VisionHandler: Using user's query as prompt: {user_prompt_text[:100]}...")
        else:
            # Fallback to a generic prompt only if user query is not available
            user_prompt_text = "Describe the provided visual input in comprehensive detail according to the system instructions."
            logging.info(
                "VisionHandler: Using generic prompt (no user query provided)")

        # Create multimodal message content
        # Ensure the base64 data doesn't have the prefix 'data:image/png;base64,'
        if image_data_base64.startswith('data:'):
            image_data_base64 = image_data_base64.split(',', 1)[-1]

        content_blocks = [
            {"type": "text", "text": user_prompt_text},
            {
                "type": "image_url",
                # Construct the data URL correctly
                "image_url": {"url": f"data:image/png;base64,{image_data_base64}"}
            }
        ]

        message = HumanMessage(content=content_blocks)
        messages_for_vision_model = [
            SystemMessage(content=system_prompt), message]

        try:
            logging.info(
                f"VisionHandler: Sending visual input to vision model '{self.vision_model_info.get('id')}' for analysis.")
            # Use invoke for a single response
            response = self.vision_llm.invoke(messages_for_vision_model)

            description = response.content.strip()

            if not description:
                logging.warning(
                    f"VisionHandler: Vision model '{self.vision_model_info.get('id')}' returned an empty description.")
                return None

            logging.info(
                f"VisionHandler: Received description (length {len(description)}). Preview: {description[:100]}...")
            return description

        except Exception as e:
            logging.error(
                f"VisionHandler: Error getting description from vision model '{self.vision_model_info.get('id')}': {str(e)}", exc_info=True)
            # Potentially provide a more specific error? For now, just None.
            return None
