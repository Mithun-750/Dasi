# Shared custom widgets for the settings UI

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QComboBox, QScrollArea, QListWidget,
    QListWidgetItem, QProxyStyle, QStyle
)
from PyQt6.QtCore import Qt, QEvent, QSize, QPoint, QRect, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QColor, QPainter, QPen, QPainterPath


# ComboBoxStyle for proper arrow display
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

    def __init__(self, parent=None, max_visible_items=10, popup_width=None):
        super().__init__(parent)

        # Store configuration
        self.max_visible_items = max_visible_items
        # Base item height including padding (Reduced from 36)
        self.item_height = 32
        self.custom_popup_width = popup_width  # Store custom width if provided

        # Apply custom arrow
        self.setStyle(ComboBoxStyle())

        # Force combobox-popup:0 to enable explicit control
        self.setStyleSheet("QComboBox { combobox-popup: 0; }")

        # Create popup frame
        self.popup_frame = QFrame(self.window())
        self.popup_frame.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.popup_frame.setProperty("class", "popup-frame")
        # Default styling - can be overridden by specific instances
        self.popup_frame.setStyleSheet("""
            QFrame.popup-frame {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)

        # Create scrollable list area
        self.scroll_area = QScrollArea(self.popup_frame)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)

        # Always hide horizontal scrollbar
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Use stronger styling to make scrollbar clearly visible
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #e67e22;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        # Create inner container for list items
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins
        self.list_layout.setSpacing(1)  # Reduced spacing

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setProperty("class", "popup-list")

        # Always hide horizontal scrollbar in list widget too
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Default list widget styling - can be overridden
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 6px; /* Reduced padding */
                border-radius: 4px;
                color: #e0e0e0;
                margin: 1px;
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

        # Connect list widget signals
        self.list_widget.itemClicked.connect(self._handle_item_selected)

        # Set up layout hierarchy
        self.list_layout.addWidget(self.list_widget)
        self.scroll_area.setWidget(self.list_container)

        # Set up popup layout
        self.popup_layout = QVBoxLayout(self.popup_frame)
        self.popup_layout.setContentsMargins(0, 0, 0, 0)
        self.popup_layout.setSpacing(0)
        self.popup_layout.addWidget(self.scroll_area)

        # Add animation
        self.animation = QPropertyAnimation(self.popup_frame, b"geometry")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.animation.setDuration(200)

        # Track popup state
        self.popup_visible = False

    def set_max_visible_items(self, count):
        """Set the maximum number of visible items in the dropdown."""
        self.max_visible_items = count

    def showPopup(self):
        """Show custom popup instead of standard dropdown."""
        if self.count() == 0 or not self.isEnabled():
            return

        # Calculate popup width and position
        if self.custom_popup_width:
            # Use custom width if specified
            popup_width = self.custom_popup_width
        else:
            # Default calculation
            popup_width = max(self.width(), 240)

        pos = self.mapToGlobal(QPoint(0, self.height()))

        # Calculate popup height based on item count
        total_items = min(self.count(), self.max_visible_items)

        # Calculate item heights with padding and spacing
        item_total_height = total_items * self.item_height
        popup_height = item_total_height + 8  # Add small margin

        # Determine if scrollbar is needed and set policy on SCROLL AREA
        if self.count() <= self.max_visible_items:
            # No need for vertical scrollbar if all items fit
            self.scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            # Show vertical scrollbar when we have more items than max_visible_items
            self.scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            # Explicitly show the scrollbar
            self.scroll_area.verticalScrollBar().show()

        # Ensure no horizontal scrollbar in both scroll area and list widget
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # For the list widget, we let the scroll area handle vertical scrolling
        self.list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Populate list widget
        self.list_widget.clear()
        for i in range(self.count()):
            item = QListWidgetItem(self.itemText(i))
            if self.itemData(i) is not None:
                item.setData(Qt.ItemDataRole.UserRole, self.itemData(i))
            self.list_widget.addItem(item)

        # Set current item
        if self.currentIndex() >= 0:
            self.list_widget.setCurrentRow(self.currentIndex())

        # Ensure the list widget has the correct size
        if self.count() > self.max_visible_items:
            # Make the list widget extend to show all items (scroll area will handle scrolling)
            self.list_widget.setMinimumHeight(self.count() * self.item_height)

        # Set up animation
        start_rect = QRect(pos.x(), pos.y(), popup_width, 0)
        end_rect = QRect(pos.x(), pos.y(), popup_width, popup_height)

        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)

        # Show popup
        self.popup_frame.setGeometry(start_rect)
        self.popup_frame.show()
        self.animation.start()

        # Update state
        self.popup_visible = True

        # Install event filter
        self.window().installEventFilter(self)

    def hidePopup(self):
        """Hide the custom popup."""
        if not self.popup_visible:
            return

        # Set up closing animation
        current_rect = self.popup_frame.geometry()
        end_rect = QRect(current_rect.x(), current_rect.y(),
                         current_rect.width(), 0)

        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(end_rect)
        self.animation.finished.connect(self._finish_hiding)
        self.animation.start()

        # Update state
        self.popup_visible = False

        # Remove event filter
        self.window().removeEventFilter(self)

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
