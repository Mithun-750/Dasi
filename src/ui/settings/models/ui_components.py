import logging
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QComboBox, QFrame, QVBoxLayout, QHBoxLayout,
    QProxyStyle, QStyle, QLineEdit, QScrollArea, QListWidget, QStyledItemDelegate,
    QListWidgetItem
)
from PyQt6.QtCore import (
    Qt, QRectF, QObject, QSize
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPen, QPainterPath
)


class RoundLabel(QLabel):
    """Custom label with rounded corners using QPainter."""

    def __init__(self, text, parent=None, radius=12):
        super().__init__(text, parent)
        self.radius = radius
        # Set colors for the label - using orange theme
        # Light orange background with ~10% opacity
        self.bg_color = QColor(230, 126, 34, 25)
        self.text_color = QColor(230, 126, 34)  # Orange text (#e67e22)
        # Set fixed height for consistent look
        self.setFixedHeight(24)
        # Set content margins to create padding
        self.setContentsMargins(12, 4, 12, 4)
        # Set font size
        font = self.font()
        font.setPointSize(9)  # Same as the original 12px
        self.setFont(font)
        # Calculate width based on text + padding
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        self.setMinimumWidth(text_width + 24)  # 12px padding on each side

    def sizeHint(self):
        size = super().sizeHint()
        size.setHeight(24)
        return size

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # Create the path for the rounded rectangle
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, self.width(), self.height()),
                                self.radius, self.radius)

            # Set the clipping path
            painter.setClipPath(path)

            # Fill background
            painter.fillRect(self.rect(), self.bg_color)

            # Draw text - use the font we set in the constructor
            painter.setPen(self.text_color)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        finally:
            painter.end()


class RoundButton(QPushButton):
    """Custom button with rounded corners using QPainter."""

    def __init__(self, text, parent=None, radius=14):
        super().__init__(text, parent)
        self.radius = radius
        self.hover = False
        # Store colors as QColor objects
        self.border_color = QColor(230, 126, 34, 76)  # ~30% opacity
        self.hover_border_color = QColor(230, 126, 34, 102)  # ~40% opacity
        self.hover_bg_color = QColor(230, 126, 34, 25)  # ~10% opacity
        self.text_color = QColor(230, 126, 34)  # #e67e22

    def enterEvent(self, event):
        self.hover = True
        self.update()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover = False
        self.update()
        return super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # Create the path for the perfect circle
            path = QPainterPath()
            path.addEllipse(QRectF(1, 1, self.width()-2, self.height()-2))

            # Set the clipping path
            painter.setClipPath(path)

            # Draw the background
            if self.hover:
                # Hover state
                painter.fillRect(self.rect(), self.hover_bg_color)
            else:
                # Normal state
                painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

            # Draw the border
            painter.setPen(
                self.hover_border_color if self.hover else self.border_color)
            painter.drawEllipse(1, 1, self.width()-2, self.height()-2)

            # Draw the text centered
            painter.setPen(self.text_color)
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        finally:
            # Make sure painter is ended properly
            painter.end()


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


class SearchableComboBox(QComboBox):
    """Custom ComboBox with search functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Apply custom arrow style
        self.setStyle(ComboBoxStyle())

        # Apply orange-themed style
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                background-color: #222222;
                padding: 4px 8px;
                min-height: 18px;
            }
            QComboBox:hover, QComboBox:focus {
                border: 1px solid #e67e22;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
        """)

        # Create search line edit
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search models...")
        self.search_edit.setProperty("class", "search-input")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QLineEdit:focus {
                border: 1px solid #e67e22;
            }
        """)

        # Create and setup the popup frame
        self.popup = QFrame(self)
        self.popup.setWindowFlags(Qt.WindowType.Popup)
        self.popup.setFrameStyle(QFrame.Shape.NoFrame)
        self.popup.setProperty("class", "card")
        self.popup.setStyleSheet("""
            QFrame {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)

        # Create scroll area for list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")
        self.scroll.setProperty("class", "global-scrollbar")

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
                background-color: #333333;
                border-left: 2px solid #e67e22;
            }
        """)
        self.list_widget.setProperty("class", "global-scrollbar")
        self.scroll.setWidget(self.list_widget)

        # Force scrollbar styling directly
        scrollbar = self.list_widget.verticalScrollBar()
        if scrollbar:
            scrollbar.setStyleSheet("""
                QScrollBar:vertical {
                    background-color: #1a1a1a !important;
                    width: 10px !important;
                    margin: 0px 0px 0px 8px !important;
                    border-radius: 5px !important;
                    border: none !important;
                }

                QScrollBar::handle:vertical {
                    background-color: #333333 !important;
                    min-height: 30px !important;
                    border-radius: 5px !important;
                    border: none !important;
                }

                QScrollBar::handle:vertical:hover {
                    background-color: #e67e22 !important;
                }

                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px !important;
                    border: none !important;
                    background: none !important;
                }

                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none !important;
                    border: none !important;
                }
            """)

        # Setup popup layout
        self.popup_layout = QVBoxLayout(self.popup)
        self.popup_layout.setContentsMargins(8, 8, 8, 8)
        self.popup_layout.setSpacing(8)
        self.popup_layout.addWidget(self.search_edit)
        self.popup_layout.addWidget(self.scroll)

        # Connect signals
        self.search_edit.textChanged.connect(self.filter_items)
        self.list_widget.itemClicked.connect(self.on_item_clicked)

        # Set item delegate for custom item height
        self.list_widget.setItemDelegate(QStyledItemDelegate())

    def showPopup(self):
        """Show custom popup."""
        # Position popup below the combobox
        pos = self.mapToGlobal(self.rect().bottomLeft())
        # Fixed height of 300px
        self.popup.setGeometry(pos.x(), pos.y(), self.width(), 300)

        # Clear and repopulate list widget
        self.list_widget.clear()
        for i in range(self.count()):
            item = QListWidgetItem(self.itemText(i))
            # Transfer item data including tooltip
            tooltip = self.itemData(i, 3)  # 3 is ToolTipRole
            if tooltip:
                item.setToolTip(tooltip)
            # Transfer user data
            item.setData(Qt.ItemDataRole.UserRole,
                         self.itemData(i, Qt.ItemDataRole.UserRole))
            self.list_widget.addItem(item)

        self.popup.show()
        self.search_edit.setFocus()
        self.search_edit.clear()

    def hidePopup(self):
        """Hide custom popup."""
        self.popup.hide()
        super().hidePopup()

    def filter_items(self, text):
        """Filter items based on search text."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_item_clicked(self, item):
        """Handle item selection."""
        self.setCurrentText(item.text())
        self.hidePopup()
