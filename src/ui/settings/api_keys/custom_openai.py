"""
Custom OpenAI models section for the API Keys tab.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QFrame, QScrollArea, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
import os
import logging
from .common import APICategory, show_status, toggle_key_visibility, create_field_row
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
        self.parent = parent
        
        # Get path to eye icons for visibility toggle
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            icons_dir = os.path.join(base_path, "assets", "icons")
        else:
            icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "icons")
        
        # Try PNG first, then fall back to SVG if needed
        self.eye_icon_path = os.path.join(icons_dir, "eye.png")
        if not os.path.exists(self.eye_icon_path):
            self.eye_icon_path = os.path.join(icons_dir, "eye.svg")
        
        if not os.path.exists(self.eye_icon_path):
            logging.error(f"Eye icon not found at: {self.eye_icon_path}")
        
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
        
        # Title and instructions
        instructions_label = QLabel("Add your custom OpenAI-compatible API endpoints.")
        instructions_label.setProperty("class", "form-description")
        instructions_label.setWordWrap(True)
        self.custom_openai_layout.addWidget(instructions_label)
        
        # Scroll area for models list
        models_scroll = QScrollArea()
        models_scroll.setWidgetResizable(True)
        models_scroll.setProperty("class", "transparent-container")
        models_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        models_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        models_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        models_container = QWidget()
        self.models_layout = QVBoxLayout(models_container)
        self.models_layout.setSpacing(12)
        self.models_layout.setContentsMargins(0, 0, 8, 0)
        
        models_scroll.setWidget(models_container)
        self.custom_openai_layout.addWidget(models_scroll)
        
        # Add New Model button
        add_model_btn = QPushButton("Add Custom Model")
        add_model_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_model_btn.setProperty("class", "primary")
        add_model_btn.clicked.connect(self.add_custom_model)
        
        self.custom_openai_layout.addWidget(add_model_btn)
        
        # Add spacer at bottom
        self.custom_openai_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        
        # Load existing custom models
        self.load_custom_models()
        
    def load_custom_models(self):
        # Clear existing models first
        while self.models_layout.count():
            item = self.models_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Get custom models from settings
        custom_models = self.settings.get('llm', 'custom_openai_models', default=[])
        
        # Add UI for each custom model
        for model_data in custom_models:
            self.add_custom_model(model_data)
    
    def add_custom_model(self, model_data=None):
        model_frame = QWidget()
        model_frame.setProperty("class", "model-frame")
        model_layout = QVBoxLayout(model_frame)
        model_layout.setSpacing(8)
        model_layout.setContentsMargins(12, 12, 12, 12)
        
        # Default values
        model_name = ""
        model_endpoint = ""
        model_api_key = ""
        
        # If model_data is provided, use it
        if isinstance(model_data, dict):
            model_name = model_data.get('name', '')
            model_endpoint = model_data.get('endpoint', '')
            model_api_key = model_data.get('api_key', '')
        
        # Create fields
        name_row, name_field = create_field_row("Model Name:", "Enter a name for this model")
        endpoint_row, endpoint_field = create_field_row("API Endpoint:", "Enter the base URL (e.g., https://your-server/v1)")
        api_key_row, api_key_field, toggle_btn = create_field_row(
            "API Key:", "Enter your API key", 
            is_password=True, 
            toggle_icon=self.eye_icon_path
        )
        
        # Set values if we have them
        name_field.setText(model_name)
        endpoint_field.setText(model_endpoint)
        api_key_field.setText(model_api_key)
        
        # Connect toggle function
        toggle_btn.clicked.connect(lambda: toggle_key_visibility(api_key_field, toggle_btn))
        
        # Add to layout
        model_layout.addWidget(name_row)
        model_layout.addWidget(endpoint_row)
        model_layout.addWidget(api_key_row)
        
        # Action buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        
        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(lambda: self.save_custom_openai_model(
            model_frame,
            name_field.text(),
            endpoint_field.text(),
            api_key_field.text()
        ))
        
        delete_btn = QPushButton("Delete")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(lambda: self.delete_custom_openai_model(model_frame))
        
        # Add buttons to row
        buttons_row.addWidget(save_btn)
        buttons_row.addWidget(delete_btn)
        buttons_row.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        model_layout.addLayout(buttons_row)
        
        # Add to parent layout
        self.models_layout.insertWidget(self.models_layout.count(), model_frame)
    
    def save_custom_openai_model(self, model_frame, name, endpoint, api_key):
        # Validate inputs
        if not name or not endpoint:
            # Could show error message here
            return
        
        # Get all existing models
        custom_models = self.settings.get('llm', 'custom_openai_models', default=[])
        
        # Create or update model data
        model_data = {
            'name': name,
            'endpoint': endpoint,
            'api_key': api_key
        }
        
        # Check if this is an edit or a new model
        found = False
        for i, existing_model in enumerate(custom_models):
            if existing_model.get('name') == name:
                # Update existing model
                custom_models[i] = model_data
                found = True
                break
        
        if not found:
            # Add new model
            custom_models.append(model_data)
        
        # Save to settings
        self.settings.set('llm', 'custom_openai_models', custom_models)
        
        # If this is parent LLM Settings window, refresh providers combobox
        if hasattr(self.parent, 'refresh_providers'):
            self.parent.refresh_providers()
    
    def delete_custom_openai_model(self, model_frame):
        # Get the model name from the widget
        name_field = None
        for i in range(model_frame.layout().count()):
            item = model_frame.layout().itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, QWidget):
                for child in widget.findChildren(QLineEdit):
                    if child.placeholderText() == "Enter a name for this model":
                        name_field = child
                        break
                if name_field:
                    break
        
        if not name_field:
            return
        
        model_name = name_field.text()
        
        # Remove from settings
        custom_models = self.settings.get('llm', 'custom_openai_models', default=[])
        
        custom_models = [m for m in custom_models if m.get('name') != model_name]
        self.settings.set('llm', 'custom_openai_models', custom_models)
        
        # Remove from UI
        model_frame.deleteLater()
        
        # If this is parent LLM Settings window, refresh providers combobox
        if hasattr(self.parent, 'refresh_providers'):
            self.parent.refresh_providers()
        
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
        add_model_button.clicked.connect(self.add_custom_model)
        return add_model_button