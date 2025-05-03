"""
Search Providers section for the API Keys tab.
"""

from PyQt6.QtWidgets import QVBoxLayout
from .common import APICategory, APIKeySection, create_section


class SearchProvidersSection(APIKeySection):
    """Section for managing search provider API keys."""

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.setObjectName("search_providers_section")
        self.init_ui()

    def init_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the search providers section
        self.search_section = create_section(APICategory.SEARCH_PROVIDERS)
        layout.addWidget(self.search_section)

        # Add search provider API keys
        search_providers = {
            "google_serper": "Google Serper API Key",
            "brave_search": "Brave Search API Key",
            "exa_search": "Exa Search API Key",
            "tavily_search": "Tavily Search API Key",
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
            self.search_section.layout().addWidget(api_section)

    def get_api_sections(self):
        """Get the API sections dictionary."""
        return self.api_sections

    def set_visibility(self, visible):
        """Set the visibility of this section."""
        self.setVisible(visible)
