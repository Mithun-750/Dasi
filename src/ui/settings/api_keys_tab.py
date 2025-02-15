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
        google_section = QWidget()
        google_layout = QVBoxLayout(google_section)
        google_layout.setSpacing(10)

        google_label = QLabel("Google API Key")
        google_label.setStyleSheet("font-size: 14px;")

        # API Key input with show/hide toggle
        key_container = QWidget()
        key_layout = QHBoxLayout(key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter your Google API key here...")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
        """)

        # Load existing API key if present
        if api_key := self.settings.get_api_key('google'):
            self.api_input.setText(api_key)

        # Toggle visibility button
        self.toggle_button = QPushButton("👁")
        self.toggle_button.setFixedSize(30, 30)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_key_visibility)

        key_layout.addWidget(self.api_input)
        key_layout.addWidget(self.toggle_button)

        google_layout.addWidget(google_label)
        google_layout.addWidget(key_container)

        # Status label (hidden by default)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
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
        self.status_label.hide()
        google_layout.addWidget(self.status_label)

        # Save button
        save_button = QPushButton("Save API Key")
        save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 4px;
                max-width: 150px;
            }
        """)
        save_button.clicked.connect(self.save_api_key)

        google_layout.addWidget(save_button)
        layout.addWidget(google_section)

        # Add stretch to push everything to the top
        layout.addStretch()

    def toggle_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_button.setText("🔒")
        else:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button.setText("👁")

    def show_status(self, message: str, is_error: bool = False):
        """Show a status message with appropriate styling."""
        self.status_label.setText(message)
        self.status_label.setProperty(
            "status", "error" if is_error else "success")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.show()

    def save_api_key(self):
        """Save the API key."""
        api_key = self.api_input.text().strip()

        if not api_key:
            self.show_status("Please enter an API key", True)
            return

        if self.settings.set_api_key('google', api_key):
            # Hide the key after saving
            self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button.setText("👁")

            # Show success message
            self.show_status("API key saved successfully!")

            # Show confirmation dialog
            QMessageBox.information(
                self,
                "Success",
                "API key has been saved successfully. You can now use Dasi with the new API key.",
                QMessageBox.StandardButton.Ok
            )
        else:
            # Show error message
            self.show_status("Failed to save API key", True)
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save API key. Please try again.",
                QMessageBox.StandardButton.Ok
            )
