import os
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QCheckBox,
    QSpinBox,
    QGridLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from .settings_manager import Settings
import logging


class WebSearchTab(QWidget):
    """Tab for configuring web search settings."""
    
    # Signal emitted when search settings change
    search_settings_changed = pyqtSignal()
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.original_values = {}
        self.has_unsaved_changes = False
        self.init_ui()
        self.save_original_values()
        
    def save_original_values(self):
        """Save the original values of all settings for comparison."""
        self.original_values = {
            'default_provider': self.settings.get('web_search', 'default_provider', default='google_serper'),
            'max_results': self.settings.get('web_search', 'max_results', default=5),
            'scrape_content': self.settings.get('web_search', 'scrape_content', default=True),
            'include_citations': self.settings.get('web_search', 'include_citations', default=True),
        }
        self.has_unsaved_changes = False
        self.update_button_visibility()
        
    def get_current_values(self):
        """Get the current values of all settings."""
        # All providers are always enabled
        all_providers = [
            'google_serper', 'brave_search', 'ddg_search', 
            'exa_search', 'tavily_search'
        ]
            
        return {
            'default_provider': self.default_provider.currentData(),
            'max_results': self.max_results.value(),
            'scrape_content': self.scrape_content.isChecked(),
            'include_citations': self.include_citations.isChecked(),
            'enabled_providers': all_providers,
        }
        
    def check_for_changes(self):
        """Check if there are any unsaved changes."""
        current = self.get_current_values()
        self.has_unsaved_changes = any([
            current['default_provider'] != self.original_values['default_provider'],
            current['max_results'] != self.original_values['max_results'],
            current['scrape_content'] != self.original_values['scrape_content'],
            current['include_citations'] != self.original_values['include_citations'],
        ])
        
        self.update_button_visibility()
        
    def update_button_visibility(self):
        """Update the visibility of action buttons based on changes."""
        self.button_container.setVisible(self.has_unsaved_changes)
        
    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Web Search Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)
        
        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        
        # Content widget for scroll area
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # General search settings section
        general_section, general_layout = self.create_section("General Search Settings")
        
        # Default search provider
        provider_container = QWidget()
        provider_layout = QVBoxLayout(provider_container)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        
        provider_label = QLabel("Default Search Provider")
        provider_label.setStyleSheet("font-weight: bold;")
        
        self.default_provider = QComboBox()
        self.default_provider.setStyleSheet("""
            QComboBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        
        # Add search providers
        self.default_provider.addItem("Google Serper", "google_serper")
        self.default_provider.addItem("Brave Search", "brave_search")
        self.default_provider.addItem("DuckDuckGo Search", "ddg_search")
        self.default_provider.addItem("Exa Search", "exa_search")
        self.default_provider.addItem("Tavily Search", "tavily_search")
        
        # Set current default provider
        current_provider = self.settings.get('web_search', 'default_provider', default='google_serper')
        index = self.default_provider.findData(current_provider)
        if index >= 0:
            self.default_provider.setCurrentIndex(index)
            
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.default_provider)
        
        # Max results
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        results_label = QLabel("Maximum Search Results")
        results_label.setStyleSheet("font-weight: bold;")
        
        self.max_results = QSpinBox()
        self.max_results.setRange(1, 20)
        self.max_results.setValue(self.settings.get('web_search', 'max_results', default=5))
        self.max_results.setStyleSheet("""
            QSpinBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        
        results_layout.addWidget(results_label)
        results_layout.addWidget(self.max_results)
        
        # Scrape content checkbox
        self.scrape_content = QCheckBox("Scrape content from search results")
        self.scrape_content.setChecked(self.settings.get('web_search', 'scrape_content', default=True))
        
        # Include citations checkbox
        self.include_citations = QCheckBox("Include citations in responses")
        self.include_citations.setChecked(self.settings.get('web_search', 'include_citations', default=True))
        
        # Add all to general layout
        general_layout.addWidget(provider_container)
        general_layout.addWidget(results_container)
        general_layout.addWidget(self.scrape_content)
        general_layout.addWidget(self.include_citations)
        
        # Add sections to main layout
        layout.addWidget(general_section)
        layout.addStretch()
        
        # Set scroll area widget
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Create button container at the bottom
        self.button_container = QWidget()
        button_layout = QHBoxLayout(self.button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        # Add Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
        cancel_button.clicked.connect(self._cancel_changes)
        
        # Add Save button
        save_all_button = QPushButton("Save Changes")
        save_all_button.setStyleSheet("""
            QPushButton {
                background-color: #2b5c99;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
        """)
        save_all_button.clicked.connect(self._save_all_changes)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_all_button)
        
        main_layout.addWidget(self.button_container)
        self.button_container.hide()  # Initially hide the buttons
        
        # Connect change signals
        self.default_provider.currentIndexChanged.connect(self._on_any_change)
        self.max_results.valueChanged.connect(self._on_any_change)
        self.scrape_content.stateChanged.connect(self._on_any_change)
        self.include_citations.stateChanged.connect(self._on_any_change)
        
    def create_section(self, title):
        """Create a styled section with title and return both the section and its layout."""
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
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #cccccc;")
        layout.addWidget(title_label)
        
        return section, layout
    
    def _on_any_change(self):
        """Handler for any change in the settings."""
        self.check_for_changes()
        
    def _cancel_changes(self):
        """Cancel all changes and restore original values."""
        # Restore default provider
        index = self.default_provider.findData(self.original_values['default_provider'])
        if index >= 0:
            self.default_provider.setCurrentIndex(index)
            
        # Restore max results
        self.max_results.setValue(self.original_values['max_results'])
        
        # Restore checkboxes
        self.scrape_content.setChecked(self.original_values['scrape_content'])
        self.include_citations.setChecked(self.original_values['include_citations'])
        
        self.has_unsaved_changes = False
        self.update_button_visibility()
        
    def _save_all_changes(self):
        """Save all changes to settings."""
        current = self.get_current_values()
        
        # Save default provider
        self.settings.set(current['default_provider'], 'web_search', 'default_provider')
        
        # Save max results
        self.settings.set(current['max_results'], 'web_search', 'max_results')
        
        # Save checkboxes
        self.settings.set(current['scrape_content'], 'web_search', 'scrape_content')
        self.settings.set(current['include_citations'], 'web_search', 'include_citations')
        
        # Save enabled providers - all providers are always enabled
        self.settings.set(current['enabled_providers'], 'web_search', 'enabled_providers')
        
        # Update original values
        self.save_original_values()
        
        # Emit signal that search settings changed
        self.search_settings_changed.emit()
        
        # Create custom message box with restart button
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Settings Saved")
        msg_box.setText("Web search settings have been saved successfully.")
        msg_box.setInformativeText(
            "For the changes to take full effect, would you like to restart the Dasi service now?"
        )
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        # Style the buttons
        for button in msg_box.buttons():
            if msg_box.buttonRole(button) == QMessageBox.ButtonRole.YesRole:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #2b5c99;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #366bb3;
                    }
                    QPushButton:pressed {
                        background-color: #1f4573;
                    }
                """)

        response = msg_box.exec()

        if response == QMessageBox.StandardButton.Yes:
            self._restart_dasi_service()
        
    def _restart_dasi_service(self):
        """Helper method to restart Dasi service with a single message."""
        from PyQt6.QtCore import QTimer
        
        main_window = self.window()
        if main_window and hasattr(main_window, 'stop_dasi') and hasattr(main_window, 'start_dasi'):
            # Stop Dasi without showing message
            main_window.stop_dasi(show_message=False)
            
            # Small delay to ensure proper shutdown
            QTimer.singleShot(500, lambda: self._start_dasi_after_stop(main_window))

    def _start_dasi_after_stop(self, main_window):
        """Helper method to start Dasi after stopping."""
        # Start Dasi without showing message
        main_window.start_dasi(show_message=False)
        
        # Show a single success message
        QMessageBox.information(
            self,
            "Success",
            "Dasi service has been restarted successfully.",
            QMessageBox.StandardButton.Ok
        ) 