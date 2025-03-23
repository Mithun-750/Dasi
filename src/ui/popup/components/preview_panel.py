from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QComboBox, QSizePolicy, QFrame,
                             QProxyStyle, QStyle, QStyledItemDelegate, QStackedWidget, QCheckBox,
                             QScrollArea, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal, QDir, QEvent, QSize, QPoint, QRect, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QTextCursor, QColor, QPen, QPainterPath, QPainter, QCursor
import sys
import os
import logging

from .markdown_renderer import MarkdownRenderer

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

# Custom ComboBox with animated popup
class CustomComboBox(QComboBox):
    """ComboBox with custom popup and animation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Apply custom arrow
        self.setStyle(ComboBoxStyle())
        
        # Create popup frame
        self.popup_frame = QFrame(self.window())
        self.popup_frame.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.popup_frame.setProperty("class", "popup-frame")
        
        # Create shadow effect
        self.popup_frame.setStyleSheet("""
            QFrame.popup-frame {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        
        # Create scroll area for better handling of many items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: transparent;")
        
        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setProperty("class", "popup-list")
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                color: #e0e0e0;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #e67e22;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #2e2e2e;
                border-left: 2px solid #e67e22;
            }
        """)
        
        # Set up the popup layout
        self.scroll_area.setWidget(self.list_widget)
        self.popup_layout = QVBoxLayout(self.popup_frame)
        self.popup_layout.setContentsMargins(0, 0, 0, 0)
        self.popup_layout.addWidget(self.scroll_area)
        
        # Connect list widget signals
        self.list_widget.itemClicked.connect(self._handle_item_selected)
        
        # Add animation
        self.animation = QPropertyAnimation(self.popup_frame, b"geometry")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.animation.setDuration(180)  # Animation duration in milliseconds
        
        # Remember if popup is visible
        self.popup_visible = False
        
        # Set fixed item height to make calculations easier
        self.item_height = 32
        
        # Set max height in items
        self.max_visible_items = 10
        
    def showPopup(self):
        """Show custom popup instead of standard dropdown."""
        if self.count() == 0 or not self.isEnabled():
            return
            
        # Calculate popup position and size
        popup_width = max(self.width(), 260)  # Minimum width for better readability
        
        # Calculate height based on number of items (limited by max_visible_items)
        items_height = min(self.count(), self.max_visible_items) * self.item_height
        popup_height = items_height + 8  # Add padding
        
        # Get global position for the popup
        pos = self.mapToGlobal(QPoint(0, self.height()))
        
        # Clear and populate list widget
        self.list_widget.clear()
        for i in range(self.count()):
            item = QListWidgetItem(self.itemText(i))
            # Store item data for later retrieval
            if self.itemData(i) is not None:
                item.setData(Qt.ItemDataRole.UserRole, self.itemData(i))
            self.list_widget.addItem(item)
        
        # Set the current item
        if self.currentIndex() >= 0:
            self.list_widget.setCurrentRow(self.currentIndex())
        
        # Set initial and final geometry for animation
        start_rect = QRect(pos.x(), pos.y(), popup_width, 0)
        end_rect = QRect(pos.x(), pos.y(), popup_width, popup_height)
        
        # Set up animation
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        
        # Show popup
        self.popup_frame.setGeometry(start_rect)
        self.popup_frame.show()
        self.animation.start()
        
        # Set popup visible flag
        self.popup_visible = True
        
        # Install event filter to handle mouse events outside the popup
        self.window().installEventFilter(self)
    
    def hidePopup(self):
        """Hide the custom popup."""
        if not self.popup_visible:
            return
            
        # Set up closing animation
        current_rect = self.popup_frame.geometry()
        start_rect = current_rect
        end_rect = QRect(current_rect.x(), current_rect.y(), current_rect.width(), 0)
        
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        
        # Connect animation finished signal to hide the popup
        self.animation.finished.connect(self._finish_hiding)
        
        # Start the closing animation
        self.animation.start()
        
        # Remove event filter
        self.window().removeEventFilter(self)
        
        # Set popup visible flag
        self.popup_visible = False
    
    def _finish_hiding(self):
        """Hide the popup frame and disconnect signal after animation."""
        self.popup_frame.hide()
        try:
            self.animation.finished.disconnect(self._finish_hiding)
        except:
            # Signal might already be disconnected
            pass
    
    def _handle_item_selected(self, item):
        """Handle item selection from the list."""
        index = self.list_widget.row(item)
        self.setCurrentIndex(index)
        self.hidePopup()
        self.activated.emit(index)
        
    def eventFilter(self, obj, event):
        """Handle events for checking if clicked outside the popup."""
        if event.type() == QEvent.Type.MouseButtonPress and self.popup_visible:
            # Check if the click is outside both the combo box and the popup
            pos = event.globalPosition().toPoint()
            if not self.popup_frame.geometry().contains(pos) and not self.geometry().contains(self.mapFromGlobal(pos)):
                self.hidePopup()
                return True
        return super().eventFilter(obj, event)
    
    def wheelEvent(self, event):
        """Override wheel event to prevent scroll changing the selection when popup is not visible."""
        if not self.popup_visible:
            event.ignore()

class PreviewPanel(QWidget):
    """Preview panel component for the Dasi window."""
    
    # Signals
    accept_clicked = pyqtSignal(str, str)  # Emitted when accept is clicked (method, response)
    export_clicked = pyqtSignal(str)  # Emitted when export is clicked (response)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_chat_mode = False  # Default to compose mode
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Get the checkmark path based on running mode
        if getattr(sys, 'frozen', False):
            # Running as bundled app
            base_path = sys._MEIPASS
            checkmark_path = os.path.join(base_path, "assets", "icons", "checkmark.svg")
        else:
            # Running in development
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            checkmark_path = os.path.join(app_dir, "ui", "assets", "icons", "checkmark.svg")
        
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)  # Reduced spacing from 5px to 3px
        
        # Create a stacked widget to hold both preview types
        self.preview_stack = QStackedWidget()
        self.preview_stack.setFixedWidth(330)  # Keep fixed width for consistent UI
        self.preview_stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        
        # Plain text preview (for compose mode)
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)  # Start as read-only
        self.response_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
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
                min-height: 0px;
            }
            QTextEdit[editable="true"] {
                background-color: #262626;
                border: 1px solid #444444;
            }
            QTextEdit[editable="true"]:focus {
                border: 1px solid #e67e22;
            }
        """)
        
        # Markdown preview (for chat mode)
        self.markdown_preview = MarkdownRenderer()
        
        # Add both widgets to the stack
        self.preview_stack.addWidget(self.response_preview)  # Index 0: Plain text
        self.preview_stack.addWidget(self.markdown_preview)  # Index 1: Markdown
        
        # Action frame for buttons and selector
        self.action_frame = QFrame()
        self.action_frame.setFixedWidth(330)  # Match width with response preview
        self.action_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)  # Only take minimum vertical space
        self.action_layout = QVBoxLayout()
        self.action_layout.setContentsMargins(2, 0, 2, 0)  # Removed bottom margin completely
        self.action_layout.setSpacing(4)  # Further reduced spacing between elements
        
        # Top row with selector and edit checkbox
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        top_row.setContentsMargins(0, 0, 0, 0)
        
        # Create insertion method selector with improved styling
        self.insert_method = CustomComboBox()
        self.insert_method.setObjectName("insertMethod")
        self.insert_method.addItem("⚡ Copy/Paste", "paste")
        self.insert_method.addItem("⌨ Type Text", "type")
        self.insert_method.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.insert_method.setMinimumHeight(30)  # Reduced height from 36px to 30px
        
        # Apply improved styling matching the style in input_panel.py
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
        """)
        
        # Set delegate for consistent item height
        self.insert_method.setItemDelegate(QStyledItemDelegate())
        
        # Add edit checkbox
        self.edit_checkbox = QCheckBox("Edit")
        self.edit_checkbox.setChecked(True)  # Default to editable in compose mode
        self.edit_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: #e0e0e0;
                font-size: 12px;
                spacing: 5px;
                outline: none;
                border: none;
            }}
            QCheckBox:focus, QCheckBox:hover {{
                outline: none;
                border: none;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid #444444;
                border-radius: 3px;
                background-color: #2a2a2a;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2d2d2d;
                border: 1px solid #ff9f30;
                image: url("{checkmark_path}");
            }}
            QCheckBox::indicator:hover {{
                border-color: #ff9f30;
                background-color: #333333;
            }}
            QCheckBox:hover {{
                color: #ffffff;
                outline: none;
                border: none;
            }}
        """)
        self.edit_checkbox.stateChanged.connect(self._toggle_edit_mode)
        
        # Add widgets to top row
        top_row.addWidget(self.insert_method, 1)  # Give the combo box more space
        top_row.addWidget(self.edit_checkbox, 0)  # Give the checkbox less space
        
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
        self.action_layout.addLayout(top_row)
        self.action_layout.addLayout(button_layout)
        self.action_frame.setLayout(self.action_layout)
        self.action_frame.hide()
        
        # Add widgets to main layout
        layout.addWidget(self.preview_stack, 1)
        layout.addWidget(self.action_frame, 0)  # Use 0 stretch factor to minimize height
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)  # Make entire panel take minimum required height
    
    def _toggle_edit_mode(self):
        """Toggle between editable text and markdown preview."""
        if not self.is_chat_mode:  # Only applies in compose mode
            if self.edit_checkbox.isChecked():
                # Switch to editable text mode
                current_text = self.markdown_preview.get_plain_text() if self.preview_stack.currentWidget() == self.markdown_preview else self.response_preview.toPlainText()
                self.preview_stack.setCurrentWidget(self.response_preview)
                self.response_preview.setText(current_text)
                self.set_editable(True)
            else:
                # Switch to markdown preview mode
                current_text = self.response_preview.toPlainText()
                self.preview_stack.setCurrentWidget(self.markdown_preview)
                self.markdown_preview.set_markdown(current_text)
                
    def set_chat_mode(self, is_chat_mode: bool):
        """Set whether the panel is in chat mode (markdown) or compose mode (plain text)."""
        # If mode is changing, transfer content between widgets
        if self.is_chat_mode != is_chat_mode:
            if is_chat_mode:
                # Transferring from text to markdown
                current_text = self.response_preview.toPlainText()
                self.preview_stack.setCurrentWidget(self.markdown_preview)
                if current_text:
                    self.markdown_preview.set_markdown(current_text)
                # Hide edit checkbox in chat mode
                self.edit_checkbox.setVisible(False)
            else:
                # Transferring from markdown to text
                current_text = self.markdown_preview.get_plain_text()
                # Check if edit mode is enabled
                if self.edit_checkbox.isChecked():
                    self.preview_stack.setCurrentWidget(self.response_preview)
                    if current_text:
                        self.response_preview.setText(current_text)
                    # Make text editable when switching to compose mode with edit enabled
                    self.response_preview.setReadOnly(False)
                    self.response_preview.setProperty("editable", True)
                    self.response_preview.style().unpolish(self.response_preview)
                    self.response_preview.style().polish(self.response_preview)
                    self.response_preview.setPlaceholderText("You can edit this response before accepting...")
                else:
                    # Keep markdown view but update content
                    if current_text:
                        self.markdown_preview.set_markdown(current_text)
                # Show edit checkbox in compose mode
                self.edit_checkbox.setVisible(True)
        
        self.is_chat_mode = is_chat_mode
    
    def set_response(self, response: str):
        """Set the response text in the preview."""
        if not response:
            return
            
        # Update both widgets to keep content in sync
        self.response_preview.setText(response)
        self.markdown_preview.set_markdown(response)
        
        # Show the stack widget
        self.preview_stack.show()
        
        # Auto-scroll to bottom if in text mode
        if not self.is_chat_mode:
            scrollbar = self.response_preview.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def set_editable(self, editable: bool):
        """Set whether the response preview is editable."""
        if self.is_chat_mode:
            # Markdown view is never editable, so switch to text mode if editing is required
            if editable:
                # Get the current markdown text
                md_text = self.markdown_preview.get_plain_text()
                # Switch to text mode and set the content
                self.is_chat_mode = False
                self.preview_stack.setCurrentWidget(self.response_preview)
                self.response_preview.setText(md_text)
                # Make it editable
                self.response_preview.setReadOnly(False)
                self.response_preview.setProperty("editable", True)
                self.response_preview.style().unpolish(self.response_preview)
                self.response_preview.style().polish(self.response_preview)
                self.response_preview.setPlaceholderText("You can edit this response before accepting...")
                # Update checkbox state
                self.edit_checkbox.setVisible(True)
                self.edit_checkbox.setChecked(True)
        else:
            # Normal text mode
            self.response_preview.setReadOnly(not editable)
            self.response_preview.setProperty("editable", editable)
            self.response_preview.style().unpolish(self.response_preview)
            self.response_preview.style().polish(self.response_preview)
            
            if editable:
                self.response_preview.setPlaceholderText("You can edit this response before accepting...")
                
            # Update checkbox state but block signals to prevent recursive calls
            self.edit_checkbox.blockSignals(True)
            self.edit_checkbox.setChecked(editable)
            self.edit_checkbox.blockSignals(False)
    
    def show_actions(self, show: bool):
        """Show or hide the action frame."""
        self.action_frame.setVisible(show)
        # Update edit checkbox visibility based on mode
        self.edit_checkbox.setVisible(show and not self.is_chat_mode)
    
    def show_preview(self, show: bool):
        """Show or hide the response preview."""
        self.preview_stack.setVisible(show)
    
    def clear(self):
        """Clear the response preview."""
        self.response_preview.clear()
        self.markdown_preview.clear()
        self.show_actions(False)  # Hide actions when clearing
    
    def _handle_accept(self):
        """Handle accept button click."""
        # Get response from the appropriate widget
        if self.is_chat_mode:
            response = self.markdown_preview.get_plain_text()
        else:
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
        # Get response from the appropriate widget
        if self.is_chat_mode:
            response = self.markdown_preview.get_plain_text()
        else:
            response = self.response_preview.toPlainText()
            
        if response:
            self.export_clicked.emit(response)
    
    def hide(self):
        """Override hide to ensure both preview widgets are hidden."""
        self.preview_stack.hide()
        super().hide()
    
    def show(self):
        """Override show to ensure the appropriate widget is shown."""
        self.preview_stack.show()
        super().show() 