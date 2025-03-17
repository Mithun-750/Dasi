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
    QStyledItemDelegate,
    QAbstractButton,
    QProxyStyle,
    QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFontMetrics, QIcon
from .settings_manager import Settings
import logging
import os


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
        # Create main layout with proper spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 0, 16)  # Right padding is 0
        
        # Set transparent background for this widget
        self.setStyleSheet("background-color: transparent;")

        # Create scroll area with modern styling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a;
                width: 10px;
                margin: 0px 0px 0px 8px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #333333;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #444444;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #1a1a1a;
                height: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background-color: #333333;
                min-width: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #444444;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        # Create content widget for scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(16)
        self.content_layout.setContentsMargins(0, 0, 8, 0)  # Added 8px right padding for gap between content and scrollbar

        # Create filter section with modern card design
        filter_section = self.create_filter_section()
        self.content_layout.addWidget(filter_section)

        # Initialize API key sections
        self.initialize_api_sections()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def create_filter_section(self):
        """Create the search and filter section."""
        filter_widget = QFrame()
        filter_widget.setProperty("class", "card")
        filter_widget.setStyleSheet("""
            QFrame.card {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
        """)
        filter_layout = QVBoxLayout(filter_widget)
        filter_layout.setSpacing(12)
        filter_layout.setContentsMargins(16, 16, 16, 16)

        # Section title
        title_label = QLabel("Filter API Keys")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #e0e0e0;
            margin-bottom: 8px;
        """)
        filter_layout.addWidget(title_label)

        # Create form layout for consistent alignment
        form_widget = QWidget()
        form_widget.setStyleSheet("background-color: transparent;")
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)
        
        # Search bar with icon styling
        search_container = QWidget()
        search_container.setStyleSheet("background-color: transparent;")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(12)
        
        search_label = QLabel("Search:")
        search_label.setFixedWidth(90)
        search_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        search_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search API keys...")
        self.search_input.setProperty("class", "search-input")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
                background-color: #2d2d2d;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        self.search_input.textChanged.connect(self.apply_filters)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        form_layout.addWidget(search_container)

        # Category filter with modern styling
        category_container = QWidget()
        category_container.setStyleSheet("background-color: transparent;")
        category_layout = QHBoxLayout(category_container)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(12)
        
        category_label = QLabel("Category:")
        category_label.setFixedWidth(90)
        category_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        category_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        
        self.category_combo = QComboBox()
        self.category_combo.setProperty("class", "category-combo")
        self.category_combo.addItem("All Categories")
        self.category_combo.addItem(APICategory.LLM_PROVIDERS)
        self.category_combo.addItem(APICategory.SEARCH_PROVIDERS)
        self.category_combo.setStyleSheet("""
            QComboBox {
                padding: 10px 12px;
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                min-height: 20px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #4a4a4a;
                background-color: #2d2d2d;
            }
            QComboBox:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border-left: 1px solid #3b3b3b;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                selection-background-color: #3b82f6;
                selection-color: white;
                padding: 4px;
            }
        """)
        
        # Apply custom style for the arrow
        self.category_combo.setStyle(ComboBoxStyle())
        
        # Connect signal
        self.category_combo.currentTextChanged.connect(self.apply_filters)
        
        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_combo)
        form_layout.addWidget(category_container)

        # Status filter with modern checkbox styling
        status_container = QWidget()
        status_container.setStyleSheet("background-color: transparent;")
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(12)
        
        status_label = QLabel("Status:")
        status_label.setFixedWidth(90)
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        
        checkbox_container = QWidget()
        checkbox_container.setStyleSheet("background-color: transparent;")
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(16)
        
        self.show_empty = QCheckBox("Show Empty")
        self.show_empty.setChecked(True)
        self.show_empty.stateChanged.connect(self.apply_filters)
        
        self.show_filled = QCheckBox("Show Filled")
        self.show_filled.setChecked(True)
        self.show_filled.stateChanged.connect(self.apply_filters)
        
        checkbox_layout.addWidget(self.show_empty)
        checkbox_layout.addWidget(self.show_filled)
        checkbox_layout.addStretch()
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(checkbox_container)
        
        form_layout.addWidget(status_container)
        filter_layout.addWidget(form_widget)

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
        custom_title_container.setStyleSheet("background-color: transparent;")
        custom_title_layout = QHBoxLayout(custom_title_container)
        custom_title_layout.setContentsMargins(0, 20, 0, 0)  # Add top margin for spacing
        custom_title_layout.setSpacing(10)  # Add spacing between title and button
        
        # Add title with modern styling
        self.custom_openai_title = QLabel("Custom OpenAI-compatible Models")
        self.custom_openai_title.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #e0e0e0;
        """)
        custom_title_layout.addWidget(self.custom_openai_title)
        
        # Add button for adding custom OpenAI models with modern styling
        add_model_button = QPushButton("Add Model")
        add_model_button.setProperty("class", "danger")
        add_model_button.setFixedWidth(100)  # Increased width to prevent text from being cut off
        add_model_button.setStyleSheet("""
            QPushButton {
                padding: 5px 8px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                background-color: #dc2626;
                border: 1px solid #ef4444;
                color: white;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border: 1px solid #f87171;
            }
            QPushButton:pressed {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        add_model_button.clicked.connect(self.add_another_custom_openai)
        custom_title_layout.addWidget(add_model_button)
        
        llm_section.layout().addWidget(custom_title_container)
        
        # Add separator line below custom title
        custom_separator = QFrame()
        custom_separator.setFrameShape(QFrame.Shape.HLine)
        custom_separator.setFrameShadow(QFrame.Shadow.Sunken)
        custom_separator.setStyleSheet("""
            background-color: #404040;
            margin-top: 5px;
            margin-bottom: 10px;
            border: none;
            height: 1px;
        """)
        llm_section.layout().addWidget(custom_separator)
        
        # Create container for custom OpenAI models
        self.custom_openai_container = QWidget()
        self.custom_openai_container.setStyleSheet("background-color: transparent;")
        self.custom_openai_layout = QVBoxLayout(self.custom_openai_container)
        self.custom_openai_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_openai_layout.setSpacing(16)
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
        section.setProperty("class", "card")
        section.setStyleSheet("""
            QFrame.card {
                background-color: #1e1e1e;
                border-radius: 8px;
                padding: 16px;
                margin: 4px 0px;
                border: 1px solid #333333;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setSpacing(16)
        
        # Create title container with horizontal layout
        title_container = QWidget()
        title_container.setStyleSheet("background-color: transparent;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add title with modern styling
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #e0e0e0;
        """)
        title_layout.addWidget(title_label)
        
        # Add stretch to push any additional widgets to the right
        title_layout.addStretch()
        
        layout.addWidget(title_container)
        
        # Add separator line below title
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("""
            background-color: #3b3b3b;
            margin-top: 5px;
            margin-bottom: 10px;
            border: none;
            height: 1px;
        """)
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
        section = QFrame()
        section.setProperty("class", "api-card")
        section.setStyleSheet("""
            QFrame.api-card {
                background-color: #292929;
                border-radius: 8px;
                padding: 0px;
                margin: 8px 0px;
                border: 1px solid #333333;
            }
        """)
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(12)
        section_layout.setContentsMargins(16, 16, 16, 16)

        # Title with icon
        title_container = QWidget()
        title_container.setStyleSheet("background-color: transparent;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #e0e0e0;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        section_layout.addWidget(title_container)

        # Add separator under title
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("""
            background-color: #3b3b3b;
            margin-top: 5px;
            margin-bottom: 10px;
            border: none;
            height: 1px;
        """)
        section_layout.addWidget(separator)

        # API Key input with modern styling
        key_container = QWidget()
        key_container.setStyleSheet("background-color: transparent;")
        key_layout = QHBoxLayout(key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(8)

        api_input = QLineEdit()
        api_input.setPlaceholderText(placeholder)
        api_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_input.setProperty("class", "api-input")
        api_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                background-color: #333333;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #383838;
                padding: 9px 11px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)

        # Load existing API key if present
        if api_key := self.settings.get_api_key(provider):
            api_input.setText(api_key)

        # Toggle visibility button with modern styling using SVG icon
        toggle_button = QPushButton()
        toggle_button.setFixedSize(38, 38)
        toggle_button.setProperty("class", "icon-button")
        toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 0px;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        
        # Set the SVG icon
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        eye_icon_path = os.path.join(icons_dir, "eye.svg")
        toggle_button.setIcon(QIcon(eye_icon_path))
        toggle_button.setIconSize(QSize(20, 20))
        
        toggle_button.clicked.connect(
            lambda: self.toggle_key_visibility(api_input, toggle_button)
        )

        key_layout.addWidget(api_input)
        key_layout.addWidget(toggle_button)

        section_layout.addWidget(key_container)

        # Status label with modern styling
        status_label = QLabel()
        status_label.setStyleSheet("""
            QLabel {
                padding: 10px 12px;
                border-radius: 6px;
                font-size: 13px;
                margin-top: 8px;
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

        # Button container with modern styling
        button_container = QWidget()
        button_container.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(10)

        # Save button with modern styling matching the danger button in settings_window.py
        save_button = QPushButton("Save")
        save_button.setProperty("class", "danger")
        save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                background-color: #dc2626;
                border: 1px solid #ef4444;
                color: white;
            }
            QPushButton:pressed {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        save_button.clicked.connect(lambda: self.save_api_key(
            provider, api_input, status_label))
        
        # Reset button with modern styling
        reset_button = QPushButton("Reset")
        reset_button.setProperty("class", "secondary")
        reset_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                background-color: #404040;
                border: 1px solid #505050;
                color: white;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        reset_button.clicked.connect(lambda: self.clear_api_key(provider, api_input, status_label))

        # Make buttons take full width
        button_layout.addWidget(save_button, 1)  # 1 is the stretch factor
        button_layout.addWidget(reset_button, 1)  # 1 is the stretch factor

        section_layout.addWidget(button_container)

        # Store references
        setattr(self, f"{provider}_input", api_input)
        setattr(self, f"{provider}_status", status_label)
        setattr(self, f"{provider}_toggle", toggle_button)

        return section

    def toggle_key_visibility(self, input_field: QLineEdit, toggle_button: QPushButton):
        """Toggle API key visibility."""
        # Get the paths to the eye icons
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        eye_icon_path = os.path.join(icons_dir, "eye.svg")
        eye_off_icon_path = os.path.join(icons_dir, "eye_off.svg")
        
        if input_field.echoMode() == QLineEdit.EchoMode.Password:
            input_field.setEchoMode(QLineEdit.EchoMode.Normal)
            toggle_button.setIcon(QIcon(eye_off_icon_path))
        else:
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
            toggle_button.setIcon(QIcon(eye_icon_path))

    def show_status(self, label: QLabel, message: str, is_error: bool = False):
        """Show a status message with appropriate styling."""
        label.setText(message)
        label.setProperty("status", "error" if is_error else "success")
        label.style().unpolish(label)
        label.style().polish(label)
        label.show()

    def save_api_key(self, provider: str, input_field: QLineEdit, status_label: QLabel):
        """Save the API key."""
        # Get the path to the eye icon
        eye_icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    "assets", "icons", "eye.svg")
        
        api_key = input_field.text().strip()

        if not api_key:
            self.show_status(status_label, "Please enter an API key", True)
            return

        if self.settings.set_api_key(provider, api_key):
            # Hide the key after saving
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
            getattr(self, f"{provider}_toggle").setIcon(QIcon(eye_icon_path))

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
        section = QFrame()
        section.setProperty("class", "api-card")
        section.setStyleSheet("""
            QFrame.api-card {
                background-color: #292929;
                border-radius: 8px;
                padding: 0px;
                margin: 8px 0px;
                border: 1px solid #333333;
            }
        """)
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(12)
        section_layout.setContentsMargins(16, 16, 16, 16)

        # Title container with modern styling
        title_container = QWidget()
        title_container.setStyleSheet("background-color: transparent;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        # Title with index if not the first one
        title_text = "Custom OpenAI-Compatible Model" if index == 0 else f"Custom OpenAI-Compatible Model #{index+1}"
        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #e0e0e0;
        """)
        title_layout.addWidget(title)
        
        # Add remove button for sections after the first one
        if index > 0:
            remove_button = QPushButton("Remove")
            remove_button.setProperty("class", "danger")
            remove_button.setStyleSheet("""
                QPushButton {
                    padding: 6px 12px;
                    font-size: 12px;
                    border-radius: 6px;
                    background-color: #dc2626;
                    border: 1px solid #ef4444;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #b91c1c;
                }
            """)
            remove_button.clicked.connect(lambda: self.remove_custom_openai_section(index))
            title_layout.addWidget(remove_button)
        
        title_layout.addStretch()
        section_layout.addWidget(title_container)

        # Add separator under title
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("""
            background-color: #3b3b3b;
            margin-top: 5px;
            margin-bottom: 10px;
            border: none;
            height: 1px;
        """)
        section_layout.addWidget(separator)

        # Determine the settings key based on index
        settings_key = f"custom_openai_{index}" if index > 0 else "custom_openai"
        provider_key = settings_key

        # Base URL input with modern styling
        base_url_container = QWidget()
        base_url_container.setStyleSheet("background-color: transparent;")
        base_url_layout = QVBoxLayout(base_url_container)
        base_url_layout.setContentsMargins(0, 0, 0, 0)
        base_url_layout.setSpacing(6)

        base_url_label = QLabel("Base URL:")
        base_url_label.setStyleSheet("font-size: 13px; color: #e0e0e0; font-weight: bold;")
        base_url_input = QLineEdit()
        base_url_input.setPlaceholderText("Enter base URL (e.g., http://localhost:8000)")
        base_url_input.setProperty("class", "api-input")
        base_url_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                background-color: #333333;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #383838;
                padding: 9px 11px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        
        # Load existing value if available
        current_url = self.settings.get('models', settings_key, 'base_url', default='')
        base_url_input.setText(current_url)
        
        base_url_layout.addWidget(base_url_label)
        base_url_layout.addWidget(base_url_input)
        section_layout.addWidget(base_url_container)

        # Model ID input with modern styling
        model_id_container = QWidget()
        model_id_container.setStyleSheet("background-color: transparent;")
        model_id_layout = QVBoxLayout(model_id_container)
        model_id_layout.setContentsMargins(0, 0, 0, 0)
        model_id_layout.setSpacing(6)

        model_id_label = QLabel("Model ID:")
        model_id_label.setStyleSheet("font-size: 13px; color: #e0e0e0; font-weight: bold;")
        model_id_input = QLineEdit()
        model_id_input.setPlaceholderText("Enter model ID (e.g., gpt-3.5-turbo)")
        model_id_input.setProperty("class", "api-input")
        model_id_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                background-color: #333333;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #383838;
                padding: 9px 11px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        
        # Load existing value if available
        current_model_id = self.settings.get('models', settings_key, 'model_id', default='')
        model_id_input.setText(current_model_id)
        
        model_id_layout.addWidget(model_id_label)
        model_id_layout.addWidget(model_id_input)
        section_layout.addWidget(model_id_container)

        # API Key input with modern styling
        api_key_container = QWidget()
        api_key_container.setStyleSheet("background-color: transparent;")
        api_key_layout = QVBoxLayout(api_key_container)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(6)

        api_key_label = QLabel("API Key:")
        api_key_label.setStyleSheet("font-size: 13px; color: #e0e0e0; font-weight: bold;")
        api_key_layout.addWidget(api_key_label)

        key_input_container = QWidget()
        key_input_container.setStyleSheet("background-color: transparent;")
        key_input_layout = QHBoxLayout(key_input_container)
        key_input_layout.setContentsMargins(0, 0, 0, 0)
        key_input_layout.setSpacing(8)

        api_input = QLineEdit()
        api_input.setPlaceholderText("Enter API key for custom OpenAI-compatible model...")
        api_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_input.setProperty("class", "api-input")
        api_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                background-color: #333333;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #383838;
                padding: 9px 11px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)

        # Load existing API key if available
        if api_key := self.settings.get_api_key(provider_key):
            api_input.setText(api_key)

        # Toggle visibility button with modern styling using SVG icon
        toggle_button = QPushButton()
        toggle_button.setFixedSize(38, 38)
        toggle_button.setProperty("class", "icon-button")
        toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 0px;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        
        # Set the SVG icon
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        eye_icon_path = os.path.join(icons_dir, "eye.svg")
        toggle_button.setIcon(QIcon(eye_icon_path))
        toggle_button.setIconSize(QSize(20, 20))
        
        toggle_button.clicked.connect(
            lambda: self.toggle_key_visibility(api_input, toggle_button)
        )

        key_input_layout.addWidget(api_input)
        key_input_layout.addWidget(toggle_button)

        api_key_layout.addWidget(key_input_container)
        
        # Status label with modern styling
        status_label = QLabel()
        status_label.setStyleSheet("""
            QLabel {
                padding: 10px 12px;
                border-radius: 6px;
                font-size: 13px;
                margin-top: 8px;
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
        api_key_layout.addWidget(status_label)
        
        section_layout.addWidget(api_key_container)

        # Button container with modern styling
        button_container = QWidget()
        button_container.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(10)

        # Save button with modern styling matching the danger button in settings_window.py
        save_button = QPushButton("Save")
        save_button.setProperty("class", "danger")
        save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                background-color: #dc2626;
                border: 1px solid #ef4444;
                color: white;
            }
            QPushButton:pressed {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
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
        
        # Reset button with modern styling
        reset_button = QPushButton("Reset")
        reset_button.setProperty("class", "secondary")
        reset_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                background-color: #404040;
                border: 1px solid #505050;
                color: white;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        reset_button.clicked.connect(lambda: self.clear_api_key(provider_key, api_input, status_label))
        
        # Add "Add Another" button with modern styling
        add_another_button = QPushButton("Add Another")
        add_another_button.setProperty("class", "secondary")
        add_another_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                background-color: #404040;
                border: 1px solid #505050;
                color: white;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        add_another_button.clicked.connect(self.add_another_custom_openai)
        
        # Make buttons take full width
        button_layout.addWidget(save_button, 1)  # 1 is the stretch factor
        button_layout.addWidget(reset_button, 1)  # 1 is the stretch factor
        
        # Add the "Add Another" button if this is the first section
        if index == 0:
            button_layout.addWidget(add_another_button)
        
        section_layout.addWidget(button_container)

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
        display_name = f"Custom OpenAI Model {index+1}" if index > 0 else f"Custom: {model_id_input.text().strip()}"
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
        """Save custom OpenAI model configuration."""
        # Get the path to the eye icon
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        eye_icon_path = os.path.join(icons_dir, "eye.svg")
        
        base_url = base_url_input.text().strip()
        model_id = model_id_input.text().strip()
        api_key = api_input.text().strip()
        
        # Validate inputs
        if not base_url:
            self.show_status(status_label, "Please enter a base URL", True)
            return
            
        if not model_id:
            self.show_status(status_label, "Please enter a model ID", True)
            return
            
        if not api_key:
            self.show_status(status_label, "Please enter an API key", True)
            return
            
        try:
            # Determine the settings key based on index
            settings_key = f"custom_openai_{index}" if index > 0 else "custom_openai"
            provider_key = settings_key
            
            # Save API key
            self.settings.set_api_key(provider_key, api_key)
            
            # Save model settings
            self.settings.set(base_url, 'models', settings_key, 'base_url')
            self.settings.set(model_id, 'models', settings_key, 'model_id')
            
            # Add to selected models
            display_name = f"Custom {index+1}: {model_id}" if index > 0 else f"Custom: {model_id}"
            
            # Hide the key after saving
            api_input.setEchoMode(QLineEdit.EchoMode.Password)
            
            # Update the toggle button icon
            for section in self.custom_openai_sections:
                if section['index'] == index:
                    section['toggle_button'].setIcon(QIcon(eye_icon_path))
                    break
            
            # Save model settings
            self.settings.save()
            
            # Update the api_sections entry if it exists
            if provider_key in self.api_sections:
                # Update the widget title if needed
                widget = self.api_sections[provider_key]['widget']
                label = widget.findChild(QLabel)
                if label and "Custom OpenAI" in label.text():
                    label.setText(f"Custom OpenAI-Compatible Model {index+1}" if index > 0 else "Custom OpenAI-Compatible Model")
            
            # Show success message
            self.show_status(status_label, "Model configuration saved successfully!")
            
            # Show confirmation dialog
            QMessageBox.information(
                self,
                "Success",
                f"Custom OpenAI model configuration has been saved successfully.",
                QMessageBox.StandardButton.Ok
            )
            
            return True
            
        except Exception as e:
            # Show error message
            self.show_status(status_label, f"Failed to save model configuration: {str(e)}", True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save model configuration: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
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

# Custom style to draw a text arrow for combo boxes
class ComboBoxStyle(QProxyStyle):
    def __init__(self, style=None):
        super().__init__(style)
        
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown and isinstance(widget, QComboBox):
            # Draw a custom arrow
            rect = option.rect
            painter.save()
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "▼")
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)
