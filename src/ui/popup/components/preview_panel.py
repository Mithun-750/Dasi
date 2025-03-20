from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QComboBox, QSizePolicy, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor

class PreviewPanel(QWidget):
    """Preview panel component for the Dasi window."""
    
    # Signals
    accept_clicked = pyqtSignal(str, str)  # Emitted when accept is clicked (method, response)
    export_clicked = pyqtSignal(str)  # Emitted when export is clicked (response)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Response preview
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)  # Start as read-only
        self.response_preview.setFixedWidth(340)
        self.response_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #4a4a4a;
                font-size: 12px;
                color: #ffffff;
                font-family: "Helvetica", sans-serif;
            }
            QTextEdit[editable="true"] {
                background-color: #262626;
                border: 1px solid #444444;
            }
            QTextEdit[editable="true"]:focus {
                border: 1px solid #e67e22;
            }
        """)
        self.response_preview.hide()
        
        # Action frame for buttons and selector
        self.action_frame = QFrame()
        self.action_layout = QVBoxLayout()
        self.action_layout.setContentsMargins(5, 0, 5, 5)
        self.action_layout.setSpacing(8)  # Increased spacing between elements
        
        # Create insertion method selector
        self.insert_method = QComboBox()
        self.insert_method.setObjectName("insertMethod")
        self.insert_method.addItem("⚡ Copy/Paste", "paste")
        self.insert_method.addItem("⌨ Type Text", "type")
        self.insert_method.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.insert_method.setMinimumHeight(32)  # Ensure minimum height
        
        # Apply specific styles to make dropdown more visible
        self.insert_method.setStyleSheet("""
            QComboBox {
                background-color: #363636;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 5px 8px;
                color: #cccccc;
                min-height: 32px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #aaa;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #363636;
                border: 1px solid #4a4a4a;
                color: #cccccc;
                selection-background-color: #4a4a4a;
                selection-color: white;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 24px;
                padding: 5px;
            }
        """)
        
        # Create accept/export buttons
        self.accept_button = QPushButton("Accept")
        self.export_button = QPushButton("Export")
        
        # Configure buttons
        self.accept_button.clicked.connect(self._handle_accept)
        self.export_button.clicked.connect(self._handle_export)
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.export_button)
        
        # Add widgets to action layout
        self.action_layout.addWidget(self.insert_method)
        self.action_layout.addLayout(button_layout)
        self.action_frame.setLayout(self.action_layout)
        self.action_frame.hide()
        
        # Add widgets to main layout
        layout.addWidget(self.response_preview, 1)
        layout.addWidget(self.action_frame)
        
        self.setLayout(layout)
    
    def set_response(self, response: str):
        """Set the response text in the preview."""
        self.response_preview.setText(response)
        self.response_preview.show()
        
        # Auto-scroll to bottom
        scrollbar = self.response_preview.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def set_editable(self, editable: bool):
        """Set whether the response preview is editable."""
        self.response_preview.setReadOnly(not editable)
        self.response_preview.setProperty("editable", editable)
        self.response_preview.style().unpolish(self.response_preview)
        self.response_preview.style().polish(self.response_preview)
        
        if editable:
            self.response_preview.setPlaceholderText("You can edit this response before accepting...")
    
    def show_actions(self, show: bool):
        """Show or hide the action frame."""
        self.action_frame.setVisible(show)
    
    def show_preview(self, show: bool):
        """Show or hide the response preview."""
        self.response_preview.setVisible(show)
    
    def clear(self):
        """Clear the response preview."""
        self.response_preview.clear()
    
    def _handle_accept(self):
        """Handle accept button click."""
        response = self.response_preview.toPlainText()
        if response:
            # Remove any leading colon that might be in the response
            if response.startswith(':'):
                response = response[1:].lstrip()
            
            # Get selected insertion method
            method = self.insert_method.currentData()
            
            # Emit signal with method and response
            self.accept_clicked.emit(method, response)
    
    def _handle_export(self):
        """Handle export button click."""
        response = self.response_preview.toPlainText()
        if response:
            self.export_clicked.emit(response) 