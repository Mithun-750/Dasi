"""
Common utilities and classes for API Keys components.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame,
    QComboBox, QCheckBox, QProxyStyle, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
import os
import sys
import logging


class APICategory:
    """Constants for API key categories."""
    LLM_PROVIDERS = "LLM Providers"
    SEARCH_PROVIDERS = "Search Providers"


class ComboBoxStyle(QProxyStyle):
    """Custom style to draw a text arrow for combo boxes."""
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


def create_section(title):
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


def toggle_key_visibility(input_field, toggle_button):
    """Toggle API key visibility."""
    # Get the paths to the eye icons - handle both development and frozen app
    if getattr(sys, 'frozen', False):
        # Running as bundled PyInstaller app
        base_path = sys._MEIPASS
        
        # Try both PNG and SVG formats (prefer PNG first, which seems to work better with PyInstaller)
        eye_icon_path = os.path.join(base_path, "assets", "icons", "eye.png")
        eye_off_icon_path = os.path.join(base_path, "assets", "icons", "eye_off.png")
        
        # If PNG doesn't exist, try SVG
        if not os.path.exists(eye_icon_path):
            eye_icon_path = os.path.join(base_path, "assets", "icons", "eye.svg")
            eye_off_icon_path = os.path.join(base_path, "assets", "icons", "eye_off.svg")
    else:
        # Running in development
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "icons")
        # Prefer PNG in development mode too for consistency
        eye_icon_path = os.path.join(icons_dir, "eye.png")
        eye_off_icon_path = os.path.join(icons_dir, "eye_off.png")
        
        # If PNG doesn't exist, try SVG
        if not os.path.exists(eye_icon_path):
            eye_icon_path = os.path.join(icons_dir, "eye.svg")
            eye_off_icon_path = os.path.join(icons_dir, "eye_off.svg")
    
    # Log errors if icons not found
    if not os.path.exists(eye_icon_path):
        logging.error(f"Eye icon not found at: {eye_icon_path}")
    if not os.path.exists(eye_off_icon_path):
        logging.error(f"Eye-off icon not found at: {eye_off_icon_path}")
    
    if input_field.echoMode() == QLineEdit.EchoMode.Password:
        input_field.setEchoMode(QLineEdit.EchoMode.Normal)
        toggle_button.setIcon(QIcon(eye_off_icon_path))
    else:
        input_field.setEchoMode(QLineEdit.EchoMode.Password)
        toggle_button.setIcon(QIcon(eye_icon_path))


def create_field_row(label_text, placeholder_text, is_password=False, toggle_icon=None):
    """Create a row with label and input field, optionally with password toggle"""
    row_widget = QWidget()
    row_widget.setProperty("class", "field-row")
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(8)
    
    # Label
    label = QLabel(label_text)
    label.setFixedWidth(100)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    
    # Input field
    input_field = QLineEdit()
    input_field.setPlaceholderText(placeholder_text)
    if is_password:
        input_field.setEchoMode(QLineEdit.EchoMode.Password)
    
    # Add label and input to layout
    row_layout.addWidget(label)
    row_layout.addWidget(input_field, 1)  # Give input field stretch
    
    # If this is a password field with toggle, add toggle button
    if is_password and toggle_icon:
        # Create toggle button
        toggle_button = QPushButton()
        toggle_button.setFixedSize(38, 38)
        toggle_button.setProperty("class", "icon-button")
        toggle_button.setIcon(QIcon(toggle_icon))
        toggle_button.setIconSize(QSize(20, 20))
        
        # Add to layout
        row_layout.addWidget(toggle_button)
        
        # Return with toggle button
        return row_widget, input_field, toggle_button
    
    # Return without toggle button
    return row_widget, input_field


def show_status(label, message, is_error=False):
    """Show a status message with appropriate styling."""
    label.setText(message)
    label.setProperty("status", "error" if is_error else "success")
    label.style().unpolish(label)
    label.style().polish(label)
    label.show()


class APIKeySection(QWidget):
    """Base class for API key section widgets."""
    
    # Signal emitted when an API key is cleared
    api_key_cleared = pyqtSignal(str)
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.api_sections = {}  # Store references to API sections
        
    def create_api_key_section(self, title, provider, placeholder, category):
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

    def save_api_key(self, provider, input_field, status_label):
        """Save the API key."""
        # Get the path to the eye icon - try PNG first, then SVG
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
        
        api_key = input_field.text().strip()

        if not api_key:
            show_status(status_label, "Please enter an API key", True)
            return

        if self.settings.set_api_key(provider, api_key):
            # Hide the key after saving
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
            getattr(self, f"{provider}_toggle").setIcon(QIcon(eye_icon_path))

            # Show success message
            show_status(status_label, "API key saved successfully!")

            # Show confirmation dialog
            QMessageBox.information(
                self,
                "Success",
                f"{provider.title()} API key has been saved successfully.",
                QMessageBox.StandardButton.Ok
            )
        else:
            # Show error message
            show_status(status_label, "Failed to save API key", True)
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save API key. Please try again.",
                QMessageBox.StandardButton.Ok
            )

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