import os
import json
from pathlib import Path
from typing import List, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal


class Settings(QObject):
    """Settings manager with signals for changes."""
    models_changed = pyqtSignal()  # Signal emitted when models list changes

    def __init__(self):
        super().__init__()
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
                'custom_openai': ''  # API key for custom OpenAI-compatible model
            },
            'models': {
                # List of {id: str, provider: str, name: str}
                'selected_models': [],
                'custom_openai': {
                    'base_url': '',  # Base URL for custom OpenAI-compatible endpoint
                    'models': []  # List of available model names
                }
            },
            'general': {
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

    def set(self, value, *keys):
        """Set a nested setting value and save."""
        if not keys:
            return False

        current = self.settings
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        return self.save_settings()

    def get_api_key(self, provider: str) -> str:
        """Get API key for a specific provider."""
        return self.get('api_keys', provider, default='')

    def set_api_key(self, provider: str, key: str) -> bool:
        """Set API key for a specific provider."""
        return self.set(key, 'api_keys', provider)

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
            success = self.set(current_models, 'models', 'selected_models')
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
            success = self.set(filtered_models, 'models', 'selected_models')
            if success:
                # Reload settings to ensure we have latest data
                self.load_settings()
                self.models_changed.emit()
            return success
        return True
