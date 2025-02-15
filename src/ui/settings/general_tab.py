from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QScrollArea,
    QFrame,
    QHBoxLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from .settings_manager import Settings


class GeneralTab(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("General Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)

        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
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

        # Create a widget to hold all settings
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 20, 0)  # Right margin for scrollbar

        # Custom Instructions Section
        instructions_section = QFrame()
        instructions_layout = QVBoxLayout(instructions_section)
        instructions_layout.setSpacing(10)

        instructions_label = QLabel("Custom Instructions")
        instructions_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        instructions_description = QLabel(
            "Add your custom instructions to personalize how Dasi responds to your queries. "
            "These will be added to Dasi's core behavior."
        )
        instructions_description.setWordWrap(True)
        instructions_description.setStyleSheet(
            "color: #888888; font-size: 12px;")

        self.custom_instructions = QTextEdit()
        self.custom_instructions.setMinimumHeight(100)
        self.custom_instructions.setPlaceholderText(
            "Example:\n- Use British English spelling\n- Include code examples in Python\n- Prefer shorter responses")
        self.custom_instructions.setStyleSheet("""
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 12px;
            }
        """)

        # Load existing custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="")
        self.custom_instructions.setText(custom_instructions)

        instructions_layout.addWidget(instructions_label)
        instructions_layout.addWidget(instructions_description)
        instructions_layout.addWidget(self.custom_instructions)

        # LLM Settings Section
        llm_section = QFrame()
        llm_layout = QVBoxLayout(llm_section)
        llm_layout.setSpacing(10)

        llm_label = QLabel("LLM Settings")
        llm_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # Temperature setting
        temp_container = QWidget()
        temp_layout = QHBoxLayout(temp_container)
        temp_layout.setContentsMargins(0, 0, 0, 0)

        temp_label = QLabel("Temperature:")
        temp_label.setStyleSheet("font-size: 12px;")
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 1.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(self.settings.get(
            'general', 'temperature', default=0.7))
        self.temperature.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 5px;
                min-width: 80px;
            }
        """)

        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temperature)
        temp_layout.addStretch()

        llm_layout.addWidget(llm_label)
        llm_layout.addWidget(temp_container)

        # Save button
        save_button = QPushButton("Save Settings")
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
        save_button.clicked.connect(self.save_settings)

        # Add sections to main layout
        layout.addWidget(instructions_section)
        layout.addWidget(llm_section)
        layout.addWidget(save_button)
        layout.addStretch()

        # Set scroll area widget
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def save_settings(self):
        """Save all settings."""
        try:
            # Save custom instructions
            self.settings.set(self.custom_instructions.toPlainText(),
                              'general', 'custom_instructions')

            # Save temperature
            self.settings.set(self.temperature.value(),
                              'general', 'temperature')

            QMessageBox.information(
                self,
                "Success",
                "Settings saved successfully. Please restart Dasi for changes to take effect.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
