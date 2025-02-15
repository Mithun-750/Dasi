from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from .settings_manager import Settings


class GeneralTab(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("General Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Placeholder text
        placeholder = QLabel(
            "General settings will be added in future updates.")
        placeholder.setStyleSheet("color: #888888; font-size: 13px;")
        layout.addWidget(placeholder)

        # Add stretch to push everything to the top
        layout.addStretch()
