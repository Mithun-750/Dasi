from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QComboBox, QSizePolicy, QFrame,
                             QProxyStyle, QStyle, QStyledItemDelegate)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor, QColor, QPen, QPainterPath, QPainter

# ComboBoxStyle for proper arrow display - copied from input_panel.py
class ComboBoxStyle(QProxyStyle):
    """Custom style to draw a text arrow for combo boxes."""
    def __init__(self, style=None):
        super().__init__(style)
        self.arrow_color = QColor("#e67e22")  # Orange color for arrow
        
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown and isinstance(widget, QComboBox):
            # Draw a custom arrow
            rect = option.rect
            painter.save()
            
            # Set up the arrow color
            painter.setPen(QPen(self.arrow_color, 1.5))
            
            # Draw a triangle instead of text arrow for more modern look
            # Calculate the triangle points
            width = 9
            height = 6
            x = rect.center().x() - width // 2
            y = rect.center().y() - height // 2
            
            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x + width, y)
            path.lineTo(x + width // 2, y + height)
            path.lineTo(x, y)
            
            # Fill the triangle
            painter.fillPath(path, self.arrow_color)
            
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)

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
        layout.setSpacing(3)  # Reduced spacing from 5px to 3px
        
        # Response preview
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)  # Start as read-only
        self.response_preview.setFixedWidth(330)  # Reduced from 340px to 330px
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
        self.action_frame.setFixedWidth(330)  # Match width with response preview
        self.action_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)  # Only take minimum vertical space
        self.action_layout = QVBoxLayout()
        self.action_layout.setContentsMargins(2, 0, 2, 0)  # Removed bottom margin completely
        self.action_layout.setSpacing(4)  # Further reduced spacing between elements
        
        # Create insertion method selector with improved styling
        self.insert_method = QComboBox()
        self.insert_method.setObjectName("insertMethod")
        self.insert_method.addItem("⚡ Copy/Paste", "paste")
        self.insert_method.addItem("⌨ Type Text", "type")
        self.insert_method.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.insert_method.setMinimumHeight(30)  # Reduced height from 36px to 30px
        
        # Set custom style for modern arrow
        self.insert_method.setStyle(ComboBoxStyle())
        
        # Apply improved styling matching the ChunkDropdown
        self.insert_method.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 4px;
                padding: 5px 10px;
                color: #e0e0e0;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #e67e22;
                background-color: #323232;
            }
            QComboBox:focus {
                border: 1px solid #e67e22;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
                padding-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 4px;
                color: #e0e0e0;
                selection-background-color: #e67e22;
                selection-color: white;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px;
                border-radius: 3px;
                min-height: 20px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #2e2e2e;
                border-left: 2px solid #e67e22;
            }
        """)
        
        # Set delegate for consistent item height
        self.insert_method.setItemDelegate(QStyledItemDelegate())
        
        # Create accept/export buttons
        self.accept_button = QPushButton("Accept")
        self.export_button = QPushButton("Export")
        
        # Configure buttons with slightly smaller width
        self.accept_button.setMinimumWidth(80)
        self.export_button.setMinimumWidth(80)
        self.accept_button.clicked.connect(self._handle_accept)
        self.export_button.clicked.connect(self._handle_export)
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)  # Reduced spacing between buttons
        button_layout.setContentsMargins(0, 0, 0, 0)  # No margins for button layout
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.export_button)
        
        # Add widgets to action layout
        self.action_layout.addWidget(self.insert_method)
        self.action_layout.addLayout(button_layout)
        self.action_frame.setLayout(self.action_layout)
        self.action_frame.hide()
        
        # Add widgets to main layout
        layout.addWidget(self.response_preview, 1)
        layout.addWidget(self.action_frame, 0)  # Use 0 stretch factor to minimize height
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)  # Make entire panel take minimum required height
    
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