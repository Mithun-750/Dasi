"""
LLM Providers section for the API Keys tab.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import pyqtSignal
from .common import APICategory, APIKeySection, create_section


class LLMProvidersSection(APIKeySection):
    """Section for managing LLM provider API keys."""
    
    # Signal emitted when a custom OpenAI model is needed
    custom_openai_requested = pyqtSignal()
    
    def __init__(self, settings, custom_openai=None, parent=None):
        super().__init__(settings, parent)
        self.setObjectName("llm_providers_section")
        self.custom_openai = custom_openai
        self.init_ui()
        
    def init_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create the LLM providers section
        self.llm_section = create_section(APICategory.LLM_PROVIDERS)
        layout.addWidget(self.llm_section)
        
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
            self.llm_section.layout().addWidget(api_section)
        
        # Add custom OpenAI section reference if provided
        if self.custom_openai:
            # Create a container for the title and add button
            custom_title_container = QWidget()
            custom_title_container.setStyleSheet("background-color: transparent;")
            custom_title_layout = QHBoxLayout(custom_title_container)
            custom_title_layout.setContentsMargins(0, 20, 0, 0)  # Add top margin for spacing
            custom_title_layout.setSpacing(10)  # Add spacing between title and button
            
            # Add section title
            self.custom_openai_title = QLabel("Custom OpenAI-compatible Models")
            self.custom_openai_title.setStyleSheet("""
                font-size: 15px;
                font-weight: bold;
                color: #e0e0e0;
            """)
            custom_title_layout.addWidget(self.custom_openai_title)
            
            self.llm_section.layout().addWidget(custom_title_container)
            
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
            self.llm_section.layout().addWidget(custom_separator)
            
            # Add the custom OpenAI section
            self.llm_section.layout().addWidget(self.custom_openai)
        
    def get_api_sections(self):
        """Get the API sections dictionary."""
        return self.api_sections
    
    def set_visibility(self, visible):
        """Set the visibility of this section."""
        self.setVisible(visible) 