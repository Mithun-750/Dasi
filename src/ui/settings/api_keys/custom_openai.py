"""
Custom OpenAI models section for the API Keys tab.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
import os
import logging
from .common import APICategory, show_status, toggle_key_visibility
import sys


class CustomOpenAISection(QWidget):
    """Section for managing custom OpenAI-compatible model configurations."""
    
    # Signal emitted when an API key is cleared
    api_key_cleared = pyqtSignal(str)
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("custom_openai_section")
        self.settings = settings
        self.custom_openai_sections = []  # Track custom OpenAI sections
        self.api_sections = {}  # Store references to API sections
        self.init_ui()
        
    def init_ui(self):
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create container for custom OpenAI models
        self.custom_openai_container = QWidget()
        self.custom_openai_container.setStyleSheet("background-color: transparent;")
        self.custom_openai_layout = QVBoxLayout(self.custom_openai_container)
        self.custom_openai_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_openai_layout.setSpacing(16)
        self.layout.addWidget(self.custom_openai_container)
        
        # Load existing custom OpenAI models
        self.load_existing_custom_openai_models()
        
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
        
        # Set the icon (try PNG first, then SVG)
        if getattr(sys, 'frozen', False):
            # Running in frozen mode
            base_path = sys._MEIPASS
            eye_icon_path = os.path.join(base_path, "assets", "icons", "eye.png")
            if not os.path.exists(eye_icon_path):
                eye_icon_path = os.path.join(base_path, "assets", "icons", "eye.svg")
        else:
            # Running in development mode
            icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "icons")
            eye_icon_path = os.path.join(icons_dir, "eye.png")
            if not os.path.exists(eye_icon_path):
                eye_icon_path = os.path.join(icons_dir, "eye.svg")
        
        if not os.path.exists(eye_icon_path):
            logging.error(f"Eye icon not found at: {eye_icon_path}")
        
        toggle_button.setIcon(QIcon(eye_icon_path))
        toggle_button.setIconSize(QSize(20, 20))
        
        toggle_button.clicked.connect(
            lambda: toggle_key_visibility(api_input, toggle_button)
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
            show_status(last_section['status_label'], "Base URL is required", True)
            last_section['base_url_input'].setFocus()
            return
        elif not model_id:
            show_status(last_section['status_label'], "Model ID is required", True)
            last_section['model_id_input'].setFocus()
            return
        elif not api_key:
            show_status(last_section['status_label'], "API Key is required", True)
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
        if getattr(sys, 'frozen', False):
            # Running in frozen mode
            base_path = sys._MEIPASS
            eye_icon_path = os.path.join(base_path, "assets", "icons", "eye.png")
            if not os.path.exists(eye_icon_path):
                eye_icon_path = os.path.join(base_path, "assets", "icons", "eye.svg")
        else:
            # Running in development mode
            icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "icons")
            eye_icon_path = os.path.join(icons_dir, "eye.png")
            if not os.path.exists(eye_icon_path):
                eye_icon_path = os.path.join(icons_dir, "eye.svg")
        
        if not os.path.exists(eye_icon_path):
            logging.error(f"Eye icon not found at: {eye_icon_path}")
        
        base_url = base_url_input.text().strip()
        model_id = model_id_input.text().strip()
        api_key = api_input.text().strip()
        
        # Validate inputs
        if not base_url:
            show_status(status_label, "Please enter a base URL", True)
            return
            
        if not model_id:
            show_status(status_label, "Please enter a model ID", True)
            return
            
        if not api_key:
            show_status(status_label, "Please enter an API key", True)
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
            show_status(status_label, "Model configuration saved successfully!")
            
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
            show_status(status_label, f"Failed to save model configuration: {str(e)}", True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save model configuration: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
            return False
            
    def clear_api_key(self, provider, input_field, status_label):
        """Clear the API key for the given provider."""
        try:
            # Clear the input field
            input_field.clear()
            
            # Remove from settings
            if self.settings.set_api_key(provider, ""):
                show_status(status_label, "API key cleared successfully!")
                
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
                show_status(status_label, "Failed to clear API key", True)
        except Exception as e:
            show_status(status_label, f"Error clearing API key: {str(e)}", True)
            
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
        
    def get_api_sections(self):
        """Get the API sections dictionary."""
        return self.api_sections
    
    def set_visibility(self, visible):
        """Set the visibility of this section."""
        self.setVisible(visible)
        
    def add_model_button(self):
        """Create and return a button for adding a new custom model."""
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
        return add_model_button