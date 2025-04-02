from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QFrame, QLabel,
                             QPushButton, QHBoxLayout, QProgressBar, QGridLayout,
                             QComboBox, QSizePolicy, QRadioButton, QButtonGroup,
                             QScrollArea, QListWidget, QListWidgetItem, QStyledItemDelegate,
                             QLineEdit, QProxyStyle, QStyle, QStackedWidget, QApplication)
from PyQt6.QtCore import (Qt, pyqtSignal, QStringListModel, QEvent, QSize, QPoint,
                          QRect, QEasingCurve, QPropertyAnimation, QMimeData, QBuffer)
from PyQt6.QtGui import (QFont, QCursor, QColor, QPainter, QPen, QPainterPath,
                         QClipboard, QTextCursor, QImage, QPixmap, QDrag, QDragEnterEvent, QDropEvent)
from typing import Callable, Optional, Dict, Any, List
from pathlib import Path
import logging
import re
import json
import os
import base64

from ...settings import Settings
from ...components.chunk_dropdown import ChunkDropdown
from ...components.mention_highlighter import MentionHighlighter


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
        self.item_height = 36  # Base item height including padding
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
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setSpacing(2)

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setProperty("class", "popup-list")

        # Always hide horizontal scrollbar in list widget too
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


# Custom QTextEdit that pastes plain text only and accepts image drops
class PlainTextEdit(QTextEdit):
    """A QTextEdit that ignores formatting when pasting text and supports image drops."""

    image_pasted = pyqtSignal(QImage)
    image_dropped = pyqtSignal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def insertFromMimeData(self, source):
        """Override to insert plain text only."""
        if source.hasImage():
            image = QImage(source.imageData())
            self.image_pasted.emit(image)
        elif source.hasText():
            self.insertPlainText(source.text())

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events for images and text."""
        mime_data = event.mimeData()
        if mime_data.hasImage() or mime_data.hasUrls() or mime_data.hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        """Handle drop events for images and text."""
        mime_data = event.mimeData()

        # First check for direct image data
        if mime_data.hasImage():
            image = QImage(mime_data.imageData())
            self.image_dropped.emit(image)
            event.acceptProposedAction()
            return

        # Then check for image files in URLs
        elif mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image = QImage(file_path)
                        if not image.isNull():
                            self.image_dropped.emit(image)
                            event.acceptProposedAction()
                            return

        # Finally fall back to standard text handling
        super().dropEvent(event)


class InputPanel(QWidget):
    """Input panel component for the Dasi window."""

    # Signals
    submit_query = pyqtSignal(str)  # Signal emitted when user submits a query
    # Signal emitted when mode changes (True for compose)
    mode_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize properties
        self.settings = Settings()
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'
        self.selected_text = None  # Store selected text
        self.chunk_dropdown = None  # Will be initialized later
        self.highlighter = None  # Initialize highlighter reference
        self.is_web_search = False  # Flag to track if current query is a web search
        self.image_data = None  # Store image data in base64
        self.image = None       # Store the QImage object

        # Initialize command history
        self.history_file = Path(
            self.settings.config_dir) / 'input_history.json'
        self.history = []
        self.history_position = -1
        self.current_input = ""
        self.max_history = 500  # Maximum number of history entries
        self._load_history()

        # Set minimum width for consistent UI
        self.setMinimumWidth(310)

        # Setup UI
        self._setup_ui()

        # Add syntax highlighter with chunks directory
        # This highlighter also handles #web and URL# patterns
        self.highlighter = MentionHighlighter(
            self.input_field.document(), self.chunks_dir)

        # Setup chunk dropdown
        self._setup_chunk_dropdown()

        # Connect to settings signals - add logging to track this connection
        logging.info(
            "InputPanel: Connecting to settings.models_changed signal")
        self.settings.models_changed.connect(self.update_model_selector)
        logging.info("InputPanel: Signal connected")

    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Context area with label and ignore button
        self.context_frame = QFrame()
        self.context_frame.setObjectName("contextFrame")
        context_layout = QVBoxLayout()
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(0)
        self.context_frame.setLayout(context_layout)

        # Set size policy and maximum height for the frame
        self.context_frame.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        # Set max height for the whole frame
        self.context_frame.setMaximumHeight(50)

        # Create container for the context area
        container = QWidget()
        container.setProperty("class", "transparent-container")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # Add image label for displaying pasted/dropped images
        self.image_label = QLabel()
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Adjusted minimum height further
        self.image_label.setMinimumHeight(30)
        self.image_label.setMaximumHeight(50)  # Reduced maximum height to 50px
        self.image_label.hide()

        # Add ignore button
        self.ignore_button = QPushButton("×")
        self.ignore_button.setObjectName("ignoreButton")
        self.ignore_button.setFixedSize(16, 16)
        self.ignore_button.clicked.connect(self.reset_context)
        self.ignore_button.hide()

        # Add widgets to the grid - context_label removed
        # grid.addWidget(self.context_label, 0, 0) # Removed context_label
        # Image label now takes the first row
        grid.addWidget(self.image_label, 0, 0)
        grid.addWidget(self.ignore_button, 0, 0,
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        # Ensure ignore button stays on top
        # self.context_label.stackUnder(self.ignore_button) # No longer needed

        context_layout.addWidget(container)
        layout.addWidget(self.context_frame)

        # Hide the context frame initially
        self.context_frame.hide()

        # Override show/hide to handle button visibility and position
        def show_context():
            # Show both widgets
            super(type(self.image_label), self.image_label).show()
            self.ignore_button.show()
            self.ignore_button.raise_()

        def hide_context():
            super(type(self.image_label), self.image_label).hide()
            self.ignore_button.hide()

        self.image_label.show = show_context
        self.image_label.hide = hide_context

        # Input field - Use PlainTextEdit instead of QTextEdit to prevent formatting on paste
        self.input_field = PlainTextEdit()
        self.input_field.setObjectName("inputField")
        self.input_field.setProperty("class", "input-field")
        self.input_field.setPlaceholderText(
            "Type your query... (@chunks, #web, and #URL/URL# will be highlighted). Paste/drop images for multimodal.")
        self.input_field.setMinimumHeight(80)

        # Connect image paste/drop signals
        self.input_field.image_pasted.connect(self.handle_image_paste)
        self.input_field.image_dropped.connect(self.handle_image_drop)

        # Set up key bindings
        self.input_field.installEventFilter(self)

        # Create container for selectors (mode and model)
        selectors_container = QWidget()
        selectors_container.setProperty("class", "transparent-container")
        selectors_layout = QHBoxLayout(selectors_container)
        selectors_layout.setContentsMargins(0, 0, 0, 0)
        selectors_layout.setSpacing(8)

        # Create mode selector dropdown - use narrower popup width
        self.mode_selector = CustomComboBox(
            max_visible_items=2, popup_width=120)
        self.mode_selector.setProperty("class", "combo-box")
        self.mode_selector.addItem("Chat")
        self.mode_selector.addItem("Compose")
        # Fixed width for consistent layout
        self.mode_selector.setFixedWidth(100)
        self.mode_selector.activated.connect(self._handle_mode_change)

        # Create model selector dropdown - use default popup width
        self.model_selector = CustomComboBox(max_visible_items=4)
        self.model_selector.setProperty("class", "combo-box")
        self.update_model_selector()

        # Add both selectors to layout
        selectors_layout.addWidget(self.mode_selector)
        selectors_layout.addWidget(self.model_selector)

        # Loading progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.hide()

        layout.addWidget(self.input_field, 1)
        layout.addWidget(selectors_container)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

        # Apply styling
        self.setStyleSheet("""
            QWidget.transparent-container {
                background-color: transparent;
            }
            
            #imageLabel {
                background-color: #222222;
                border-radius: 6px;
                padding: 4px; /* Reduced padding */
                /* margin-top: 8px; */ /* Removed top margin */
            }
            
            #ignoreButton {
                background-color: #333333;
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
                background-color: #444444;
                color: #ffffff;
            }
            
            .input-field, #inputField {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 6px;
                selection-background-color: #3b82f6;
                selection-color: white;
            }
            
            .mode-container {
                background-color: #222222;
                border-radius: 6px;
                padding: 2px;
            }
            
            .segment-button {
                color: #cccccc;
                font-size: 12px;
                font-weight: medium;
                padding: 6px 12px;
                border-radius: 4px;
                background-color: transparent;
                border: none;
                text-align: center;
            }
            
            .segment-button:hover {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            
            .segment-button.active {
                color: white;
                background-color: #e67e22;
                font-weight: bold;
            }
            
            .combo-box {
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 4px;
                padding: 6px 8px;
                color: #e0e0e0;
                min-height: 18px;
            }
            
            .combo-box:hover {
                border-color: #e67e22;
                background-color: #323232;
            }
            
            .combo-box:focus {
                border: 1px solid #e67e22;
            }
            
            .combo-box::drop-down {
                border: none;
                width: 20px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
                padding-right: 8px;
            }
            
            #progressBar {
                border: none;
                background-color: #2a2a2a;
                border-radius: 1px;
                height: 2px;
            }
            
            #progressBar::chunk {
                background-color: #e67e22;
            }
        """)

    def reset_context(self):
        """Reset all context including selected text and image."""
        self.selected_text = None
        self.image_data = None
        self.image = None
        self.image_label.hide()
        self.ignore_button.hide()
        self.context_frame.hide()  # Also hide the frame

    def set_selected_text(self, text: str):
        """Set the selected text and update UI."""
        self.selected_text = text
        if text:
            self.context_frame.show()  # Show frame when there's text
            self.image_label.show()
            self.ignore_button.show()
        else:
            # Only hide context label and frame if no image is present
            self.image_label.hide()
            if not self.image_data:
                self.ignore_button.hide()
                self.context_frame.hide()  # Hide frame when empty
            self.selected_text = None

    def handle_image_paste(self, image: QImage):
        """Handle pasted image from clipboard."""
        self._process_image(image)

    def handle_image_drop(self, image: QImage):
        """Handle dropped image."""
        self._process_image(image)

    def _process_image(self, image: QImage):
        """Process and display an image."""
        if image.isNull():
            logging.error("Received null image")
            return

        # Store the image
        self.image = image

        # Convert image to base64
        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.ReadWrite)
        image.save(buffer, "PNG")
        image_data = buffer.data().data()
        self.image_data = base64.b64encode(image_data).decode('utf-8')

        # Resize image for display (maintaining aspect ratio) using the new max height
        scaled_image = image.scaled(300, 50, Qt.AspectRatioMode.KeepAspectRatio,  # Use new max height (50px)
                                    Qt.TransformationMode.SmoothTransformation)

        # Display image
        self.image_label.setPixmap(QPixmap.fromImage(scaled_image))
        self.image_label.show()

        # Show context frame and ignore button
        self.context_frame.show()
        self.ignore_button.show()

        # Removed the check and warning for vision model
        # vision_model = self.settings.get('models', 'vision_model')
        # if not vision_model:
        #     self.context_label.setText(
        #         "Warning: No vision model selected in settings! Image will be ignored.")
        #     self.context_label.show()

    def eventFilter(self, obj, event):
        """Handle key events."""
        if obj is self.input_field and event.type() == QEvent.Type.KeyPress:
            key_event = event

            # History navigation with up/down arrow keys
            if key_event.key() == Qt.Key.Key_Up:
                # Alt+Up to cycle to previous model
                if key_event.modifiers() & Qt.KeyboardModifier.AltModifier:
                    current_index = self.model_selector.currentIndex()
                    if current_index > 0:
                        self.model_selector.setCurrentIndex(current_index - 1)
                    else:
                        # Wrap around to the last item
                        self.model_selector.setCurrentIndex(
                            self.model_selector.count() - 1)
                    return True

                # If dropdown is visible, let it handle navigation
                if self.chunk_dropdown.isVisible():
                    return False

                # Get current text for searching
                current_text = self.input_field.toPlainText()

                # Save the current input before navigating history
                if self.history_position == -1:
                    self.current_input = current_text

                # Navigate history backwards (older entries)
                if len(self.history) > 0:
                    # Search mode - find items starting with current input (not current display text)
                    search_text = self.current_input if self.history_position != -1 else current_text

                    # Start searching from next position
                    start_pos = self.history_position + 1 if self.history_position != -1 else 0

                    # Don't search beyond the history length
                    if start_pos < len(self.history):
                        found = False
                        # Loop through history entries from newest to oldest
                        for i in range(start_pos, len(self.history)):
                            if self.history[len(self.history) - 1 - i].startswith(search_text):
                                self.history_position = i
                                self._set_input_text(
                                    self.history[len(self.history) - 1 - i])
                                found = True
                                break

                        if not found and start_pos > 0:
                            # No more matches, stay at current position
                            pass

                return True

            elif key_event.key() == Qt.Key.Key_Down:
                # Alt+Down to cycle to next model
                if key_event.modifiers() & Qt.KeyboardModifier.AltModifier:
                    current_index = self.model_selector.currentIndex()
                    if current_index < self.model_selector.count() - 1:
                        self.model_selector.setCurrentIndex(current_index + 1)
                    else:
                        # Wrap around to the first item
                        self.model_selector.setCurrentIndex(0)
                    return True

                # If dropdown is visible, let it handle navigation
                if self.chunk_dropdown.isVisible():
                    return False

                # Only navigate down if we're in history
                if self.history_position == -1:
                    return False

                # Navigate history forwards (newer entries)
                search_text = self.current_input

                if self.history_position > 0:
                    # Try to find a matching entry in a newer position
                    found = False
                    # Loop from current position toward newer entries
                    for i in range(self.history_position - 1, -1, -1):
                        if self.history[len(self.history) - 1 - i].startswith(search_text):
                            self.history_position = i
                            self._set_input_text(
                                self.history[len(self.history) - 1 - i])
                            found = True
                            break

                    if not found:
                        # Return to original input if no more matches
                        self.history_position = -1
                        self._set_input_text(self.current_input)
                else:
                    # Already at newest history entry, return to original input
                    self.history_position = -1
                    self._set_input_text(self.current_input)

                return True

            # Alt+Left/Right to cycle through modes
            elif key_event.key() == Qt.Key.Key_Left and key_event.modifiers() & Qt.KeyboardModifier.AltModifier:
                # Cycle to previous mode
                current_index = self.mode_selector.currentIndex()
                if current_index > 0:
                    self.mode_selector.setCurrentIndex(current_index - 1)
                else:
                    # Wrap around to the last item
                    self.mode_selector.setCurrentIndex(
                        self.mode_selector.count() - 1)
                self._handle_mode_change(self.mode_selector.currentIndex())
                return True

            elif key_event.key() == Qt.Key.Key_Right and key_event.modifiers() & Qt.KeyboardModifier.AltModifier:
                # Cycle to next mode
                current_index = self.mode_selector.currentIndex()
                if current_index < self.mode_selector.count() - 1:
                    self.mode_selector.setCurrentIndex(current_index + 1)
                else:
                    # Wrap around to the first item
                    self.mode_selector.setCurrentIndex(0)
                self._handle_mode_change(self.mode_selector.currentIndex())
                return True

            # Show dropdown on @ key only when properly spaced
            if key_event.text() == '@':
                # Get the text and cursor position
                cursor = self.input_field.textCursor()
                text = self.input_field.toPlainText()
                pos = cursor.position()

                # Check if @ is at the beginning or has a space before it
                is_start_or_after_space = pos == 0 or (
                    pos > 0 and text[pos-1] in [' ', '\n', '\t'])

                if is_start_or_after_space:
                    self.chunk_dropdown.update_items(self.chunk_titles)
                    self.chunk_dropdown.show()

                return False  # Let the @ be typed

            # Handle Shift+Backspace to clear selected text
            if (key_event.key() == Qt.Key.Key_Backspace and
                    key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.reset_context()
                return True  # Event handled

            # Handle submit when dropdown is not visible
            if (key_event.key() == Qt.Key.Key_Return and
                not key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier and
                    not self.chunk_dropdown.isVisible()):
                self._handle_submit()
                return True

            # Reset history position when typing
            if key_event.key() != Qt.Key.Key_Up and key_event.key() != Qt.Key.Key_Down:
                self.history_position = -1

            # Add special handling for Ctrl+V to check clipboard for images
            if (obj is self.input_field and event.type() == QEvent.Type.KeyPress and
                    key_event.key() == Qt.Key.Key_V and
                    key_event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                clipboard = QApplication.clipboard()
                mime_data = clipboard.mimeData()

                if mime_data.hasImage():
                    image = QImage(mime_data.imageData())
                    if not image.isNull():
                        self.handle_image_paste(image)
                        return False  # Still allow the standard paste event for any text

            return False  # Let all other keys through

        return super().eventFilter(obj, event)

    def _setup_chunk_dropdown(self):
        """Set up the chunk selection dropdown."""
        self.chunk_dropdown = ChunkDropdown(self.input_field)
        self.chunk_dropdown.itemSelected.connect(self.insert_chunk)
        self.update_chunk_titles()

    def update_chunk_titles(self):
        """Update the list of available chunk titles."""
        self.chunk_titles = []
        if self.chunks_dir.exists():
            for file_path in self.chunks_dir.glob("*.md"):
                title = file_path.stem
                self.chunk_titles.append(title)

        # Update highlighter's available chunks
        if self.highlighter:
            self.highlighter.update_available_chunks()

    def insert_chunk(self, chunk_title: str):
        """Insert the selected chunk title at cursor position."""
        from PyQt6.QtGui import QTextCursor

        cursor = self.input_field.textCursor()
        current_word, start = self.get_word_under_cursor()

        # Calculate how many characters to remove
        extra = len(current_word)

        # Move cursor to start of the word and select it
        cursor.movePosition(QTextCursor.MoveOperation.Left,
                            QTextCursor.MoveMode.MoveAnchor, extra)
        cursor.movePosition(QTextCursor.MoveOperation.Right,
                            QTextCursor.MoveMode.KeepAnchor, extra)

        # Insert chunk title with @ prefix and a space
        cursor.insertText('@' + chunk_title.lower() + ' ')
        self.input_field.setTextCursor(cursor)
        self.chunk_dropdown.hide()

    def get_word_under_cursor(self):
        """Get the word being typed and its start position."""
        cursor = self.input_field.textCursor()
        text = self.input_field.toPlainText()
        pos = cursor.position()

        # Find the start of the current word
        start = pos
        while start > 0 and text[start-1] not in [' ', '\n', '\t']:
            start -= 1

        # Only get the word up to the first space after @
        current_word = text[start:pos]
        if ' ' in current_word and current_word.startswith('@'):
            return '@', start  # Return just the @ if we hit a space

        return current_word, start

    def update_model_selector(self):
        """Update the model selector with currently selected models."""
        # Log that this method was called
        logging.info("InputPanel: Updating model selector")

        # Reload settings from disk
        self.settings.load_settings()

        self.model_selector.clear()
        selected_models = self.settings.get_selected_models()

        # Log the current models
        logging.info(f"InputPanel: Found {len(selected_models)} models")

        if not selected_models:
            self.model_selector.addItem("No models selected")
            self.model_selector.setEnabled(False)
            return

        # Get default model ID
        default_model_id = self.settings.get('models', 'default_model')
        default_index = 0  # Default to first model if no default set

        # Add models with their metadata
        for index, model in enumerate(selected_models):
            # Create a more concise display text
            provider = model['provider']
            name = model['name']

            # Format provider name to be more concise
            provider_display = {
                'google': 'Google',
                'openai': 'OpenAI',
                'anthropic': 'Anthropic',
                'ollama': 'Ollama',
                'groq': 'Groq',
                'deepseek': 'Deepseek',
                'together': 'Together',
                'openrouter': 'OpenRouter',
                'custom_openai': 'Custom'
            }.get(provider, provider)

            # Create shorter display text for combobox
            display_text = f"{name[:30]}... ({provider_display})" if len(
                name) > 30 else f"{name} ({provider_display})"

            # Full text for tooltip
            full_text = f"{name}\nProvider: {provider_display}"

            self.model_selector.addItem(display_text, model)
            # Set tooltip for the current index
            self.model_selector.setItemData(
                index, full_text, Qt.ItemDataRole.ToolTipRole)

            # If this is the default model, store its index
            if default_model_id and model['id'] == default_model_id:
                default_index = index

        self.model_selector.setEnabled(True)

        # Set the default model as current
        self.model_selector.setCurrentIndex(default_index)

        # Configure size policy to expand horizontally
        self.model_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Log that the update is complete
        logging.info("InputPanel: Model selector updated successfully")

    def get_selected_model(self):
        """Get the currently selected model ID."""
        current_index = self.model_selector.currentIndex()
        if current_index >= 0:
            model_info = self.model_selector.itemData(current_index)
            if model_info and 'id' in model_info:
                return model_info
        return None

    def _handle_mode_change(self, index):
        """Handle mode change between Chat and Compose modes."""
        # Update mode based on selected index
        is_compose = index == 1  # 1 is "Compose", 0 is "Chat"

        # Emit signal to inform parent
        self.mode_changed.emit(is_compose)

    def is_compose_mode(self):
        """Check if compose mode is active."""
        return self.mode_selector.currentIndex() == 1

    def enable_input(self, enabled=True):
        """Enable or disable the input field."""
        self.input_field.setEnabled(enabled)

    def set_focus(self):
        """Set focus to the input field."""
        self.input_field.setFocus()

    def show_progress(self, show=True):
        """Show or hide the progress bar."""
        if show:
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.progress_bar.show()
        else:
            self.progress_bar.hide()

    def get_query(self):
        """Get the current query text."""
        return self.input_field.toPlainText().strip()

    def clear_input(self):
        """Clear the input field and context (including image)."""
        self.input_field.clear()
        self.reset_context()

    def _handle_submit(self):
        """Handle submit action."""
        query = self.get_query()
        if query:
            # Add to history
            self._add_to_history(query)

            # Replace @mentions with chunk content
            query = self._replace_chunks(query)

            # Check if this is a web search query
            self.is_web_search = "#web" in query.lower()

            # Check if this is a link scrape query using our detection method
            self.is_link_scrape, self.link_to_scrape = self._detect_link_scrape(
                query)

            # If link scrape is detected, modify the query to make it clearer
            if self.is_link_scrape and self.link_to_scrape:
                # Log the detection
                logging.info(f"Link scrape detected: {self.link_to_scrape}")

                # Remove the # from the query if it's at the beginning of the URL
                query = query.replace(
                    f"#{self.link_to_scrape}", self.link_to_scrape, 1)
                # Remove the # from the query if it's at the end of the URL
                query = query.replace(
                    f"{self.link_to_scrape}#", self.link_to_scrape, 1)

            # Extract actual web search query if this is a web search
            if self.is_web_search:
                # Keep the original query format for submission, but make a note of the actual search content
                # The actual extraction happens in LLMHandler
                logging.info(f"Web search query detected: {query}")

            # Show loading state
            self.enable_input(False)
            self.show_progress(True)

            # Emit signal with query
            self.submit_query.emit(query)

    def _add_to_history(self, query: str):
        """Add a query to the history."""
        # Don't add empty queries or duplicates of the most recent entry
        if not query or (self.history and self.history[-1] == query):
            return

        # Add to history
        self.history.append(query)

        # Trim history if it exceeds max size
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        # Reset history position
        self.history_position = -1

        # Save history to file
        self._save_history()

    def _load_history(self):
        """Load command history from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
                    # Ensure we don't exceed max history
                    self.history = self.history[-self.max_history:]
        except Exception as e:
            logging.error(f"Error loading history: {e}")
            self.history = []

    def _save_history(self):
        """Save command history to file."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.history_file.parent, exist_ok=True)

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({'history': self.history}, f,
                          ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error saving history: {e}")

    def _set_input_text(self, text: str):
        """Set input text and move cursor to end."""
        self.input_field.setPlainText(text)
        cursor = self.input_field.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.input_field.setTextCursor(cursor)

    def _replace_chunks(self, query: str) -> str:
        """Replace @mentions with their corresponding chunk content."""
        # Find all @mentions
        mentions = re.finditer(r'@(\w+(?:_\w+)*)', query)

        # Replace each mention with its chunk content
        offset = 0
        for match in mentions:
            chunk_title = match.group(1)  # Get the title without @
            sanitized_title = chunk_title.lower()  # Convert to lowercase for filename
            chunk_file = self.chunks_dir / f"{sanitized_title}.md"

            if chunk_file.exists():
                chunk_content = chunk_file.read_text().strip()
                start = match.start() + offset
                end = match.end() + offset
                query = query[:start] + chunk_content + query[end:]
                offset += len(chunk_content) - (end - start)

        return query

    def get_context(self):
        """Get the current context as a dictionary."""
        context = {}
        if self.selected_text:
            context['selected_text'] = self.selected_text

        # Include image data if available
        if self.image_data:
            context['image_data'] = self.image_data

        # Always include mode information
        context['mode'] = 'compose' if self.is_compose_mode() else 'chat'

        # Include link scrape info if available
        if self.is_link_scrape and self.link_to_scrape:
            context['is_link_scrape'] = True
            context['link_to_scrape'] = self.link_to_scrape

        return context

    def _detect_link_scrape(self, text):
        """Detect if the text contains a URL followed by # for link scraping.

        Args:
            text: The text to check

        Returns:
            Tuple (is_link_scrape, link_to_scrape) where link_to_scrape is None if is_link_scrape is False
        """
        import re
        # Match URL followed by # (original pattern)
        url_pattern_after = r'(https?://[^\s]+)#'
        # Match # followed by URL (new pattern)
        url_pattern_before = r'#(https?://[^\s]+)'

        # Check for URL followed by #
        url_match = re.search(url_pattern_after, text)
        if url_match:
            return True, url_match.group(1)

        # Check for # followed by URL
        url_match = re.search(url_pattern_before, text)
        if url_match:
            return True, url_match.group(1)

        return False, None
