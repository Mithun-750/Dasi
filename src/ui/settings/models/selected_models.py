import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QEvent, QObject, pyqtSignal

from ..general_tab import SectionFrame
from .ui_components import RoundLabel, RoundButton
from .model_fetcher import create_model_tooltip


class HoverEventFilter(QObject):
    """Event filter for handling hover effects on model items."""

    def __init__(self, widget, default_btn, remove_btn, is_default=False, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.default_btn = default_btn
        self.remove_btn = remove_btn
        self.is_default = is_default
        # Keep reference to original style to avoid affecting inner elements
        self.original_style = """
            #modelItem {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """
        self.hover_style = """
            #modelItem {
                background-color: #2a2a2a;
                border: 1px solid #444444;
                border-radius: 8px;
            }
        """

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            # Show buttons
            if not self.is_default:
                self.default_btn.setVisible(True)
            self.remove_btn.setVisible(True)

            # Apply hover style only to the main widget
            self.widget.setStyleSheet(self.hover_style)

        elif event.type() == QEvent.Type.Leave:
            # Hide buttons
            self.default_btn.setVisible(False)
            self.remove_btn.setVisible(False)

            # Restore original style
            self.widget.setStyleSheet(self.original_style)

        return False


class SelectedModelsComponent(QWidget):
    """Component for managing selected models."""

    model_changed = pyqtSignal()  # Signal for when models are added/removed/modified

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        """Initialize the UI for the selected models component."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Selected Models Section
        self.models_section = SectionFrame(
            "Selected Models",
            "Models that will be available for use in Dasi. Set a default model that will be used when no specific model is requested."
        )

        # Selected models list with modern styling
        self.models_list = QListWidget()
        self.models_list.setFrameShape(QFrame.Shape.NoFrame)
        self.models_list.setSpacing(8)  # Increased spacing between items
        self.models_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 4px 0;
            }
            QListWidget::item:selected {
                background-color: transparent;
                border: none;
            }
            QListWidget::item:hover {
                background-color: transparent;
                border: none;
            }
        """)

        self.models_section.layout.addWidget(self.models_list)
        layout.addWidget(self.models_section)

        # Load selected models
        self.load_selected_models()

    def load_selected_models(self):
        """Load selected models into the list."""
        self.models_list.clear()
        for model in self.settings.get_selected_models():
            self.add_model_to_list(model)

    def add_model_to_list(self, model_info: dict):
        """Add a model to the list widget with a remove button."""
        item = QListWidgetItem()
        item.setBackground(Qt.GlobalColor.transparent)
        self.models_list.addItem(item)

        # Main container widget with single border
        widget = QWidget()
        # Give it a specific name for styling
        widget.setObjectName("modelItem")
        widget.setStyleSheet("""
            #modelItem {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        # Create tooltip for the model
        tooltip = create_model_tooltip(model_info)
        widget.setToolTip(tooltip)

        # Use a single horizontal layout
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Create content layout for text directly without any container
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # Create name and provider labels
        name_label = QLabel(model_info['name'])
        name_label.setAutoFillBackground(False)
        name_label.setFrameShape(QFrame.Shape.NoFrame)
        name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
        """)

        provider_label = QLabel(f"Provider: {model_info['provider']}")
        provider_label.setAutoFillBackground(False)
        provider_label.setFrameShape(QFrame.Shape.NoFrame)
        provider_label.setStyleSheet("""
            font-size: 12px;
            color: #aaaaaa;
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
        """)

        # Add labels to content layout
        content_layout.addWidget(name_label)
        content_layout.addWidget(provider_label)

        # Add the layout directly to main layout
        layout.addLayout(content_layout, 1)  # Give it a stretch factor of 1

        # Create actions layout directly (no container widget)
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)
        actions_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Default model indicator
        is_default = self.settings.get(
            'models', 'default_model') == model_info['id']
        default_label = RoundLabel("Default")
        default_label.setVisible(is_default)

        # Set Default button with modern styling
        default_btn = QPushButton("Set Default")
        default_btn.setStyleSheet("""
            padding: 4px 12px;
            font-size: 12px;
            border-radius: 12px;
            background-color: transparent;
            border: 1px solid rgba(230, 126, 34, 0.3);
            color: #e67e22;
        """)
        default_btn.setVisible(False)
        default_btn.clicked.connect(
            lambda: self.set_default_model(model_info['id']))

        # Add hover effects with event filter
        default_btn.enterEvent = lambda e: default_btn.setStyleSheet("""
            padding: 4px 12px;
            font-size: 12px;
            border-radius: 12px;
            background-color: rgba(230, 126, 34, 0.1);
            border: 1px solid rgba(230, 126, 34, 0.4);
            color: #e67e22;
        """)
        default_btn.leaveEvent = lambda e: default_btn.setStyleSheet("""
            padding: 4px 12px;
            font-size: 12px;
            border-radius: 12px;
            background-color: transparent;
            border: 1px solid rgba(230, 126, 34, 0.3);
            color: #e67e22;
        """)

        # Remove button with modern styling - now using RoundButton with custom painting
        remove_btn = RoundButton("×")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setVisible(False)
        remove_btn.clicked.connect(lambda: self.remove_model(model_info['id']))

        # Add content to actions layout
        actions_layout.addWidget(default_label)
        actions_layout.addWidget(default_btn)
        actions_layout.addWidget(remove_btn)

        # Add actions layout to main layout
        layout.addLayout(actions_layout)

        # Install event filter for hover effects
        hover_filter = HoverEventFilter(
            widget, default_btn, remove_btn, is_default, widget)
        widget.installEventFilter(hover_filter)
        widget.hover_filter = hover_filter  # Keep reference to avoid garbage collection

        # Set appropriate size for the item
        size_hint = widget.sizeHint()
        size_hint.setHeight(max(64, size_hint.height()))
        item.setSizeHint(size_hint)

        self.models_list.setItemWidget(item, widget)

    def set_default_model(self, model_id: str):
        """Set a model as the default model."""
        # Save the default model in settings
        self.settings.set('models', 'default_model', model_id)

        # Refresh the list to update the UI
        self.load_selected_models()

        # Emit signal that model changed
        self.model_changed.emit()

        # Show confirmation message
        QMessageBox.information(
            self,
            "Success",
            f"Default model has been set successfully.",
            QMessageBox.StandardButton.Ok
        )

    def add_model(self, model_info: dict):
        """Add a model to the selected models list."""
        if model_info and model_info['id'] not in self.settings.get_selected_model_ids():
            # Add model to settings
            if self.settings.add_selected_model(
                model_info['id'],
                model_info['provider'],
                model_info['name']
            ):
                # Reload settings from disk to ensure we have latest data
                self.settings.load_settings()
                # Update UI
                self.add_model_to_list(model_info)
                # Emit signal
                self.model_changed.emit()
                return True
        return False

    def remove_model(self, model_id: str):
        """Remove a model from the list."""
        if self.settings.remove_selected_model(model_id):
            # Reload settings from disk
            self.settings.load_settings()
            # Refresh the list
            self.load_selected_models()
            # Emit signal
            self.model_changed.emit()
            return True
        return False

    def remove_models_by_provider(self, provider: str):
        """Remove all models from a specific provider when its API key is cleared."""
        if not provider:
            return False

        # Get current selected models
        current_models = self.settings.get_selected_models()

        # Find models from the specified provider
        # For custom_openai providers, we need to match the exact provider key
        if provider == 'custom_openai' or provider.startswith('custom_openai_'):
            models_to_remove = [
                model['id'] for model in current_models if model['provider'] == provider]
        else:
            # For standard providers, remove all models from that provider
            models_to_remove = [
                model['id'] for model in current_models if model['provider'] == provider]

        if not models_to_remove:
            # No models to remove
            return False

        # Remove each model
        removed_any = False
        for model_id in models_to_remove:
            if self.settings.remove_selected_model(model_id):
                removed_any = True

        if removed_any:
            # Reload settings from disk
            self.settings.load_settings()
            # Refresh the list
            self.load_selected_models()
            # Emit signal
            self.model_changed.emit()

            # Log the removal
            logging.info(
                f"Removed {len(models_to_remove)} models from provider '{provider}' due to API key reset")

            # Check if the default model was removed
            default_model_id = self.settings.get('models', 'default_model')
            if default_model_id in models_to_remove:
                # Reset the default model
                self.settings.set('models', 'default_model',
                                  "")  # Set ID to empty string
                logging.info(
                    f"Reset default model as it was from provider '{provider}'")

            # Format the provider name for display
            display_provider = provider
            if provider.startswith('custom_openai_'):
                index = provider.split('_')[-1]
                display_provider = f"Custom OpenAI Model #{int(index)+1}"
            elif provider == 'custom_openai':
                display_provider = "Custom OpenAI Model"
            else:
                display_provider = provider.title()

            QMessageBox.information(
                self,
                "Models Removed",
                f"Removed {len(models_to_remove)} models from {display_provider} because the API key was cleared.",
                QMessageBox.StandardButton.Ok
            )

            return True

        return False
