from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QComboBox, QSizePolicy, QFrame,
                             QProxyStyle, QStyle, QStyledItemDelegate, QStackedWidget, QCheckBox,
                             QScrollArea, QListWidget, QListWidgetItem, QMenu, QGridLayout, QToolButton)
from PyQt6.QtCore import Qt, pyqtSignal, QDir, QEvent, QSize, QPoint, QRect, QEasingCurve, QPropertyAnimation, QTimer
from PyQt6.QtGui import QTextCursor, QColor, QPen, QPainterPath, QPainter, QCursor, QIcon, QAction, QPixmap
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
        self.popup_frame.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
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
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: transparent;")

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setProperty("class", "popup-list")
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
        # Minimum width for better readability
        popup_width = max(self.width(), 260)

        # Calculate height based on number of items (limited by max_visible_items)
        items_height = min(
            self.count(), self.max_visible_items) * self.item_height
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
        end_rect = QRect(current_rect.x(), current_rect.y(),
                         current_rect.width(), 0)

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

# SplitButton: A button with a dropdown arrow using QToolButton


class SplitButton(QToolButton):
    """A button with a dropdown menu for selection options."""

    # Signal emitted when an option is selected from the dropdown
    option_selected = pyqtSignal(str, object)

    def __init__(self, text, parent=None):
        super().__init__(parent)

        # Store the checkmark icon path
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            self.checkmark_path = os.path.join(
                base_path, "assets", "icons", "checkmark.svg")
        else:
            app_dir = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            self.checkmark_path = os.path.join(
                app_dir, "ui", "assets", "icons", "checkmark.svg")

        # Set up basic properties
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        # Set fixed size to match dropdown height
        self.setFixedHeight(30)

        # Apply styling - simplified to the essential elements only
        self.setStyleSheet("""
            QToolButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 8px;
                min-height: 18px;
                max-height: 18px;
            }
            QToolButton:hover {
                background-color: #d35400;
            }
            QToolButton:pressed {
                background-color: #a04000;
            }
            QToolButton::menu-button {
                background-color: #e67e22;
                border-left: 1px solid rgba(0, 0, 0, 0.2);
                width: 16px;
            }
            QToolButton::menu-button:hover {
                background-color: #d35400;
            }
            QToolButton::menu-button:pressed {
                background-color: #a04000;
            }
            QToolButton::menu-arrow {
                image: none;
            }
        """)

        # Create the menu
        self.menu = QMenu()
        self.setMenu(self.menu)

        # Style the menu
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 8px;
                border-radius: 3px;
                color: #e0e0e0;
                margin: 2px;
                min-width: 150px;
            }
            QMenu::item:selected {
                background-color: #2e2e2e;
                border-left: 2px solid #e67e22;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333333;
                margin: 2px 5px;
            }
        """)

        # Track options and selected index
        self.options = []
        self.selected_index = 0

        # Connect the button click to use default selected option
        self.clicked.connect(self._on_main_button_clicked)

    def add_option(self, text, data=None):
        """Add an option to the dropdown menu."""
        self.options.append((text, data))
        self._rebuild_menu()

    def _rebuild_menu(self):
        """Rebuild the menu with current options and check marks."""
        self.menu.clear()

        for i, (text, data) in enumerate(self.options):
            action = QAction(text, self)
            action.setData(data)
            # Set checkmark for the selected option
            if i == self.selected_index:
                icon = QIcon(self.checkmark_path)
                action.setIcon(icon)

            # Connect action to selection handler
            action.triggered.connect(
                lambda checked=False, idx=i: self._handle_option_selected(idx))
            self.menu.addAction(action)

    def _on_main_button_clicked(self):
        """Handle main button click to use the currently selected option."""
        if self.options and 0 <= self.selected_index < len(self.options):
            text, data = self.options[self.selected_index]
            self.option_selected.emit(text, data)

    def _handle_option_selected(self, index):
        """Handle when an option is selected from the dropdown."""
        if 0 <= index < len(self.options):
            self.selected_index = index
            text, data = self.options[index]
            self.option_selected.emit(text, data)

    def get_selected_data(self):
        """Get the data for the currently selected option."""
        if self.options and 0 <= self.selected_index < len(self.options):
            return self.options[self.selected_index][1]
        return None

    def set_selected_index(self, index):
        """Set the selected index."""
        if 0 <= index < len(self.options):
            self.selected_index = index
            self._rebuild_menu()

    def set_selected_data(self, data):
        """Set the selected option by data value."""
        for i, (_, option_data) in enumerate(self.options):
            if option_data == data:
                self.selected_index = i
                self._rebuild_menu()
                break


class PreviewPanel(QWidget):
    """Preview panel component for the Dasi window."""

    # Signals
    # Emitted when use is clicked (method, response)
    use_clicked = pyqtSignal(str, str)
    # Emitted when export is clicked (response)
    export_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_chat_mode = False  # Default to compose mode
        self._user_edit_preference = True  # Track user's edit mode preference
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        # Get the checkmark path based on running mode
        if getattr(sys, 'frozen', False):
            # Running as bundled app
            base_path = sys._MEIPASS
            checkmark_path = os.path.join(
                base_path, "assets", "icons", "checkmark.svg")
        else:
            # Running in development
            app_dir = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            checkmark_path = os.path.join(
                app_dir, "ui", "assets", "icons", "checkmark.svg")

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create a stacked widget to hold both preview types
        self.preview_stack = QStackedWidget()
        # Keep fixed width for consistent UI
        self.preview_stack.setFixedWidth(330)
        self.preview_stack.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        # Plain text preview (for compose mode)
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)  # Start as read-only
        self.response_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
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
        self.preview_stack.addWidget(
            self.response_preview)  # Index 0: Plain text
        self.preview_stack.addWidget(
            self.markdown_preview)  # Index 1: Markdown

        # Create a container for the preview stack that allows positioning
        self.preview_container = QFrame()
        self.preview_container.setObjectName("preview_container")
        self.preview_container.setFixedWidth(330)
        self.preview_container.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        # Set up container layout
        container_layout = QVBoxLayout(self.preview_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self.preview_stack)

        # Create overlay for the edit button
        self.preview_overlay = QFrame(self.preview_container)
        self.preview_overlay.setObjectName("preview_overlay")
        self.preview_overlay.setGeometry(
            0, 0, self.preview_container.width(), self.preview_container.height())
        self.preview_overlay.setStyleSheet("background-color: transparent;")

        # Make the overlay transparent to mouse events
        self.preview_overlay.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Create empty layout for overlay
        overlay_layout = QVBoxLayout(self.preview_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)

        # Create edit button
        self.edit_button = QPushButton(self.preview_container)
        # Slightly larger for better touchability
        self.edit_button.setFixedSize(28, 28)
        self.edit_button.setCheckable(True)
        self.edit_button.setObjectName("edit_button")
        self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_button.setText("")  # Ensure no text is set
        self.edit_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                border: none;
                border-radius: 14px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:checked {
                background-color: #a04000;
            }
        """)

        # Create pen icon for the button
        pen_icon = self._create_pen_icon()
        self.edit_button.setIcon(pen_icon)
        # Smaller icon for cleaner appearance
        self.edit_button.setIconSize(QSize(14, 14))

        # Initially position the button (will be updated in update_button_position)
        self.edit_button.move(0, 0)

        # Connect button signals
        self.edit_button.toggled.connect(self._on_edit_toggled)

        # Setup chat overlay
        # Use the response_preview which is at index 0
        self.chat_overlay = ChatOverlay(self.preview_stack.widget(0))

        # Install event filter to handle resize events
        self.preview_container.installEventFilter(self)

        # Initialize with the current settings
        self.update_ui_mode()
        self.update_button_position()  # Position the button initially

        # Action frame for buttons and selector
        self.action_frame = QFrame()
        # Match width with response preview
        self.action_frame.setFixedWidth(330)
        # Only take minimum vertical space
        self.action_frame.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.action_layout = QVBoxLayout()
        self.action_layout.setContentsMargins(
            2, 0, 2, 0)  # Removed bottom margin completely
        # Further reduced spacing between elements
        self.action_layout.setSpacing(4)

        # Button layout with grid to ensure equal width
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Use a grid layout for equal button widths
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(4)

        # Create combined use button with dropdown
        self.use_split_button = SplitButton("Use")
        self.use_split_button.add_option("⚡ Copy/Paste", "paste")
        self.use_split_button.add_option("⌨ Type Text", "type")
        self.use_split_button.clicked.connect(self._handle_use)
        self.use_split_button.option_selected.connect(
            self._handle_option_selected)
        # Use Expanding policy to fill available space
        self.use_split_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Create export button
        self.export_button = QPushButton("Export")
        self.export_button.setProperty("class", "secondary")
        self.export_button.clicked.connect(self._handle_export)
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Match the height with use button
        self.export_button.setFixedHeight(30)
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: bold;
                min-height: 18px;
                max-height: 18px;
            }
            QPushButton:hover {
                background-color: #444444;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)

        # Add to grid layout with equal column stretch
        grid_layout.addWidget(self.use_split_button, 0, 0)
        grid_layout.addWidget(self.export_button, 0, 1)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

        # Add grid to button layout
        button_layout.addLayout(grid_layout)

        # Add layouts to action layout
        self.action_layout.addLayout(button_layout)
        self.action_frame.setLayout(self.action_layout)
        self.action_frame.hide()

        # Add widgets to main layout
        layout.addWidget(self.preview_container)
        # Use 0 stretch factor to minimize height
        layout.addWidget(self.action_frame)

        self.setLayout(layout)
        # Make entire panel take minimum required height
        self.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Minimum)

    def _create_pen_icon(self):
        """Create a simple pen icon for the edit button."""
        # Create a pixmap for drawing the pen icon
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Create a painter to draw on the pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set up the pen - use a thicker line for better visibility
        pen_color = QColor(255, 255, 255)  # White color
        painter.setPen(QPen(pen_color, 1.8))

        # Draw a simplified pencil/pen icon
        # Main diagonal line
        painter.drawLine(9, 19, 18, 10)

        # Pen tip (small triangle)
        pen_path = QPainterPath()
        pen_path.moveTo(18, 10)
        pen_path.lineTo(20, 12)
        pen_path.lineTo(16, 16)
        pen_path.lineTo(18, 10)

        # Fill the pen tip
        painter.setBrush(pen_color)
        painter.drawPath(pen_path)

        painter.end()

        return QIcon(pixmap)

    def _on_edit_toggled(self, checked):
        """Toggle between editable text and markdown preview."""
        if not self.is_chat_mode:  # Only applies in compose mode
            # Update user preference based on button state
            self._user_edit_preference = checked

            if checked:
                # Switch to editable text mode
                current_text = self.markdown_preview.get_plain_text() if self.preview_stack.currentWidget(
                ) == self.markdown_preview else self.response_preview.toPlainText()
                self.preview_stack.setCurrentWidget(self.response_preview)
                self.response_preview.setText(current_text)
                # Make text editable
                self.response_preview.setReadOnly(False)
                self.response_preview.setProperty("editable", True)
                self.response_preview.style().unpolish(self.response_preview)
                self.response_preview.style().polish(self.response_preview)
                self.response_preview.setPlaceholderText(
                    "You can edit this response before using...")
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
                # Hide edit button in chat mode
                self.edit_button.setVisible(False)
            else:
                # Transferring from markdown to text
                current_text = self.markdown_preview.get_plain_text()

                # Apply the user's stored edit preference
                self.edit_button.blockSignals(True)
                self.edit_button.setChecked(self._user_edit_preference)
                self.edit_button.blockSignals(False)

                # Show the appropriate view based on user preference
                if self._user_edit_preference:
                    self.preview_stack.setCurrentWidget(self.response_preview)
                    if current_text:
                        self.response_preview.setText(current_text)
                    # Make text editable
                    self.response_preview.setReadOnly(False)
                    self.response_preview.setProperty("editable", True)
                    self.response_preview.style().unpolish(self.response_preview)
                    self.response_preview.style().polish(self.response_preview)
                    self.response_preview.setPlaceholderText(
                        "You can edit this response before using...")
                else:
                    # Keep markdown view but update content
                    if current_text:
                        self.markdown_preview.set_markdown(current_text)

                # Show edit button in compose mode
                self.edit_button.setVisible(True)

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

        # Synchronize UI with user preference
        self._sync_ui_with_preference()

        # Auto-scroll to bottom if in text mode
        if not self.is_chat_mode and self.preview_stack.currentWidget() == self.response_preview:
            scrollbar = self.response_preview.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def set_editable(self, editable: bool, update_button: bool = True):
        """Set whether the response preview is editable.

        Args:
            editable: Whether the response should be editable
            update_button: Whether to update the button state (default: True)
        """
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
                self.response_preview.setPlaceholderText(
                    "You can edit this response before using...")
                # Update button state
                if update_button:
                    self.edit_button.setVisible(True)
                    self.edit_button.setChecked(True)
        else:
            # Normal text mode
            self.response_preview.setReadOnly(not editable)
            self.response_preview.setProperty("editable", editable)
            self.response_preview.style().unpolish(self.response_preview)
            self.response_preview.style().polish(self.response_preview)

            if editable:
                self.response_preview.setPlaceholderText(
                    "You can edit this response before using...")

            # Update button state but block signals to prevent recursive calls
            if update_button:
                self.edit_button.blockSignals(True)
                self.edit_button.setChecked(editable)
                self.edit_button.blockSignals(False)

    def show_actions(self, show: bool):
        """Show or hide the action frame."""
        self.action_frame.setVisible(show)

        # Only update edit button visibility if showing actions
        if show and not self.is_chat_mode:
            # Make the edit button visible
            self.edit_button.setVisible(True)

            # Ensure button state matches user preference without triggering signals
            self.edit_button.blockSignals(True)
            self.edit_button.setChecked(self._user_edit_preference)
            self.edit_button.blockSignals(False)

            # Also make sure the current displayed widget matches the preference
            if self._user_edit_preference:
                self.preview_stack.setCurrentWidget(self.response_preview)
            else:
                self.preview_stack.setCurrentWidget(self.markdown_preview)
        else:
            # Hide edit button in chat mode
            self.edit_button.setVisible(show and not self.is_chat_mode)

    def show_preview(self, show: bool):
        """Show or hide the response preview."""
        self.preview_stack.setVisible(show)
        # Also update edit button visibility
        if not self.is_chat_mode:
            self.edit_button.setVisible(show)

    def clear(self):
        """Clear the response preview."""
        self.response_preview.clear()
        self.markdown_preview.clear()
        self.show_actions(False)  # Hide actions when clearing

    def _handle_use(self):
        """Handle use button click."""
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
            method = self.use_split_button.get_selected_data()

            # Emit signal with method and response
            self.use_clicked.emit(method, response)

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
        # Synchronize UI with user preference when showing
        self._sync_ui_with_preference()
        # Update button position
        self.update_button_position()
        super().show()

    def _sync_ui_with_preference(self):
        """Synchronize UI state (edit button, preview widget, editable state) with user preference."""
        if self.is_chat_mode:
            # Always show markdown in chat mode
            self.preview_stack.setCurrentWidget(self.markdown_preview)
            self.edit_button.setVisible(False)
            return

        # Block signals to avoid triggering _toggle_edit_mode
        self.edit_button.blockSignals(True)
        self.edit_button.setChecked(self._user_edit_preference)
        self.edit_button.blockSignals(False)
        self.edit_button.setVisible(True)

        # Set the appropriate widget
        if self._user_edit_preference:
            # If edit is enabled, show text editor
            self.preview_stack.setCurrentWidget(self.response_preview)
            self.response_preview.setReadOnly(False)
            self.response_preview.setProperty("editable", True)
            self.response_preview.style().unpolish(self.response_preview)
            self.response_preview.style().polish(self.response_preview)
        else:
            # If edit is disabled, show markdown
            self.preview_stack.setCurrentWidget(self.markdown_preview)

    def _handle_option_selected(self, text, data):
        """Handle when an option is selected from the split button dropdown."""
        # No need to do anything here, the option is already stored in the button
        pass

    def update_button_position(self):
        """Update the position of the edit button to the bottom right corner of the preview."""
        try:
            if not hasattr(self, 'preview_container') or not hasattr(self, 'edit_button'):
                return

            # If we're in chat mode and the button exists, hide it
            if self.is_chat_mode and hasattr(self, 'edit_button'):
                self.edit_button.setVisible(False)
                return

            # Make sure the button is visible when not in chat mode
            self.edit_button.setVisible(True)

            # Get preview container dimensions
            container_width = self.preview_container.width()
            container_height = self.preview_container.height()

            # Calculate position (bottom right with padding)
            button_size = self.edit_button.size()
            padding = 10  # Padding from edge
            x_pos = container_width - button_size.width() - padding
            y_pos = container_height - button_size.height() - padding

            # Ensure positions are valid (non-negative)
            x_pos = max(0, x_pos)
            y_pos = max(0, y_pos)

            # Move button to position
            self.edit_button.move(x_pos, y_pos)

            # Ensure button is on top
            self.edit_button.raise_()

        except Exception as e:
            # Log warning if anything goes wrong
            logging.warning(f"Error positioning edit button: {e}")

    def showEvent(self, event):
        """Handle show events to ensure proper button positioning."""
        super().showEvent(event)
        # Update button position when shown
        QTimer.singleShot(0, self.update_button_position)

    def eventFilter(self, obj, event):
        """Event filter to handle resize events for the preview container."""
        if obj == self.preview_container:
            if event.type() == QEvent.Type.Resize:
                # Update button position on resize
                self.update_button_position()

                # Also update overlay size if we're using it
                if hasattr(self, 'preview_overlay'):
                    self.preview_overlay.setGeometry(
                        0, 0, obj.width(), obj.height())

            # Make sure we don't block scroll events
            elif event.type() in [QEvent.Type.Wheel, QEvent.Type.MouseButtonPress,
                                  QEvent.Type.MouseButtonRelease, QEvent.Type.MouseMove]:
                # Don't filter these events, let them be processed normally
                return False

        return super().eventFilter(obj, event)

    def update_ui_mode(self):
        """Update UI components based on current mode (chat or compose)."""
        if self.is_chat_mode:
            # In chat mode, show markdown and hide edit button
            self.preview_stack.setCurrentWidget(self.markdown_preview)
            self.edit_button.setVisible(False)
        else:
            # In compose mode, set widget and edit state based on user preference
            if self._user_edit_preference:
                self.preview_stack.setCurrentWidget(self.response_preview)
                self.response_preview.setReadOnly(False)
                self.response_preview.setProperty("editable", True)
                self.response_preview.style().unpolish(self.response_preview)
                self.response_preview.style().polish(self.response_preview)
            else:
                self.preview_stack.setCurrentWidget(self.markdown_preview)

            # Make edit button visible and sync with current preference
            self.edit_button.blockSignals(True)
            self.edit_button.setChecked(self._user_edit_preference)
            self.edit_button.blockSignals(False)
            self.edit_button.setVisible(True)

# If ChatOverlay is not defined elsewhere, create a simple placeholder class


class ChatOverlay:
    """Placeholder for ChatOverlay. Replace with actual implementation."""

    def __init__(self, parent=None):
        self.parent = parent

    def clear(self):
        pass
