import logging
import requests
from PyQt6.QtCore import QThread, pyqtSignal


class ModelFetchWorker(QThread):
    """Worker thread for fetching models from various providers."""
    finished = pyqtSignal(list)  # Emits list of model names
    error = pyqtSignal(str)      # Emits error message

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
        try:
            # Fetch models from all providers
            google_models = self.fetch_google_models()
            openrouter_models = self.fetch_openrouter_models()
            ollama_models = self.fetch_ollama_models()
            groq_models = self.fetch_groq_models()
            openai_models = self.fetch_openai_models()
            anthropic_models = self.fetch_anthropic_models()
            deepseek_models = self.fetch_deepseek_models()
            together_models = self.fetch_together_models()
            xai_models = self.fetch_xai_models()

            # Combine all models
            all_models = (google_models + openrouter_models +
                          ollama_models + groq_models + openai_models +
                          anthropic_models + deepseek_models + together_models +
                          xai_models)

            if not all_models:
                self.error.emit(
                    "No models found. Please check your API keys and model configurations.")
                return

            self.finished.emit(all_models)
        except Exception as e:
            self.error.emit(str(e))


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
