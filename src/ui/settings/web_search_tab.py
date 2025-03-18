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
    QStyledItemDelegate,
    QProxyStyle,
    QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QIcon
from .settings_manager import Settings
from .general_tab import SectionFrame  # Import SectionFrame from general_tab
import logging


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
            'default_provider': self.settings.get('web_search', 'default_provider', default='ddg_search'),
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
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 0, 16)  # Match general_tab padding
        
        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { 
                padding-right: 8px; 
                background-color: transparent; 
            }
            QScrollBar:vertical {
                border: none;
                background-color: transparent;
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
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 8, 0)  # Added 8px right padding for gap between content and scrollbar
        
        # General search settings section
        general_section = SectionFrame(
            "Web Search Settings",
            "Configure how Dasi performs web searches and presents results."
        )
        
        # Default search provider
        provider_container = QWidget()
        provider_container.setProperty("class", "transparent-container")
        provider_layout = QVBoxLayout(provider_container)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.setSpacing(8)
        
        provider_label = QLabel("Default Search Provider")
        provider_label.setProperty("class", "setting-label")
        
        self.default_provider = QComboBox()
        # Updated modern UI styling that matches the global stylesheet
        self.default_provider.setStyleSheet("""
            QComboBox {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 10px 12px;
                color: #e0e0e0;
                min-height: 20px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #444444;
                background-color: #2a2a2a;
            }
            QComboBox:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border-left: 1px solid #333333;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                selection-background-color: #3b82f6;
                selection-color: white;
                padding: 8px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #2a2a2a;
            }
        """)
        
        # Apply custom style for the arrow
        self.default_provider.setStyle(ComboBoxStyle())
        
        # Add search providers
        self.default_provider.addItem("Google Serper", "google_serper")
        self.default_provider.addItem("Brave Search", "brave_search")
        self.default_provider.addItem("DuckDuckGo Search", "ddg_search")
        self.default_provider.addItem("Exa Search", "exa_search")
        self.default_provider.addItem("Tavily Search", "tavily_search")
        
        # Set current default provider - changed to ddg_search
        current_provider = self.settings.get('web_search', 'default_provider', default='ddg_search')
        index = self.default_provider.findData(current_provider)
        if index >= 0:
            self.default_provider.setCurrentIndex(index)
            
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.default_provider)
        
        # Max results
        results_container = QWidget()
        results_container.setProperty("class", "transparent-container")
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(8)
        
        results_label = QLabel("Maximum Search Results")
        results_label.setProperty("class", "setting-label")
        
        self.max_results = QSpinBox()
        self.max_results.setRange(1, 20)
        self.max_results.setValue(self.settings.get('web_search', 'max_results', default=5))
        self.max_results.setStyleSheet("""
            QSpinBox {
                padding: 10px 12px;
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                color: #e0e0e0;
                min-height: 20px;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 1px solid #3b82f6;
                background-color: #2a2a2a;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #333333;
                border: none;
                width: 16px;
                border-radius: 3px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #444444;
            }
        """)
        
        results_layout.addWidget(results_label)
        results_layout.addWidget(self.max_results)
        
        # Options section
        options_container = QWidget()
        options_container.setProperty("class", "transparent-container")
        options_layout = QVBoxLayout(options_container)
        options_layout.setContentsMargins(0, 8, 0, 0)
        options_layout.setSpacing(8)
        
        options_label = QLabel("Additional Options")
        options_label.setProperty("class", "setting-label")
        options_layout.addWidget(options_label)
        
        # Scrape content checkbox - exactly matching api_keys_tab.py styling
        self.scrape_content = QCheckBox("Scrape content from search results")
        self.scrape_content.setChecked(self.settings.get('web_search', 'scrape_content', default=True))
        
        # Include citations checkbox - exactly matching api_keys_tab.py styling
        self.include_citations = QCheckBox("Include citations in responses")
        self.include_citations.setChecked(self.settings.get('web_search', 'include_citations', default=True))
        
        options_layout.addWidget(self.scrape_content)
        options_layout.addWidget(self.include_citations)
        
        # Add all to general layout
        general_section.layout.addWidget(provider_container)
        general_section.layout.addWidget(results_container)
        general_section.layout.addWidget(options_container)
        
        # Add sections to main layout
        layout.addWidget(general_section)
        layout.addStretch()
        
        # Set scroll area widget
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Create button container at the bottom
        self.button_container = QWidget()
        self.button_container.setProperty("class", "transparent-container")
        self.button_container.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(self.button_container)
        button_layout.setContentsMargins(0, 16, 0, 0)
        button_layout.setSpacing(8)
        
        # Add Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self._cancel_changes)
        
        # Add Save button
        save_all_button = QPushButton("Save & Apply")
        save_all_button.setProperty("class", "primary")
        save_all_button.clicked.connect(self._save_all_changes)
        
        button_layout.addWidget(cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(save_all_button)
        
        main_layout.addWidget(self.button_container)
        self.button_container.hide()  # Initially hide the buttons
        
        # Connect change signals
        self.default_provider.currentIndexChanged.connect(self._on_any_change)
        self.max_results.valueChanged.connect(self._on_any_change)
        self.scrape_content.stateChanged.connect(self._on_any_change)
        self.include_citations.stateChanged.connect(self._on_any_change)
    
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
                button.setProperty("class", "primary")
                button.style().unpolish(button)
                button.style().polish(button)

        response = msg_box.exec()

        if response == QMessageBox.StandardButton.Yes:
            self._restart_dasi_service()
        
    def _restart_dasi_service(self):
        """Helper method to restart Dasi service with a single message."""
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