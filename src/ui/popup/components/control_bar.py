from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, 
                            QRadioButton, QButtonGroup, QComboBox, 
                            QWidget, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal

class ControlBar(QFrame):
    """Control bar component for mode selection and model choice."""
    mode_changed = pyqtSignal(bool)  # True for compose mode, False for chat mode

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setObjectName("controlBar")
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        control_layout = QVBoxLayout(self)
        control_layout.setContentsMargins(8, 4, 8, 4)
        control_layout.setSpacing(8)

        # Create mode selector container
        mode_container = QFrame()
        mode_container.setObjectName("modeContainer")
        mode_layout = QHBoxLayout(mode_container)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)

        # Create radio buttons
        self.mode_group = QButtonGroup()
        self.chat_mode = QRadioButton("Chat")
        self.compose_mode = QRadioButton("Compose")
        self.chat_mode.setChecked(True)  # Default to chat mode
        
        # Style radio buttons
        radio_style = """
            QRadioButton {
                color: #cccccc;
                font-size: 12px;
                padding: 6px 12px;
                border-radius: 3px;
                background-color: transparent;
                border: none;
                text-align: center;
            }
            QRadioButton:hover {
                background-color: #404040;
            }
            QRadioButton:checked {
                color: white;
                background-color: #2b5c99;
            }
            QRadioButton::indicator {
                width: 0px;
                height: 0px;
            }
        """
        self.chat_mode.setStyleSheet(radio_style)
        self.compose_mode.setStyleSheet(radio_style)
        
        # Set size policies to make buttons expand horizontally
        self.chat_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.compose_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Add to button group
        self.mode_group.addButton(self.chat_mode)
        self.mode_group.addButton(self.compose_mode)
        
        # Connect mode change signal
        self.mode_group.buttonClicked.connect(self._handle_mode_change)
        
        mode_layout.addWidget(self.chat_mode)
        mode_layout.addWidget(self.compose_mode)

        # Create model selector container
        model_container = QWidget()
        model_layout = QHBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)

        self.model_selector = QComboBox()
        self.model_selector.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 12px;
                color: #cccccc;
            }
            QComboBox:hover {
                border-color: #4a4a4a;
                background-color: #323232;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #888;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                selection-background-color: #2b5c99;
                selection-color: white;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 8px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #363636;
            }
            QComboBox::item {
                color: #cccccc;
            }
            QComboBox::drop-down:button {
                border: none;
            }
        """)
        self.update_model_selector()

        model_layout.addWidget(self.model_selector)

        # Add all elements to control bar vertically
        control_layout.addWidget(mode_container)
        control_layout.addWidget(model_container)

        # Set frame style
        self.setStyleSheet("""
            #controlBar {
                background-color: #363636;
                border-radius: 4px;
                padding: 4px;
            }
        """)

    def _handle_mode_change(self, button):
        """Handle mode change between Chat and Compose."""
        is_compose = button == self.compose_mode
        self.mode_changed.emit(is_compose)

    def update_model_selector(self):
        """Update the model selector with currently selected models."""
        # Reload settings from disk
        self.settings.load_settings()

        self.model_selector.clear()
        selected_models = self.settings.get_selected_models()

        if not selected_models:
            self.model_selector.addItem("No models selected")
            self.model_selector.setEnabled(False)
            return

        # Get default model ID
        default_model_id = self.settings.get('models', 'default_model')
        default_index = 0  # Default to first model if no default set

        # Add models with their metadata
        for index, model in enumerate(selected_models):
            # Create a more concise display text
            provider = model['provider']
            name = model['name']
            
            # Format provider name to be more concise
            provider_display = {
                'google': 'Google',
                'openai': 'OpenAI',
                'anthropic': 'Anthropic',
                'ollama': 'Ollama',
                'groq': 'Groq',
                'deepseek': 'Deepseek',
                'together': 'Together',
                'openrouter': 'OpenRouter',
                'custom_openai': 'Custom'
            }.get(provider, provider)
            
            # Create shorter display text for combobox
            display_text = f"{name[:30]}... ({provider_display})" if len(name) > 30 else f"{name} ({provider_display})"
            
            # Full text for tooltip
            full_text = f"{name}\nProvider: {provider_display}"
            
            self.model_selector.addItem(display_text, model)
            # Set tooltip for the current index
            self.model_selector.setItemData(index, full_text, Qt.ItemDataRole.ToolTipRole)
            
            # If this is the default model, store its index
            if default_model_id and model['id'] == default_model_id:
                default_index = index

        self.model_selector.setEnabled(True)

        # Set the default model as current
        self.model_selector.setCurrentIndex(default_index)

        # Configure size policy to expand horizontally
        self.model_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.model_selector.setMaxVisibleItems(10)  # Show max 10 items in dropdown

    def get_selected_model(self):
        """Get the currently selected model info."""
        current_index = self.model_selector.currentIndex()
        if current_index >= 0:
            return self.model_selector.itemData(current_index)
        return None

    def is_compose_mode(self):
        """Check if compose mode is selected."""
        return self.compose_mode.isChecked()
