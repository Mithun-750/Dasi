import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import Qt
import qdarktheme


class Settings:
    def __init__(self):
        # Get config directory (following XDG specification)
        self.config_dir = Path(
            os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')) / 'dasi'
        self.config_file = self.config_dir / 'settings.json'

        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Default settings
        self.settings = {
            'google_api_key': ''
        }

        # Load existing settings if they exist
        self.load_settings()

    def load_settings(self):
        """Load settings from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.settings.update(json.load(f))
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to config file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get(self, key: str, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value):
        """Set a setting value and save."""
        self.settings[key] = value
        return self.save_settings()


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Dasi Settings")
        self.setMinimumSize(500, 300)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("Dasi Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignTop)

        # API Key section
        api_section = QWidget()
        api_layout = QVBoxLayout(api_section)
        api_layout.setSpacing(10)

        api_label = QLabel("Google API Key")
        api_label.setStyleSheet("font-size: 14px;")

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter your Google API key here...")
        self.api_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
        """)

        # Load existing API key if present
        if api_key := self.settings.get('google_api_key'):
            self.api_input.setText(api_key)

        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_input)
        layout.addWidget(api_section)

        # Buttons
        button_layout = QHBoxLayout()

        save_button = QPushButton("Save & Launch Dasi")
        save_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        save_button.clicked.connect(self.save_and_launch)

        button_layout.addStretch()
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

        # Add stretch to push everything to the top
        layout.addStretch()

    def save_and_launch(self):
        api_key = self.api_input.text().strip()
        if not api_key:
            QMessageBox.warning(
                self, "Error", "Please enter your Google API key.")
            return

        try:
            # Save API key to settings
            if not self.settings.set('google_api_key', api_key):
                raise Exception("Failed to save settings")

            # Launch main application
            from main import Dasi
            self.hide()  # Hide settings window
            app = Dasi()
            app.run()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save settings: {str(e)}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    window = SettingsWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
