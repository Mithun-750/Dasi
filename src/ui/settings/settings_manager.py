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
                'google': ''
            },
            'models': {
                'selected_models': []
            },
            'general': {}
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
        current = self.settings
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, default)
            else:
                return default
        return current

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

    def get_selected_models(self) -> List[str]:
        """Get list of selected models."""
        return self.get('models', 'selected_models', default=[])

    def set_selected_models(self, models: List[str]) -> bool:
        """Set list of selected models."""
        success = self.set(models, 'models', 'selected_models')
        if success:
            self.models_changed.emit()  # Emit signal when models change
        return success

    def add_selected_model(self, model: str) -> bool:
        """Add a model to selected models if not already present."""
        current_models = self.get_selected_models()
        if model not in current_models:
            current_models.append(model)
            success = self.set_selected_models(current_models)
            if success:
                self.models_changed.emit()  # Emit signal when models change
            return success
        return True

    def remove_selected_model(self, model: str) -> bool:
        """Remove a model from selected models."""
        current_models = self.get_selected_models()
        if model in current_models:
            current_models.remove(model)
            success = self.set_selected_models(current_models)
            if success:
                self.models_changed.emit()  # Emit signal when models change
            return success
        return True
