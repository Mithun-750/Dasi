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
    QComboBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from .settings_manager import Settings
import logging


class APICategory:
    LLM_PROVIDERS = "LLM Providers"
    SEARCH_PROVIDERS = "Search Providers"


class APIKeysTab(QWidget):
    # Signal emitted when an API key is cleared
    api_key_cleared = pyqtSignal(str)
    
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.custom_openai_sections = []  # Track custom OpenAI sections
        self.api_sections = {}  # Store references to API sections
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

        # Search and Filter Section
        filter_section = self.create_filter_section()
        main_layout.addWidget(filter_section)

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
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(20)
        self.content_layout.setContentsMargins(0, 0, 20, 0)

        # Initialize API key sections
        self.initialize_api_sections()

        scroll.setWidget(self.content)
        main_layout.addWidget(scroll)

    def create_filter_section(self):
        """Create the search and filter section."""
        filter_widget = QFrame()
        filter_widget.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        filter_layout = QVBoxLayout(filter_widget)

        # Search bar
        search_container = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search API keys...")
        self.search_input.textChanged.connect(self.apply_filters)
        search_container.addWidget(search_label)
        search_container.addWidget(self.search_input)

        # Category filter
        category_container = QHBoxLayout()
        category_label = QLabel("Category:")
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories")
        self.category_combo.addItem(APICategory.LLM_PROVIDERS)
        self.category_combo.addItem(APICategory.SEARCH_PROVIDERS)
        self.category_combo.currentTextChanged.connect(self.apply_filters)
        category_container.addWidget(category_label)
        category_container.addWidget(self.category_combo)

        # Status filter
        status_container = QHBoxLayout()
        self.show_empty = QCheckBox("Show Empty")
        self.show_empty.setChecked(True)
        self.show_empty.stateChanged.connect(self.apply_filters)
        self.show_filled = QCheckBox("Show Filled")
        self.show_filled.setChecked(True)
        self.show_filled.stateChanged.connect(self.apply_filters)
        status_container.addWidget(self.show_empty)
        status_container.addWidget(self.show_filled)
        status_container.addStretch()

        filter_layout.addLayout(search_container)
        filter_layout.addLayout(category_container)
        filter_layout.addLayout(status_container)

        return filter_widget

    def initialize_api_sections(self):
        """Initialize all API key sections."""
        # LLM Providers Section
        llm_section = self.create_section(APICategory.LLM_PROVIDERS)
        self.content_layout.addWidget(llm_section)

        # Add LLM provider API keys
        llm_providers = {
            "openai": "OpenAI API Key",
            "anthropic": "Anthropic API Key",
            "google": "Google API Key",
            "groq": "Groq API Key",
            "deepseek": "Deepseek API Key",
            "together": "Together AI API Key",
            "xai": "xAI API Key",
            "openrouter": "OpenRouter API Key"
        }

        for provider, title in llm_providers.items():
            api_section = self.create_api_key_section(
                title,
                provider,
                f"Enter your {title} here...",
                APICategory.LLM_PROVIDERS
            )
            self.api_sections[provider] = {
                'widget': api_section,
                'category': APICategory.LLM_PROVIDERS
            }
            llm_section.layout().addWidget(api_section)

        # Custom OpenAI-compatible model section
        # Create a container for the title and add button
        custom_title_container = QWidget()
        custom_title_layout = QHBoxLayout(custom_title_container)
        custom_title_layout.setContentsMargins(0, 20, 0, 0)  # Add top margin for spacing
        
        # Add title
        self.custom_openai_title = QLabel("Custom OpenAI-compatible Models")
        self.custom_openai_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cccccc;")
        custom_title_layout.addWidget(self.custom_openai_title)
        
        # Add button for adding custom OpenAI models
        self.add_custom_button = QPushButton("+ Add Model")
        self.add_custom_button.setStyleSheet("""
            QPushButton {
                background-color: #2b5c99;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                color: white;
                font-size: 12px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
        """)
        self.add_custom_button.clicked.connect(self.add_another_custom_openai)
        custom_title_layout.addWidget(self.add_custom_button)
        
        llm_section.layout().addWidget(custom_title_container)
        
        # Add separator line below custom title
        custom_separator = QFrame()
        custom_separator.setFrameShape(QFrame.Shape.HLine)
        custom_separator.setFrameShadow(QFrame.Shadow.Sunken)
        custom_separator.setStyleSheet("background-color: #444444; margin-top: 5px; margin-bottom: 10px;")
        llm_section.layout().addWidget(custom_separator)
        
        # Create container for custom OpenAI models
        self.custom_openai_container = QWidget()
        self.custom_openai_layout = QVBoxLayout(self.custom_openai_container)
        self.custom_openai_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_openai_layout.setSpacing(20)
        llm_section.layout().addWidget(self.custom_openai_container)
        
        # Load existing custom OpenAI models
        self.load_existing_custom_openai_models()

        # Search Providers Section
        search_section = self.create_section(APICategory.SEARCH_PROVIDERS)
        self.content_layout.addWidget(search_section)

        # Add search provider API keys
        search_providers = {
            "google_serper": "Google Serper API Key",
            "brave_search": "Brave Search API Key",
            "exa_search": "Exa Search API Key",
            "tavily_search": "Tavily Search API Key",
            "jina_search": "Jina Search API Key"
        }

        for provider, title in search_providers.items():
            api_section = self.create_api_key_section(
                title,
                provider,
                f"Enter your {title} here...",
                APICategory.SEARCH_PROVIDERS
            )
            self.api_sections[provider] = {
                'widget': api_section,
                'category': APICategory.SEARCH_PROVIDERS
            }
            search_section.layout().addWidget(api_section)

    def create_section(self, title):
        """Create a section with title."""
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setSpacing(15)
        
        # Create title container with horizontal layout
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #cccccc;")
        title_layout.addWidget(title_label)
        
        # Add stretch to push any additional widgets to the right
        title_layout.addStretch()
        
        layout.addWidget(title_container)
        
        # Add separator line below title
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #444444; margin-top: 5px; margin-bottom: 10px;")
        layout.addWidget(separator)
        
        return section

    def apply_filters(self):
        """Apply search and filter criteria to API key sections."""
        search_text = self.search_input.text().lower()
        selected_category = self.category_combo.currentText()
        show_empty = self.show_empty.isChecked()
        show_filled = self.show_filled.isChecked()

        # Track visible items per category
        visible_items = {
            APICategory.LLM_PROVIDERS: 0,
            APICategory.SEARCH_PROVIDERS: 0
        }

        # First, filter regular API sections
        for provider, section_info in self.api_sections.items():
            widget = section_info['widget']
            category = section_info['category']
            
            # Skip custom OpenAI models as they'll be handled separately
            if provider.startswith('custom_openai'):
                continue
                
            # Get the API key input field
            api_input = getattr(self, f"{provider}_input", None)
            if not api_input:
                continue

            has_key = bool(api_input.text().strip())
            title = widget.findChild(QLabel).text().lower()

            # Apply filters
            should_show = True

            # Category filter
            if selected_category != "All Categories" and category != selected_category:
                should_show = False

            # Search filter
            if search_text and search_text not in title.lower():
                should_show = False

            # Status filter
            if has_key and not show_filled:
                should_show = False
            if not has_key and not show_empty:
                should_show = False

            widget.setVisible(should_show)
            
            # Count visible items per category
            if should_show:
                visible_items[category] += 1

        # Handle custom OpenAI models
        any_custom_visible = False
        for section_data in self.custom_openai_sections:
            widget = section_data['widget']
            category = APICategory.LLM_PROVIDERS
            
            # Get data for filtering
            base_url = section_data['base_url_input'].text().strip()
            model_id = section_data['model_id_input'].text().strip()
            api_key = section_data['api_input'].text().strip()
            has_key = bool(api_key)
            
            # Create a searchable text combining model ID and base URL
            searchable_text = f"custom openai model {model_id} {base_url}".lower()
            
            # Apply filters
            should_show = True
            
            # Category filter
            if selected_category != "All Categories" and category != selected_category:
                should_show = False
                
            # Search filter
            if search_text and search_text not in searchable_text:
                should_show = False
                
            # Status filter
            if has_key and not show_filled:
                should_show = False
            if not has_key and not show_empty:
                should_show = False
                
            widget.setVisible(should_show)
            
            # Count visible items and track if any custom model is visible
            if should_show:
                visible_items[category] += 1
                any_custom_visible = True
                
        # Now find and hide/show category sections based on visible items
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                # Check if this is a category section
                title_label = widget.findChild(QLabel)
                if title_label and title_label.text() in [APICategory.LLM_PROVIDERS, APICategory.SEARCH_PROVIDERS]:
                    category = title_label.text()
                    # Show section only if it has visible items or if no category filter is applied
                    widget.setVisible(visible_items[category] > 0 or selected_category == "All Categories")
                    
        # Handle visibility of custom OpenAI elements
        show_custom_section = any_custom_visible and (
            selected_category == "All Categories" or 
            selected_category == APICategory.LLM_PROVIDERS
        )
        
        # Always show the add button if we're in LLM category or all categories
        show_custom_controls = (
            selected_category == "All Categories" or 
            selected_category == APICategory.LLM_PROVIDERS
        )
        
        # Find the custom title container and separator
        custom_title_container = None
        custom_separator = None
        
        # Look for the custom title container and separator in the LLM section
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                # Find the LLM section
                title_label = widget.findChild(QLabel)
                if title_label and title_label.text() == APICategory.LLM_PROVIDERS:
                    # Look through the LLM section's children
                    layout = widget.layout()
                    for j in range(layout.count()):
                        item = layout.itemAt(j)
                        if item.widget():
                            # Check if this is the custom title container
                            if item.widget().findChild(QLabel) and item.widget().findChild(QLabel).text() == "Custom OpenAI-compatible Models":
                                custom_title_container = item.widget()
                            # The separator is right after the title container
                            elif j > 0 and custom_title_container and isinstance(item.widget(), QFrame) and item.widget().frameShape() == QFrame.Shape.HLine:
                                custom_separator = item.widget()
                                break
        
        # Set visibility of custom OpenAI elements
        if custom_title_container:
            custom_title_container.setVisible(show_custom_controls)
        if custom_separator:
            custom_separator.setVisible(show_custom_controls)
            
        self.custom_openai_container.setVisible(show_custom_section)

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

    def create_api_key_section(self, title: str, provider: str, placeholder: str, category: str) -> QWidget:
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
            'provider_key': provider_key,
            'category': APICategory.LLM_PROVIDERS
        }
        
        self.custom_openai_sections.append(section_data)
        self.custom_openai_layout.addWidget(section)
        
        # Add to api_sections for filtering
        display_name = f"Custom OpenAI Model {index+1}" if index > 0 else "Custom OpenAI Model"
        self.api_sections[provider_key] = {
            'widget': section,
            'category': APICategory.LLM_PROVIDERS
        }
        
        return section

    def add_another_custom_openai(self):
        """Add another custom OpenAI model section."""
        # Check if there are any existing sections
        if not self.custom_openai_sections:
            # Add the first section if none exist
            self.add_custom_openai_section(0)
            return
            
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
            
            # Find the toggle button for this section
            for section in self.custom_openai_sections:
                if section['index'] == index:
                    section['toggle_button'].setText("👁")
                    break
            
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
            
            # Update the api_sections entry if it exists
            if provider_key in self.api_sections:
                # Update the widget title if needed
                widget = self.api_sections[provider_key]['widget']
                label = widget.findChild(QLabel)
                if label and "Custom OpenAI" in label.text():
                    label.setText(f"Custom OpenAI Model: {model_id}")
            
            # Show success message
            self.show_status(status_label, "Model settings saved successfully!")
            
            # Show confirmation dialog
            QMessageBox.information(
                self,
                "Success",
                f"Custom OpenAI model settings have been saved successfully.",
                QMessageBox.StandardButton.Ok
            )
            
            # Apply filters to update visibility
            self.apply_filters()
            
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
        
        # Remove from our lists
        self.custom_openai_sections.pop(section_index)
        
        # Remove from api_sections
        if provider_key in self.api_sections:
            del self.api_sections[provider_key]
        
        # Show confirmation
        QMessageBox.information(
            self,
            "Success",
            "Custom OpenAI model has been removed.",
            QMessageBox.StandardButton.Ok
        )
