from PyQt6.QtWidgets import (QTextEdit, QFrame, QVBoxLayout, QLabel, 
                            QPushButton, QGridLayout, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from pathlib import Path
from ..highlighter import MentionHighlighter

class ContextLabel(QFrame):
    """Label for displaying selected text context."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contextFrame")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        self.setLayout(layout)

        # Create container for the context area
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # Create label
        self.label = QLabel()
        self.label.setObjectName("contextLabel")
        self.label.setWordWrap(True)
        self.label.hide()

        # Create ignore button
        self.ignore_button = QPushButton("×")
        self.ignore_button.setObjectName("ignoreButton")
        self.ignore_button.setFixedSize(16, 16)
        self.ignore_button.hide()

        # Add both widgets to the same grid cell
        grid.addWidget(self.label, 0, 0)
        grid.addWidget(self.ignore_button, 0, 0, 
                      Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        # Ensure ignore button stays on top
        self.label.stackUnder(self.ignore_button)

        layout.addWidget(container)

        # Style components
        self.setStyleSheet("""
            #contextFrame {
                background: transparent;
            }
            #contextLabel {
                color: #888888;
                font-size: 11px;
                padding: 4px 6px;
                background-color: #323232;
                border-radius: 3px;
            }
            #ignoreButton {
                background-color: #464646;
                color: #999999;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
            }
            #ignoreButton:hover {
                background-color: #565656;
                color: #ffffff;
            }
        """)

    def set_text(self, text: str):
        """Set the context label text."""
        if text:
            self.label.setText(f"Selected Text: {text[:100]}..." if len(text) > 100 else f"Selected Text: {text}")
            self.show()
        else:
            self.hide()

    def show(self):
        """Show both label and ignore button."""
        self.label.show()
        self.ignore_button.show()
        super().show()

    def hide(self):
        """Hide both label and ignore button."""
        self.label.hide()
        self.ignore_button.hide()
        super().hide()

class InputField(QTextEdit):
    """Input field component with context label and syntax highlighting."""
    submit_triggered = pyqtSignal()

    def __init__(self, chunks_dir: Path = None):
        super().__init__()
        self.setPlaceholderText("Type your query...")
        self.setMinimumHeight(80)
        self.chunks_dir = chunks_dir
        self._setup_ui()
        self._setup_highlighter()

    def _setup_ui(self):
        """Set up the UI components."""
        self.setStyleSheet("""
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #4a4a4a;
                font-size: 12px;
                color: #ffffff;
                font-family: "Helvetica", sans-serif;
            }
            QTextEdit::selection {
                background-color: #4a4a4a;
                color: #ffffff;
            }
        """)

    def _setup_highlighter(self):
        """Set up syntax highlighting for @mentions."""
        self.highlighter = MentionHighlighter(self.document(), self.chunks_dir)

    def keyPressEvent(self, event):
        """Handle key events."""
        # Submit on Enter (without Shift)
        if (event.key() == Qt.Key.Key_Return and 
            not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submit_triggered.emit()
            return

        super().keyPressEvent(event)

    def update_chunks_dir(self, chunks_dir: Path):
        """Update the chunks directory and refresh highlighter."""
        self.chunks_dir = chunks_dir
        if self.highlighter:
            self.highlighter.chunks_dir = chunks_dir
            self.highlighter.update_available_chunks()

    def get_text(self) -> str:
        """Get the current input text."""
        return self.toPlainText().strip()

    def clear_text(self):
        """Clear the input field."""
        self.clear()
