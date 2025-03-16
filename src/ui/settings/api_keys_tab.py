from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from .settings_manager import Settings
import logging


class APIKeysTab(QWidget):
    # Signal emitted when an API key is cleared
    api_key_cleared = pyqtSignal(str)
    
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.custom_openai_sections = []  # Track custom OpenAI sections
        self.init_ui()
        
        # Connect the api_key_cleared signal to any slots that need it
        # This will be connected externally by the settings dialog

    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("API Keys")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Create content widget for scroll area
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 20, 0)  # Right margin for scrollbar

        # LLM API Keys Section Title
        llm_title = QLabel("LLM API Keys")
        llm_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cccccc;")
        layout.addWidget(llm_title)

        # Google API Key section
        google_section = self.create_api_key_section(
            "Google API Key",
            "google",
            "Enter your Google API key here..."
        )
        layout.addWidget(google_section)

        # Anthropic API Key section
        anthropic_section = self.create_api_key_section(
            "Anthropic API Key",
            "anthropic",
            "Enter your Anthropic API key here..."
        )
        layout.addWidget(anthropic_section)

        # OpenAI API Key section
        openai_section = self.create_api_key_section(
            "OpenAI API Key",
            "openai",
            "Enter your OpenAI API key here..."
        )
        layout.addWidget(openai_section)

        # OpenRouter API Key section
        openrouter_section = self.create_api_key_section(
            "OpenRouter API Key",
            "openrouter",
            "Enter your OpenRouter API key here..."
        )
        layout.addWidget(openrouter_section)

        # Groq API Key section
        groq_section = self.create_api_key_section(
            "Groq API Key",
            "groq",
            "Enter your Groq API key here..."
        )
        layout.addWidget(groq_section)

        # Deepseek API Key section
        deepseek_section = self.create_api_key_section(
            "Deepseek API Key",
            "deepseek",
            "Enter your Deepseek API key here..."
        )
        layout.addWidget(deepseek_section)

        # Together AI API Key section
        together_section = self.create_api_key_section(
            "Together AI API Key",
            "together",
            "Enter your Together AI API key here..."
        )
        layout.addWidget(together_section)

        # xAI API Key section
        xai_section = self.create_api_key_section(
            "xAI API Key",
            "xai",
            "Enter your xAI API key here..."
        )
        layout.addWidget(xai_section)

        # Web Search API Keys Section Title
        search_title = QLabel("Web Search API Keys")
        search_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cccccc; margin-top: 20px;")
        layout.addWidget(search_title)

        # Google Serper API Key section
        serper_section = self.create_api_key_section(
            "Google Serper API Key",
            "google_serper",
            "Enter your Serper API key here..."
        )
        layout.addWidget(serper_section)

        # Brave Search API Key section
        brave_section = self.create_api_key_section(
            "Brave Search API Key",
            "brave_search",
            "Enter your Brave Search API key here..."
        )
        layout.addWidget(brave_section)

        # Exa Search API Key section
        exa_section = self.create_api_key_section(
            "Exa Search API Key",
            "exa_search",
            "Enter your Exa Search API key here..."
        )
        layout.addWidget(exa_section)

        # Jina Search API Key section
        jina_section = self.create_api_key_section(
            "Jina Search API Key",
            "jina_search",
            "Enter your Jina Search API key here..."
        )
        layout.addWidget(jina_section)

        # Tavily Search API Key section
        tavily_section = self.create_api_key_section(
            "Tavily Search API Key",
            "tavily_search",
            "Enter your Tavily Search API key here..."
        )
        layout.addWidget(tavily_section)

        # Custom OpenAI-compatible model section
        custom_openai_title = QLabel("Custom OpenAI-compatible Models")
        custom_openai_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cccccc; margin-top: 20px;")
        layout.addWidget(custom_openai_title)

        # Add custom OpenAI section
        self.custom_openai_container = QWidget()
        self.custom_openai_layout = QVBoxLayout(self.custom_openai_container)
        self.custom_openai_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_openai_layout.setSpacing(20)
        
        # Load existing custom OpenAI models
        self.load_existing_custom_openai_models()
        
        # Add button for adding more custom OpenAI models
        add_custom_button = QPushButton("+ Add Custom OpenAI-compatible Model")
        add_custom_button.setStyleSheet("""
            QPushButton {
                background-color: #2b5c99;
                border: none;
                border-radius: 4px;
                padding: 10px;
                color: white;
                font-size: 13px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
        """)
        add_custom_button.clicked.connect(self.add_another_custom_openai)
        
        layout.addWidget(self.custom_openai_container)
        layout.addWidget(add_custom_button)
        layout.addStretch()

        # Set content widget to scroll area
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def load_existing_custom_openai_models(self):
        """Load existing custom OpenAI models from settings."""
        # Always add the first model section
        self.add_custom_openai_section(0)
        
        # Check for additional custom OpenAI models
        index = 1
        while True:
            settings_key = f"custom_openai_{index}"
            # Check if this model exists in settings
            if self.settings.get('models', settings_key):
                self.add_custom_openai_section(index)
                index += 1
            else:
                break

    def create_api_key_section(self, title: str, provider: str, placeholder: str) -> QWidget:
        """Create a section for an API key input."""
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(10)

        # Label
        label = QLabel(title)
        label.setStyleSheet("font-size: 14px;")

        # API Key input with show/hide toggle
        key_container = QWidget()
        key_layout = QHBoxLayout(key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)

        api_input = QLineEdit()
        api_input.setPlaceholderText(placeholder)
        api_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
        """)

        # Load existing API key if present
        if api_key := self.settings.get_api_key(provider):
            api_input.setText(api_key)

        # Toggle visibility button
        toggle_button = QPushButton("👁")
        toggle_button.setFixedSize(30, 30)
        toggle_button.setStyleSheet("""
            QPushButton {
                border-radius: 6px;
                font-size: 14px;
                background-color: #404040;
                border: none;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #333333;
                padding-top: 1px;
                padding-left: 1px;
            }
        """)
        toggle_button.clicked.connect(
            lambda: self.toggle_key_visibility(api_input, toggle_button))

        # Clear button
        clear_button = QPushButton("×")
        clear_button.setFixedSize(30, 30)
        clear_button.setStyleSheet("""
            QPushButton {
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
                background-color: #404040;
                border: none;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #ff4444;
                color: white;
            }
            QPushButton:pressed {
                background-color: #cc3333;
                padding-top: 1px;
                padding-left: 1px;
            }
        """)
        clear_button.clicked.connect(lambda: self.clear_api_key(provider, api_input, status_label))

        key_layout.addWidget(api_input)
        key_layout.addWidget(toggle_button)
        key_layout.addWidget(clear_button)

        section_layout.addWidget(label)
        section_layout.addWidget(key_container)

        # Status label
        status_label = QLabel()
        status_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                border-radius: 4px;
                font-size: 12px;
            }
            QLabel[status="success"] {
                background-color: #1e4620;
                color: #4caf50;
            }
            QLabel[status="error"] {
                background-color: #461e1e;
                color: #f44336;
            }
        """)
        status_label.hide()
        section_layout.addWidget(status_label)

        # Save button
        save_button = QPushButton(f"Save {title}")
        save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                max-width: 200px;
                background-color: #2b5c99;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
            QPushButton:pressed {
                background-color: #1f4573;
                padding: 9px 16px 7px 16px;
            }
        """)
        save_button.clicked.connect(lambda: self.save_api_key(
            provider, api_input, status_label))

        section_layout.addWidget(save_button)

        # Store references
        setattr(self, f"{provider}_input", api_input)
        setattr(self, f"{provider}_status", status_label)
        setattr(self, f"{provider}_toggle", toggle_button)

        return section

    def toggle_key_visibility(self, input_field: QLineEdit, toggle_button: QPushButton):
        """Toggle API key visibility."""
        if input_field.echoMode() == QLineEdit.EchoMode.Password:
            input_field.setEchoMode(QLineEdit.EchoMode.Normal)
            toggle_button.setText("🔒")
        else:
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
            toggle_button.setText("👁")

    def show_status(self, label: QLabel, message: str, is_error: bool = False):
        """Show a status message with appropriate styling."""
        label.setText(message)
        label.setProperty("status", "error" if is_error else "success")
        label.style().unpolish(label)
        label.style().polish(label)
        label.show()

    def save_api_key(self, provider: str, input_field: QLineEdit, status_label: QLabel):
        """Save the API key."""
        api_key = input_field.text().strip()

        if not api_key:
            self.show_status(status_label, "Please enter an API key", True)
            return

        if self.settings.set_api_key(provider, api_key):
            # Hide the key after saving
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
            getattr(self, f"{provider}_toggle").setText("👁")

            # Show success message
            self.show_status(status_label, "API key saved successfully!")

            # Show confirmation dialog
            QMessageBox.information(
                self,
                "Success",
                f"{provider.title()} API key has been saved successfully.",
                QMessageBox.StandardButton.Ok
            )
        else:
            # Show error message
            self.show_status(status_label, "Failed to save API key", True)
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save API key. Please try again.",
                QMessageBox.StandardButton.Ok
            )

    def add_custom_openai_section(self, index=0):
        """Create section for custom OpenAI-compatible model configuration."""
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(10)
        section_layout.setContentsMargins(0, 10, 0, 10)

        # Add a separator if not the first section
        if index > 0:
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            separator.setStyleSheet("background-color: #444444;")
            section_layout.addWidget(separator)

        # Title with index if not the first one
        title_layout = QHBoxLayout()
        title_text = "Custom OpenAI-Compatible Model" if index == 0 else f"Custom OpenAI-Compatible Model #{index+1}"
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(title)
        
        # Add remove button for sections after the first one
        if index > 0:
            remove_button = QPushButton("Remove")
            remove_button.setStyleSheet("""
                QPushButton {
                    padding: 4px 8px;
                    font-size: 12px;
                    border-radius: 4px;
                    background-color: #661a1a;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #8a2222;
                }
                QPushButton:pressed {
                    background-color: #551515;
                }
            """)
            remove_button.clicked.connect(lambda: self.remove_custom_openai_section(index))
            title_layout.addWidget(remove_button)
        
        title_layout.addStretch()
        section_layout.addLayout(title_layout)

        # Determine the settings key based on index
        settings_key = f"custom_openai_{index}" if index > 0 else "custom_openai"
        provider_key = settings_key

        # Base URL input
        base_url_layout = QHBoxLayout()
        base_url_label = QLabel("Base URL:")
        base_url_input = QLineEdit()
        base_url_input.setPlaceholderText(
            "Enter base URL (e.g., http://localhost:8000)")
        
        # Load existing value if available
        current_url = self.settings.get(
            'models', settings_key, 'base_url', default='')
        base_url_input.setText(current_url)
        
        base_url_layout.addWidget(base_url_label)
        base_url_layout.addWidget(base_url_input)
        section_layout.addLayout(base_url_layout)

        # Model ID input
        model_id_layout = QHBoxLayout()
        model_id_label = QLabel("Model ID:")
        model_id_input = QLineEdit()
        model_id_input.setPlaceholderText(
            "Enter model ID (e.g., gpt-3.5-turbo)")
        
        # Load existing value if available
        current_model_id = self.settings.get(
            'models', settings_key, 'model_id', default='')
        model_id_input.setText(current_model_id)
        
        model_id_layout.addWidget(model_id_label)
        model_id_layout.addWidget(model_id_input)
        section_layout.addLayout(model_id_layout)

        # API Key input with show/hide toggle
        api_key_layout = QVBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setStyleSheet("font-size: 14px;")
        api_key_layout.addWidget(api_key_label)

        key_container = QWidget()
        key_container_layout = QHBoxLayout(key_container)
        key_container_layout.setContentsMargins(0, 0, 0, 0)

        api_input = QLineEdit()
        api_input.setPlaceholderText("Enter API key for custom OpenAI-compatible model...")
        api_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
        """)

        # Load existing API key if available
        if api_key := self.settings.get_api_key(provider_key):
            api_input.setText(api_key)

        # Toggle visibility button
        toggle_button = QPushButton("👁")
        toggle_button.setFixedSize(30, 30)
        toggle_button.setStyleSheet("""
            QPushButton {
                border-radius: 6px;
                font-size: 14px;
                background-color: #404040;
                border: none;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #333333;
                padding-top: 1px;
                padding-left: 1px;
            }
        """)
        toggle_button.clicked.connect(
            lambda: self.toggle_key_visibility(api_input, toggle_button))

        # Clear button
        clear_button = QPushButton("×")
        clear_button.setFixedSize(30, 30)
        clear_button.setStyleSheet("""
            QPushButton {
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
                background-color: #404040;
                border: none;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #ff4444;
                color: white;
            }
            QPushButton:pressed {
                background-color: #cc3333;
                padding-top: 1px;
                padding-left: 1px;
            }
        """)
        
        # Status label
        status_label = QLabel()
        status_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                border-radius: 4px;
                font-size: 12px;
            }
            QLabel[status="success"] {
                background-color: #1e4620;
                color: #4caf50;
            }
            QLabel[status="error"] {
                background-color: #461e1e;
                color: #f44336;
            }
        """)
        status_label.hide()
        
        clear_button.clicked.connect(
            lambda: self.clear_api_key(provider_key, api_input, status_label))

        key_container_layout.addWidget(api_input)
        key_container_layout.addWidget(toggle_button)
        key_container_layout.addWidget(clear_button)

        api_key_layout.addWidget(key_container)
        api_key_layout.addWidget(status_label)
        section_layout.addLayout(api_key_layout)

        # Save button
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                max-width: 200px;
                background-color: #2b5c99;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
            QPushButton:pressed {
                background-color: #1f4573;
                padding: 9px 16px 7px 16px;
            }
        """)
        
        # Connect save button to save function
        save_button.clicked.connect(
            lambda: self.save_custom_openai_model(
                index, 
                base_url_input, 
                model_id_input, 
                api_input, 
                status_label
            )
        )
        
        button_layout.addWidget(save_button)
        
        # Add "Add Another" button if this is the last section
        add_another_button = QPushButton("Add Another")
        add_another_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                max-width: 200px;
                background-color: #404040;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #333333;
                padding: 9px 16px 7px 16px;
            }
        """)
        add_another_button.clicked.connect(self.add_another_custom_openai)
        button_layout.addWidget(add_another_button)
        
        # Add spacer to push buttons to the left
        button_layout.addStretch()
        section_layout.addLayout(button_layout)

        # Store references to inputs for this section
        section_data = {
            'widget': section,
            'base_url_input': base_url_input,
            'model_id_input': model_id_input,
            'api_input': api_input,
            'status_label': status_label,
            'toggle_button': toggle_button,
            'add_another_button': add_another_button,
            'index': index,
            'provider_key': provider_key
        }
        
        self.custom_openai_sections.append(section_data)
        self.custom_openai_layout.addWidget(section)
        
        return section

    def add_another_custom_openai(self):
        """Add another custom OpenAI model section."""
        # Check if the last section has all fields filled
        last_section = self.custom_openai_sections[-1]
        base_url = last_section['base_url_input'].text().strip()
        model_id = last_section['model_id_input'].text().strip()
        api_key = last_section['api_input'].text().strip()
        
        # If any field is empty, show error and focus on the first empty field
        if not base_url:
            self.show_status(last_section['status_label'], "Base URL is required", True)
            last_section['base_url_input'].setFocus()
            return
        elif not model_id:
            self.show_status(last_section['status_label'], "Model ID is required", True)
            last_section['model_id_input'].setFocus()
            return
        elif not api_key:
            self.show_status(last_section['status_label'], "API Key is required", True)
            last_section['api_input'].setFocus()
            return
        
        # Save the current section first to ensure it's properly stored
        index = last_section['index']
        success = self.save_custom_openai_model(
            index,
            last_section['base_url_input'],
            last_section['model_id_input'],
            last_section['api_input'],
            last_section['status_label']
        )
        
        # Only add a new section if the save was successful
        if success:
            # Add a new section with incremented index
            new_index = len(self.custom_openai_sections)
            self.add_custom_openai_section(new_index)

    def save_custom_openai_model(self, index, base_url_input, model_id_input, api_input, status_label):
        """Save custom OpenAI model settings."""
        base_url = base_url_input.text().strip()
        model_id = model_id_input.text().strip()
        api_key = api_input.text().strip()
        
        # Validate inputs
        if not base_url or not model_id or not api_key:
            self.show_status(status_label, "All fields are required", True)
            return False
        
        # Validate base URL format
        if not base_url.startswith(('http://', 'https://')):
            self.show_status(status_label, "Base URL must start with http:// or https://", True)
            return False
            
        # Remove trailing slashes from base URL
        base_url = base_url.rstrip('/')
        base_url_input.setText(base_url)
        
        try:
            # Determine the provider key based on index
            provider_key = f"custom_openai_{index}" if index > 0 else "custom_openai"
            
            # Save API key
            if not self.settings.set_api_key(provider_key, api_key):
                self.show_status(status_label, "Failed to save API key", True)
                return False
            
            # Hide the key after saving
            api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.custom_openai_sections[index]['toggle_button'].setText("👁")
            
            # Save model settings
            settings_key = f"custom_openai_{index}" if index > 0 else "custom_openai"
            
            # Ensure the models.custom_openai dictionary exists
            if not self.settings.get('models', settings_key):
                self.settings.set({}, 'models', settings_key)
            
            # Save the base URL and model ID
            self.settings.set(base_url, 'models', settings_key, 'base_url')
            self.settings.set(model_id, 'models', settings_key, 'model_id')
            
            # Add to selected models
            display_name = f"Custom {index+1}: {model_id}" if index > 0 else f"Custom: {model_id}"
            
            # Log the model being added
            logging.info(f"Adding custom OpenAI model: {model_id} with provider: {settings_key}")
            
            self.settings.add_selected_model(
                model_id,
                settings_key,
                display_name
            )
            
            # Show success message
            self.show_status(status_label, "Model settings saved successfully!")
            
            # Show confirmation dialog
            QMessageBox.information(
                self,
                "Success",
                f"Custom OpenAI model settings have been saved successfully.",
                QMessageBox.StandardButton.Ok
            )
            
            return True  # Return success status
            
        except Exception as e:
            self.show_status(status_label, f"Error saving settings: {str(e)}", True)
            logging.error(f"Error saving custom OpenAI model: {str(e)}", exc_info=True)
            return False

    def create_custom_openai_section(self):
        """Legacy method for backward compatibility."""
        # This is now handled by add_custom_openai_section
        return QWidget()  # Return empty widget

    def save_custom_openai_settings(self):
        """Legacy method for backward compatibility."""
        # This is now handled by save_custom_openai_model
        pass

    def clear_api_key(self, provider: str, input_field: QLineEdit, status_label: QLabel):
        """Clear the API key for the given provider."""
        try:
            # Clear the input field
            input_field.clear()
            
            # Remove from settings
            if self.settings.set_api_key(provider, ""):
                self.show_status(status_label, "API key cleared successfully!")
                
                # Emit signal that the API key was cleared
                self.api_key_cleared.emit(provider)
                
                # Show confirmation dialog
                provider_display = provider
                if provider.startswith('custom_openai_'):
                    index = provider.split('_')[-1]
                    provider_display = f"Custom OpenAI Model #{int(index)+1}"
                elif provider == 'custom_openai':
                    provider_display = "Custom OpenAI Model"
                else:
                    provider_display = provider.title()
                    
                QMessageBox.information(
                    self,
                    "Success",
                    f"{provider_display} API key has been cleared.",
                    QMessageBox.StandardButton.Ok
                )
            else:
                self.show_status(status_label, "Failed to clear API key", True)
        except Exception as e:
            self.show_status(status_label, f"Error clearing API key: {str(e)}", True)

    def remove_custom_openai_section(self, index):
        """Remove a custom OpenAI model section."""
        # Confirm with the user
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove this custom OpenAI model?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        # Find the section to remove
        section_to_remove = None
        for i, section in enumerate(self.custom_openai_sections):
            if section['index'] == index:
                section_to_remove = section
                section_index = i
                break
                
        if not section_to_remove:
            return
            
        # Remove from UI
        section_to_remove['widget'].setParent(None)
        section_to_remove['widget'].deleteLater()
        
        # Remove from settings
        provider_key = section_to_remove['provider_key']
        settings_key = f"custom_openai_{index}" if index > 0 else "custom_openai"
        
        # Clear API key
        self.settings.set_api_key(provider_key, "")
        
        # Remove model settings by setting it to an empty dictionary
        # The Settings class doesn't have a remove method, so we use set instead
        self.settings.set({}, 'models', settings_key)
        
        # Remove from selected models
        model_id = section_to_remove['model_id_input'].text().strip()
        if model_id:
            self.settings.remove_selected_model(model_id)
        
        # Remove from our list
        self.custom_openai_sections.pop(section_index)
        
        # Show confirmation
        QMessageBox.information(
            self,
            "Success",
            "Custom OpenAI model has been removed.",
            QMessageBox.StandardButton.Ok
        )
