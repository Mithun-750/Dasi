from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal


class ConfirmationPanel(QWidget):
    """
    Panel for confirming tool calls (e.g., web search) in the Dasi popup window.
    """
    # Signals
    accepted = pyqtSignal()
    rejected = pyqtSignal()

    def __init__(self, tool_name, tool_args, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self.tool_args = tool_args
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("confirmationContainer")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(12)
        self.setFixedWidth(330)

        # Title
        title = QLabel("Tool Call Confirmation")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; color: #e67e22; font-weight: bold;")
        layout.addWidget(title)

        # Info message
        info = QLabel(self._get_info_text())
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        info.setStyleSheet(
            "font-size: 14px; color: #e0e0e0; margin-top: 8px; font-weight: 500;")
        info.setFixedWidth(290)
        layout.addWidget(info)

        # Accept/Reject buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(16)
        accept_btn = QPushButton("Accept")
        accept_btn.setObjectName("acceptButton")
        accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        accept_btn.setStyleSheet("""
            #acceptButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-size: 13px;
                font-weight: 600;
            }
            #acceptButton:hover {
                background-color: #d35400;
            }
            #acceptButton:pressed {
                background-color: #a04000;
            }
        """)
        accept_btn.clicked.connect(self.accepted.emit)
        reject_btn = QPushButton("Reject")
        reject_btn.setObjectName("rejectButton")
        reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reject_btn.setStyleSheet("""
            #rejectButton {
                background-color: #333333;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-size: 13px;
                font-weight: 600;
            }
            #rejectButton:hover {
                border: 1px solid #e67e22;
            }
            #rejectButton:pressed {
                background-color: #222222;
            }
        """)
        reject_btn.clicked.connect(self.rejected.emit)
        button_row.addWidget(accept_btn)
        button_row.addWidget(reject_btn)
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(button_row)

        self.setStyleSheet("""
            #confirmationContainer {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
        """)

    def _get_info_text(self):
        # Customize this for each tool type
        if self.tool_name == "web_search":
            query = self.tool_args.get("query", "")
            return f"Dasi wants to search the web for: \n\n\"{query}\"\n\nDo you want to allow this?"
        return f"Dasi wants to call tool: {self.tool_name} with args: {self.tool_args}. Allow?"
