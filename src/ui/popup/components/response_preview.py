from PyQt6.QtWidgets import QTextEdit, QScrollBar
from PyQt6.QtCore import Qt

class ResponsePreview(QTextEdit):
    """Response preview component with editable mode support."""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFixedWidth(300)
        self._setup_ui()

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
            QTextEdit[editable="true"] {
                background-color: #404040;
                border: 1px solid #505050;
            }
            QTextEdit[editable="true"]:focus {
                border: 1px solid #606060;
            }
        """)

    def set_editable(self, editable: bool):
        """Set whether the preview is editable."""
        self.setReadOnly(not editable)
        self.setProperty("editable", editable)
        self.style().unpolish(self)
        self.style().polish(self)
        if editable:
            self.setPlaceholderText("You can edit this response before accepting...")

    def append_text(self, text: str):
        """Append text and auto-scroll to bottom."""
        self.append(text)
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def get_text(self) -> str:
        """Get the current response text."""
        return self.toPlainText().strip()

    def clear_text(self):
        """Clear the response preview."""
        self.clear()
