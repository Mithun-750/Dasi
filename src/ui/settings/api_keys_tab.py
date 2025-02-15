from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from .settings_manager import Settings


class APIKeysTab(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("API Keys")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Google API Key section
        google_section = self.create_api_key_section(
            "Google API Key",
            "google",
            "Enter your Google API key here..."
        )
        layout.addWidget(google_section)

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

        # Add stretch to push everything to the top
        layout.addStretch()

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

        key_layout.addWidget(api_input)
        key_layout.addWidget(toggle_button)

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
