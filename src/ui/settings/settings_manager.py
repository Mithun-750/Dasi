import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
import keyring
import keyring.errors


class Settings(QObject):
    """Settings manager with signals for changes."""
    # Singleton instance
    _instance = None

    # Signals
    models_changed = pyqtSignal()  # Signal emitted when models list changes
    # Signal emitted when custom instructions change
    custom_instructions_changed = pyqtSignal()
    temperature_changed = pyqtSignal()  # Signal emitted when temperature changes
    # Signal emitted when web search settings change
    web_search_changed = pyqtSignal()
    tools_settings_changed = pyqtSignal()  # New signal for tools

    DASI_API_SERVICE_NAME = "dasi.api_keys"

    def __new__(cls):
        """Create a new instance or return the existing one (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize Settings once."""
        # Only initialize once due to singleton pattern
        if self._initialized:
            return

        super().__init__()
        self._initialized = True

        # Get config directory (following XDG specification)
        self.config_dir = Path(
            os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')) / 'dasi'
        self.config_file = self.config_dir / 'settings.json'

        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Default settings
        self.settings = {
            'api_keys': {
                'google': '',
                'openrouter': '',
                'groq': '',
                'custom_openai': '',  # API key for custom OpenAI-compatible model
                'anthropic': '',
                'deepseek': '',
                'together': '',
                'xai': '',
                'google_serper': '',
                'brave_search': '',
                'exa_search': '',
                'searchapi': '',
                'serpapi': '',
                'tavily_search': ''
            },
            'models': {
                # List of {id: str, provider: str, name: str}
                'selected_models': [],
                'custom_openai': {
                    'base_url': '',  # Base URL for custom OpenAI-compatible endpoint
                    'models': []  # List of available model names
                },
                'vision_model_info': None
            },
            'general': {
                'temperature': 0.7,  # Default temperature
                'chat_history_limit': 20,  # Default number of messages to keep
                'custom_instructions': ''  # Default custom instructions
            },
            'web_search': {
                'default_provider': 'google_serper',
                'max_results': 5,
                'scrape_content': True,
                'enabled_providers': [
                    'google_serper',
                    'brave_search',
                    'ddg_search'
                ]
            },
            'tools': {
                'web_search_enabled': True,
                'system_info_enabled': True,
                'terminal_command_enabled': True
            }
        }

        # Load existing settings if they exist
        self.load_settings()

    def load_settings(self):
        """Load settings from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Update recursively to preserve default structure
                    self._update_dict_recursive(self.settings, loaded_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")

    def _update_dict_recursive(self, target: Dict, source: Dict):
        """Update dictionary recursively while preserving structure."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._update_dict_recursive(target[key], value)
            else:
                target[key] = value

    def save_settings(self):
        """Save settings to config file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get(self, *keys, default=None):
        """Get a nested setting value."""
        try:
            current = self.settings
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, *args):
        """Set a nested setting value and save.

        This method can be called in two ways:
        1. set(key1, key2, ..., value) - where the last argument is the value
        2. set(value, key1, key2, ...) - where the first argument is the value (old implementation)
        """
        if not args:
            return False

        # Check how it's being called (old or new style)
        if len(args) >= 3 and isinstance(args[0], str) and isinstance(args[1], str):
            # Called as set(key1, key2, ..., value)
            keys = args[:-1]
            value = args[-1]
        else:
            # Called as set(value, key1, key2, ...)
            value = args[0]
            keys = args[1:]

        if not keys:
            return False

        current = self.settings
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        success = self.save_settings()

        # Emit appropriate signals based on what was changed
        if success:
            # Check if this is a web search setting change
            if keys and keys[0] == 'web_search':
                self.web_search_changed.emit()
            # Check for custom instructions change
            elif keys and keys[0] == 'general' and keys[-1] == 'custom_instructions':
                self.custom_instructions_changed.emit()
            # Check for temperature change
            elif keys and keys[0] == 'general' and keys[-1] == 'temperature':
                self.temperature_changed.emit()
            # Check for model changes
            elif keys[0] == 'models':
                self.models_changed.emit()
            # Check for tools change
            elif keys[0] == 'tools':
                self.tools_settings_changed.emit()

        return success

    def get_api_key(self, provider: str) -> str:
        """Get API key for a specific provider, using keyring if available."""
        # Try to get from keyring first
        try:
            key = keyring.get_password(self.DASI_API_SERVICE_NAME, provider)
            if key is not None:
                return key
        except keyring.errors.KeyringError as e:
            print(f"[Dasi] Keyring error: {e}. Falling back to settings.json.")

        # Fallback: check settings.json (for migration)
        key = self.get('api_keys', provider, default='')
        if key:
            # Try to migrate to keyring
            try:
                keyring.set_password(self.DASI_API_SERVICE_NAME, provider, key)
                # Remove from settings.json after migration
                self.set('api_keys', provider, '')
                print(f"[Dasi] Migrated {provider} API key to system keyring.")
            except keyring.errors.KeyringError as e:
                print(
                    f"[Dasi] Could not migrate {provider} API key to keyring: {e}")
            return key
        return ''

    def set_api_key(self, provider: str, key: str) -> bool:
        """Set API key for a specific provider, using keyring if available."""
        try:
            if key:
                keyring.set_password(self.DASI_API_SERVICE_NAME, provider, key)
                # Remove from settings.json if present
                self.set('api_keys', provider, '')
            else:
                # Remove from keyring
                try:
                    keyring.delete_password(
                        self.DASI_API_SERVICE_NAME, provider)
                except keyring.errors.PasswordDeleteError:
                    pass  # Already deleted or not present
                self.set('api_keys', provider, '')
            success = True
        except keyring.errors.KeyringError as e:
            print(f"[Dasi] Keyring error: {e}. Falling back to settings.json.")
            # Fallback: store in settings.json
            success = self.set('api_keys', provider, key)

        # Emit web_search_changed signal if this is a web search provider
        if success and provider in ['google_serper', 'brave_search', 'exa_search', 'tavily_search']:
            self.web_search_changed.emit()

        return success

    def get_selected_models(self) -> List[Dict[str, str]]:
        """Get list of selected models with metadata."""
        models = self.get('models', 'selected_models', default=[])
        # Ensure we're returning a list of dictionaries
        if not models:
            return []
        # If we get a list of strings (old format), convert to dictionaries
        if models and isinstance(models[0], str):
            return [{'id': model, 'provider': 'google', 'name': model} for model in models]
        return models

    def get_selected_model_ids(self) -> List[str]:
        """Get list of just the model IDs."""
        return [model['id'] for model in self.get_selected_models()]

    def add_selected_model(self, model_id: str, provider: str, display_name: str = None) -> bool:
        """Add a model to selected models if not already present."""
        current_models = self.get_selected_models()
        if not any(m['id'] == model_id for m in current_models):
            model_info = {
                'id': model_id,
                'provider': provider,
                'name': display_name or model_id
            }
            current_models.append(model_info)
            success = self.set('models', 'selected_models', current_models)
            if success:
                # Reload settings to ensure we have latest data
                self.load_settings()
                self.models_changed.emit()
            return success
        return True

    def remove_selected_model(self, model_id: str) -> bool:
        """Remove a model from selected models."""
        current_models = self.get_selected_models()
        filtered_models = [m for m in current_models if m['id'] != model_id]
        if len(filtered_models) != len(current_models):
            success = self.set('models', 'selected_models', filtered_models)
            if success:
                # Reload settings to ensure we have latest data
                self.load_settings()
                self.models_changed.emit()
            return success
        return True

    def get_vision_model_info(self) -> Optional[dict]:
        """Get the full information dictionary for the configured vision model."""
        return self.get('models', 'vision_model_info', default=None)

    def set_vision_model_info(self, model_info: Optional[dict]):
        """Set the full information dictionary for the vision model."""
        self.set('models', 'vision_model_info', model_info)
        self.models_changed.emit()

    def reset_defaults(self):
        """Reset all settings to their default values."""
        self.set('general', 'custom_instructions', '')
        self.set('general', 'temperature', 0.7)
        self.set('tools', 'web_search_enabled', True)
        self.set('tools', 'system_info_enabled', True)
        self.set('tools', 'terminal_command_enabled', True)
        self.set('models', 'selected_models', [])
        self.set('models', 'vision_model_info', None)
        self.set('web_search', 'default_provider', 'google_serper')
        self.set('web_search', 'max_results', 5)
        self.set('web_search', 'scrape_content', True)
        self.set('web_search', 'enabled_providers', [
                 'google_serper', 'brave_search', 'ddg_search'])
        self.save_settings()
        self.load_settings()
        self.models_changed.emit()
        self.web_search_changed.emit()
        self.tools_settings_changed.emit()
        self.api_keys_changed.emit()

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a specific tool is enabled in settings.

        Args:
            tool_name: The base name of the tool (e.g., 'web_search', 'system_info').

        Returns:
            True if the tool is enabled, False otherwise.
        """
        # Try different possible key formats
        setting_key = f'{tool_name}_enabled'
        setting_key_alt1 = f'enable_{tool_name}'
        setting_key_alt2 = f'enable_{tool_name}_enabled'
        setting_key_alt3 = f'Enable {tool_name.replace("_", " ").title()}'
        setting_key_alt4 = f'Enable {tool_name.replace("_", " ").title()} Execution'

        # Check all possible setting keys
        setting_value = self.get('tools', setting_key, default=None)
        if setting_value is not None:
            return setting_value

        setting_value = self.get('tools', setting_key_alt1, default=None)
        if setting_value is not None:
            return setting_value

        setting_value = self.get('tools', setting_key_alt2, default=None)
        if setting_value is not None:
            return setting_value

        setting_value = self.get('tools', setting_key_alt3, default=None)
        if setting_value is not None:
            return setting_value

        setting_value = self.get('tools', setting_key_alt4, default=None)
        if setting_value is not None:
            return setting_value

        # Default to True if no setting found
        return True
