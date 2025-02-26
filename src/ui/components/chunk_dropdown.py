from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLineEdit, 
                             QListView, QWidget, QTextEdit)
from PyQt6.QtCore import (Qt, QPoint, pyqtSignal, QSize, 
                          QStringListModel)
from PyQt6.QtGui import QFont
from typing import List


class ChunkDropdown(QFrame):
    """Custom dropdown with search for chunk selection."""
    itemSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Create search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search chunks...")
        self.search_box.textChanged.connect(self._filter_items)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #363636;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 8px;
                color: white;
                font-size: 12px;
                selection-background-color: #2b5c99;
            }
            QLineEdit:focus {
                border: 1px solid #4a9eff;
                background-color: #404040;
            }
        """)
        layout.addWidget(self.search_box)
        
        # Create list view
        self.list_view = QListView()
        self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_view.clicked.connect(self._handle_click)
        self.list_view.activated.connect(self._handle_click)
        
        # Setup model
        self.model = QStringListModel()
        self.list_view.setModel(self.model)
        self.all_items = []  # Store all items for filtering
        
        # Style the list view
        self.list_view.setStyleSheet("""
            QListView {
                background-color: transparent;
                border: none;
                outline: none;
                padding: 4px 0px;
            }
            QListView::item {
                padding: 6px 8px;
                border-radius: 4px;
                color: white;
                margin: 2px 0px;
            }
            QListView::item:selected {
                background-color: #2b5c99;
                color: white;
            }
            QListView::item:hover:!selected {
                background-color: #404040;
            }
            QScrollBar:vertical {
                border: none;
                background: #363636;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #505050;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #606060;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        layout.addWidget(self.list_view)
        
        # Set frame style
        self.setStyleSheet("""
            ChunkDropdown {
                background-color: #2b2b2b;
                border: 1px solid #3f3f3f;
                border-radius: 6px;
            }
        """)

    def update_items(self, items: List[str]):
        """Update the list of available items."""
        self.all_items = items
        self.model.setStringList(items)
        if self.model.rowCount() > 0:
            self.list_view.setCurrentIndex(self.model.index(0, 0))
        self.search_box.clear()
        self.search_box.setFocus()

    def _filter_items(self):
        """Filter items based on search text."""
        search_text = self.search_box.text().lower()
        filtered_items = [item for item in self.all_items if search_text in item.lower()]
        self.model.setStringList(filtered_items)
        if self.model.rowCount() > 0:
            self.list_view.setCurrentIndex(self.model.index(0, 0))

    def _handle_click(self, index):
        """Handle item click or activation."""
        if index.isValid():
            text = self.model.data(index, Qt.ItemDataRole.DisplayRole)
            self.itemSelected.emit(text)
            self.hide()

    def keyPressEvent(self, event):
        """Handle key events."""
        if event.key() == Qt.Key.Key_Return and not event.modifiers():
            current = self.list_view.currentIndex()
            if current.isValid():
                text = self.model.data(current, Qt.ItemDataRole.DisplayRole)
                self.itemSelected.emit(text)
                self.hide()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Up:
            current_row = max(0, self.list_view.currentIndex().row() - 1)
            self.list_view.setCurrentIndex(self.model.index(current_row, 0))
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Down:
            current_row = min(self.model.rowCount() - 1, self.list_view.currentIndex().row() + 1)
            self.list_view.setCurrentIndex(self.model.index(current_row, 0))
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

    def sizeHint(self):
        """Calculate proper size for the dropdown."""
        width = max(300, self.parent().width() // 2 if self.parent() else 300)
        height = min(400, (self.model.rowCount() * 30) + 50)  # Extra height for search box
        return QSize(width, height) 