from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLineEdit, 
                             QListWidget, QListWidgetItem, QWidget, QTextEdit,
                             QScrollArea, QStyledItemDelegate)
from PyQt6.QtCore import (Qt, QPoint, pyqtSignal, QSize, 
                          QStringListModel, QEvent)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPainterPath
from typing import List


class ChunkDropdown(QFrame):
    """Custom dropdown with search for chunk selection."""
    itemSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        
        # Set frame style with modern look
        self.setProperty("class", "card")
        self.setStyleSheet("""
            QFrame.card {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Create search box with improved styling
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search chunks...")
        self.search_box.setProperty("class", "search-input")
        self.search_box.textChanged.connect(self._filter_items)
        self.search_box.setStyleSheet("""
            QLineEdit.search-input {
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 4px;
                padding: 8px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit.search-input:focus {
                border: 1px solid #e67e22;
                background-color: #323232;
            }
        """)
        layout.addWidget(self.search_box)
        
        # Create scroll area for list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")
        
        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
                color: #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #e67e22;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #2e2e2e;
                border-left: 2px solid #e67e22;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #e67e22;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Set item delegate for custom item height
        self.list_widget.setItemDelegate(QStyledItemDelegate())
        
        # Connect signals
        self.list_widget.itemClicked.connect(self._handle_item_selected)
        self.list_widget.itemActivated.connect(self._handle_item_selected)
        
        # Setup scroll area
        self.scroll.setWidget(self.list_widget)
        layout.addWidget(self.scroll)
        
        # Store all items for filtering
        self.all_items = []

    def update_items(self, items: List[str]):
        """Update the list of available items."""
        self.all_items = items
        self.list_widget.clear()
        
        # Add items to list widget
        for item in items:
            list_item = QListWidgetItem(item)
            self.list_widget.addItem(list_item)
            
        # Select first item if available
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
        # Clear search box and focus
        self.search_box.clear()
        self.search_box.setFocus()

    def _filter_items(self, text):
        """Filter items based on search text."""
        self.list_widget.clear()
        search_text = text.lower()
        
        for item in self.all_items:
            if search_text in item.lower():
                list_item = QListWidgetItem(item)
                self.list_widget.addItem(list_item)
                
        # Select first item in filtered list
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _handle_item_selected(self, item):
        """Handle item selection."""
        if item:
            self.itemSelected.emit(item.text())
            self.hide()

    def keyPressEvent(self, event):
        """Handle key events."""
        if event.key() == Qt.Key.Key_Return and not event.modifiers():
            current = self.list_widget.currentItem()
            if current:
                self.itemSelected.emit(current.text())
                self.hide()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Up:
            current_row = max(0, self.list_widget.currentRow() - 1)
            self.list_widget.setCurrentRow(current_row)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Down:
            current_row = min(self.list_widget.count() - 1, self.list_widget.currentRow() + 1)
            self.list_widget.setCurrentRow(current_row)
            event.accept()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        """Position the dropdown when shown."""
        super().showEvent(event)
        if isinstance(self.parent(), QTextEdit):
            cursor_rect = self.parent().cursorRect()
            global_pos = self.parent().mapToGlobal(cursor_rect.bottomLeft())
            self.move(global_pos + QPoint(0, 5))
            
            # Set fixed width and height
            width = max(300, self.parent().width() // 2)
            height = min(250, (self.list_widget.count() * 36) + 60)  # Reduced from 350 to 250
            self.setFixedSize(width, height)

    def sizeHint(self):
        """Calculate proper size for the dropdown."""
        width = max(300, self.parent().width() // 2 if self.parent() else 300)
        height = min(250, (self.list_widget.count() * 36) + 60)  # Reduced from 350 to 250
        return QSize(width, height) 