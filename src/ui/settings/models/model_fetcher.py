import logging
import requests
from PyQt6.QtCore import QThread, pyqtSignal


class ModelFetchWorker(QThread):
    """Worker thread for fetching models from various providers."""
    finished = pyqtSignal(list)  # Emits list of model names
    error = pyqtSignal(str)      # Emits error message
    # Signal to indicate that no providers are configured or available
    no_providers = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def fetch_google_models(self):
        """Fetch models from Google AI API."""
        api_key = self.settings.get_api_key('google')
        if not api_key:
            return []

        try:
            response = requests.get(
                'https://generativelanguage.googleapis.com/v1beta/models',
                params={'key': api_key}
            )
            response.raise_for_status()
            models = response.json().get('models', [])

            # Filter for models that support text generation
            text_models = []
            for model in models:
                if any(method in model.get('supportedGenerationMethods', [])
                       for method in ['generateText', 'generateContent']):
                    model_info = {
                        'id': model['name'],
                        'provider': 'google',
                        'name': model.get('displayName', model['name'])
                    }

                    # Preserve additional model attributes that might be useful
                    if 'description' in model:
                        model_info['description'] = model['description']
                    if 'inputTokenLimit' in model:
                        model_info['inputTokenLimit'] = model['inputTokenLimit']
                    if 'outputTokenLimit' in model:
                        model_info['outputTokenLimit'] = model['outputTokenLimit']
                    if 'supportedGenerationMethods' in model:
                        model_info['supportedMethods'] = model['supportedGenerationMethods']

                    text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Google models: {str(e)}")
            return []

    def fetch_openrouter_models(self):
        """Fetch models from OpenRouter API."""
        api_key = self.settings.get_api_key('openrouter')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/mithuns/dasi',
                'X-Title': 'Dasi'
            }

            response = requests.get(
                'https://openrouter.ai/api/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Filter for text-to-text models
            text_models = []
            for model in models:
                if model.get('architecture', {}).get('modality') == 'text->text':
                    model_info = {
                        'id': model['id'],
                        'provider': 'openrouter',
                        'name': model.get('name', model['id'])
                    }

                    # Store additional model info
                    if 'context_length' in model:
                        model_info['inputTokenLimit'] = model['context_length']
                    if 'pricing' in model:
                        model_info['pricing'] = model['pricing']
                    if 'description' in model:
                        model_info['description'] = model['description']
                    if 'mantained_by' in model:
                        model_info['maintainedBy'] = model['mantained_by']
                    if 'architecture' in model and isinstance(model['architecture'], dict):
                        arch = model['architecture']
                        if 'vision' in arch and arch['vision']:
                            model_info['hasVision'] = True
                        if 'features' in arch:
                            model_info['features'] = arch['features']

                    text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching OpenRouter models: {str(e)}")
            return []

    def fetch_ollama_models(self):
        """Fetch models from local Ollama instance."""
        try:
            response = requests.get('http://localhost:11434/api/tags')
            response.raise_for_status()
            models = response.json().get('models', [])

            text_models = []
            for model in models:
                model_info = {
                    'id': model['name'],
                    'provider': 'ollama',
                    'name': model['name']
                }
                text_models.append(model_info)
            return text_models
        except requests.exceptions.ConnectionError:
            logging.warning("Ollama server not running or not accessible")
            return []
        except Exception as e:
            logging.error(f"Error fetching Ollama models: {str(e)}")
            return []

    def fetch_groq_models(self):
        """Fetch models from Groq API."""
        api_key = self.settings.get_api_key('groq')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.groq.com/openai/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Format models
            text_models = []
            for model in models:
                model_info = {
                    'id': model['id'],
                    'provider': 'groq',
                    # Use ID as name since that's what Groq provides
                    'name': model.get('id')
                }

                # Store additional info
                if 'created' in model:
                    model_info['created'] = model['created']
                if 'owned_by' in model:
                    model_info['ownedBy'] = model['owned_by']
                if 'context_window' in model:
                    model_info['inputTokenLimit'] = model['context_window']

                text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Groq models: {str(e)}")
            return []

    def fetch_openai_models(self):
        """Fetch models from OpenAI API."""
        api_key = self.settings.get_api_key('openai')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.openai.com/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Filter for chat models
            text_models = []
            for model in models:
                if 'gpt' in model['id'].lower():  # Filter for GPT models
                    model_info = {
                        'id': model['id'],
                        'provider': 'openai',
                        'name': model['id']
                    }

                    # Store additional info when available
                    if 'created' in model:
                        model_info['created'] = model['created']
                    if 'owned_by' in model:
                        model_info['ownedBy'] = model['owned_by']
                    if 'capabilities' in model:
                        model_info['capabilities'] = model['capabilities']

                    text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching OpenAI models: {str(e)}")
            return []

    def fetch_anthropic_models(self):
        """Fetch models from Anthropic API."""
        api_key = self.settings.get_api_key('anthropic')
        if not api_key:
            logging.error("Anthropic API key not found.")
            return []

        try:
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.anthropic.com/v1/models', headers=headers)

            if response.status_code == 200:
                models = response.json().get('data', [])
                text_models = []
                for model in models:
                    model_info = {
                        'id': model['id'],
                        'provider': 'anthropic',
                        'name': model.get('display_name', model['id'])
                    }

                    # Store additional info
                    if 'description' in model:
                        model_info['description'] = model['description']
                    if 'max_tokens' in model:
                        model_info['outputTokenLimit'] = model['max_tokens']
                    if 'context_window' in model:
                        model_info['inputTokenLimit'] = model['context_window']
                    if 'capabilities' in model:
                        model_info['capabilities'] = model['capabilities']

                    text_models.append(model_info)
                return text_models
            else:
                logging.error(
                    f"Failed to fetch models. Status code: {response.status_code}, Response: {response.text}")
                return []
        except Exception as e:
            logging.error(f"Error fetching Anthropic models: {str(e)}")
            return []

    def fetch_deepseek_models(self):
        """Fetch models from Deepseek API."""
        api_key = self.settings.get_api_key('deepseek')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.deepseek.com/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Format models
            text_models = []
            for model in models:
                model_info = {
                    'id': model['id'],
                    'provider': 'deepseek',
                    'name': model.get('name', model['id'])
                }
                text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Deepseek models: {str(e)}")
            return []

    def fetch_together_models(self):
        """Fetch models from Together AI API."""
        api_key = self.settings.get_api_key('together')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.together.xyz/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json()

            # Format models
            text_models = []
            for model in models:
                model_info = {
                    'id': model['id'],
                    'provider': 'together',
                    'name': model.get('name', model['id'])
                }
                text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Together AI models: {str(e)}")
            return []

    def fetch_xai_models(self):
        """Fetch models from xAI (Grok) API."""
        api_key = self.settings.get_api_key('xai')
        if not api_key:
            return []

        try:
            # xAI currently offers limited models, so we'll hardcode them
            # This can be updated when xAI expands their model offerings
            models = [
                {
                    'id': 'grok-beta',
                    'provider': 'xai',
                    'name': 'Grok Beta'
                },
                {
                    'id': 'grok-1',
                    'provider': 'xai',
                    'name': 'Grok-1'
                }
            ]

            return models
        except Exception as e:
            logging.error(f"Error setting up xAI models: {str(e)}")
            return []

    def run(self):
        """Fetch models from all configured providers."""
        all_models = []
        providers_checked = False

        # 1. Check for Ollama first (local and potentially faster)
        ollama_available = False
        try:
            # Quick check if Ollama is running
            response = requests.get(
                'http://localhost:11434/api/tags', timeout=0.5)
            if response.status_code == 200:
                ollama_available = True
                ollama_models = self.fetch_ollama_models()
                all_models.extend(ollama_models)
                providers_checked = True  # Mark that we found at least one potential source
        except requests.exceptions.RequestException:
            logging.warning(
                "Ollama server not running or not accessible during check.")
        except Exception as e:
            logging.error(f"Error checking/fetching Ollama: {str(e)}")

        # 2. Check API keys for other providers
        has_other_providers = False
        providers_to_check = ['google', 'openrouter', 'groq',
                              'openai', 'anthropic', 'deepseek', 'together', 'xai']
        for provider in providers_to_check:
            if self.settings.get_api_key(provider):
                has_other_providers = True
                break

        # 3. Check for custom OpenAI models (original and indexed)
        has_custom_openai = False
        # Check the original custom_openai model
        custom_model_id = self.settings.get(
            'models', 'custom_openai', 'model_id')
        custom_base_url = self.settings.get(
            'models', 'custom_openai', 'base_url')
        custom_api_key = self.settings.get_api_key('custom_openai')
        if custom_model_id and custom_base_url and custom_api_key:
            has_custom_openai = True

        # Check for additional custom OpenAI models if the first wasn't found
        if not has_custom_openai:
            index = 1
            while True:
                settings_key = f"custom_openai_{index}"
                model_id = self.settings.get(
                    'models', settings_key, 'model_id')
                base_url = self.settings.get(
                    'models', settings_key, 'base_url')
                api_key = self.settings.get_api_key(settings_key)
                if model_id and base_url and api_key:
                    has_custom_openai = True
                    break
                if index > 10:  # Limit the search
                    break
                index += 1

        # If no Ollama, no API keys, and no custom models, emit no_providers and exit
        if not ollama_available and not has_other_providers and not has_custom_openai:
            self.no_providers.emit()
            self.finished.emit([])  # Emit empty list as well
            return

        # Mark that we need to check providers if keys or custom models exist
        if has_other_providers or has_custom_openai:
            providers_checked = True

        # Fetch from providers with API keys if needed
        if has_other_providers:
            all_models.extend(self.fetch_google_models())
            all_models.extend(self.fetch_openrouter_models())
            all_models.extend(self.fetch_groq_models())
            all_models.extend(self.fetch_openai_models())
            all_models.extend(self.fetch_anthropic_models())
            all_models.extend(self.fetch_deepseek_models())
            all_models.extend(self.fetch_together_models())
            all_models.extend(self.fetch_xai_models())

        # Add custom OpenAI models (handled in _on_fetch_success in the main tab now)
        # The main tab will check settings again to add custom ones after fetching

        if not providers_checked:
            # This case should ideally not be reached if the initial check logic is correct,
            # but as a fallback, if somehow we get here without checking anything, emit no_providers.
            logging.warning(
                "ModelFetchWorker reached end without checking any providers.")
            self.no_providers.emit()
            self.finished.emit([])
            return

        try:
            # Sort models alphabetically by name for consistent display
            all_models.sort(key=lambda x: x.get('name', '').lower())
            self.finished.emit(all_models)
        except Exception as e:
            self.error.emit(f"Error processing models: {str(e)}")


def create_model_tooltip(model):
    """Create a descriptive tooltip from model information."""
    # Start with basic model info
    tooltip_parts = [
        f"<b>{model['name']}</b>",
        f"Provider: {model['provider']}",
        f"ID: {model['id']}"
    ]

    # Add description if available
    if 'description' in model and model['description']:
        # Truncate long descriptions
        desc = model['description']
        if len(desc) > 300:
            desc = desc[:300] + "..."
        tooltip_parts.append(f"Description: {desc}")

    # Add token limits if available
    if 'inputTokenLimit' in model:
        tooltip_parts.append(
            f"Input token limit: {model['inputTokenLimit']}")
    if 'outputTokenLimit' in model:
        tooltip_parts.append(
            f"Output token limit: {model['outputTokenLimit']}")

    # Add capabilities if available
    if 'supportedMethods' in model and model['supportedMethods']:
        methods = ', '.join(model['supportedMethods'])
        tooltip_parts.append(f"Capabilities: {methods}")
    if 'capabilities' in model and model['capabilities']:
        if isinstance(model['capabilities'], list):
            capabilities = ', '.join(model['capabilities'])
        elif isinstance(model['capabilities'], dict):
            capabilities = ', '.join(model['capabilities'].keys())
        else:
            capabilities = str(model['capabilities'])
        tooltip_parts.append(f"Features: {capabilities}")

    # Add vision capability if explicitly noted
    if 'hasVision' in model and model['hasVision']:
        tooltip_parts.append("<b>Supports vision/images</b>")

    # Add creation date if available
    if 'created' in model:
        # Try to format the timestamp if it's a number
        try:
            from datetime import datetime
            created_date = datetime.fromtimestamp(
                model['created']).strftime('%Y-%m-%d')
            tooltip_parts.append(f"Created: {created_date}")
        except:
            tooltip_parts.append(f"Created: {model['created']}")

    # Add ownership info if available
    if 'ownedBy' in model:
        tooltip_parts.append(f"Owned by: {model['ownedBy']}")
    if 'maintainedBy' in model:
        tooltip_parts.append(f"Maintained by: {model['maintainedBy']}")

    # Join all parts with HTML line breaks for proper formatting
    return "<br>".join(tooltip_parts)
