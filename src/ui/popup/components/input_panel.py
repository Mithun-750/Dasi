from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QFrame, QLabel, 
                             QPushButton, QHBoxLayout, QProgressBar, QGridLayout, 
                             QComboBox, QSizePolicy, QRadioButton, QButtonGroup,
                             QScrollArea, QListWidget, QListWidgetItem, QStyledItemDelegate,
                             QLineEdit, QProxyStyle, QStyle, QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel, QEvent, QSize, QPoint, QRect, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QFont, QCursor, QColor, QPainter, QPen, QPainterPath
from typing import Callable, Optional, Dict, Any
from pathlib import Path
import logging
import re

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


class InputPanel(QWidget):
    """Input panel component for the Dasi window."""
    
    # Signals
    submit_query = pyqtSignal(str)  # Signal emitted when user submits a query
    mode_changed = pyqtSignal(bool)  # Signal emitted when mode changes (True for compose)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize properties
        self.settings = Settings()
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'
        self.selected_text = None  # Store selected text
        self.chunk_dropdown = None  # Will be initialized later
        self.highlighter = None  # Initialize highlighter reference
        self.is_web_search = False  # Flag to track if current query is a web search
        
        # Set minimum width for consistent UI
        self.setMinimumWidth(310)
        
        # Setup UI
        self._setup_ui()
        
        # Add syntax highlighter with chunks directory
        self.highlighter = MentionHighlighter(self.input_field.document(), self.chunks_dir)
        
        # Setup chunk dropdown
        self._setup_chunk_dropdown()
        
        # Connect to settings signals
        self.settings.models_changed.connect(self.update_model_selector)
        
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
        
        # Set size policy to collapse when empty
        self.context_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        # Create container for the context area
        container = QWidget()
        container.setProperty("class", "transparent-container")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # Add context label
        self.context_label = QLabel()
        self.context_label.setObjectName("contextLabel")
        self.context_label.setWordWrap(True)
        self.context_label.hide()

        # Add ignore button
        self.ignore_button = QPushButton("×")
        self.ignore_button.setObjectName("ignoreButton")
        self.ignore_button.setFixedSize(16, 16)
        self.ignore_button.clicked.connect(self.reset_context)
        self.ignore_button.hide()

        # Add both widgets to the same grid cell
        grid.addWidget(self.context_label, 0, 0)
        grid.addWidget(self.ignore_button, 0, 0,
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        # Ensure ignore button stays on top
        self.context_label.stackUnder(self.ignore_button)

        context_layout.addWidget(container)
        layout.addWidget(self.context_frame)
        
        # Hide the context frame initially
        self.context_frame.hide()

        # Override show/hide to handle button visibility and position
        def show_context():
            # Show both widgets
            super(type(self.context_label), self.context_label).show()
            self.ignore_button.show()
            self.ignore_button.raise_()

        def hide_context():
            super(type(self.context_label), self.context_label).hide()
            self.ignore_button.hide()

        self.context_label.show = show_context
        self.context_label.hide = hide_context

        # Input field
        self.input_field = QTextEdit()
        self.input_field.setObjectName("inputField")
        self.input_field.setProperty("class", "input-field")
        self.input_field.setPlaceholderText("Type your query... (Use #web to search the internet)")
        self.input_field.setMinimumHeight(80)
        
        # Set up key bindings
        self.input_field.installEventFilter(self)

        # Create mode selector container - using segmented button style
        mode_container = QWidget()
        mode_container.setObjectName("modeContainer")
        mode_container.setProperty("class", "mode-container")
        mode_layout = QHBoxLayout(mode_container)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)

        # Create modern mode selector with custom buttons
        self.chat_button = QPushButton("Chat")
        self.compose_button = QPushButton("Compose")
        
        # Style buttons and set initial state
        self.chat_button.setProperty("class", "segment-button active")
        self.compose_button.setProperty("class", "segment-button")
        self.chat_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.compose_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # Set fixed height for consistent look
        self.chat_button.setFixedHeight(32)
        self.compose_button.setFixedHeight(32)
        
        # Add buttons to layout
        mode_layout.addWidget(self.chat_button)
        mode_layout.addWidget(self.compose_button)
        
        # Connect button signals
        self.chat_button.clicked.connect(lambda: self._handle_mode_button_click(self.chat_button))
        self.compose_button.clicked.connect(lambda: self._handle_mode_button_click(self.compose_button))

        # Create model selector container
        model_container = QWidget()
        model_container.setProperty("class", "transparent-container")
        model_layout = QHBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)

        # Create a custom ComboBox with animated popup
        self.model_selector = CustomComboBox()
        self.model_selector.setProperty("class", "combo-box")
        self.update_model_selector()

        model_layout.addWidget(self.model_selector)

        # Loading progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.hide()

        layout.addWidget(self.input_field, 1)
        layout.addWidget(mode_container)
        layout.addWidget(model_container)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)
        
        # Apply styling
        self.setStyleSheet("""
            QWidget.transparent-container {
                background-color: transparent;
            }
            
            #contextLabel {
                color: #888888;
                font-size: 11px;
                padding: 4px 6px;
                background-color: #222222;
                border-radius: 4px;
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
        """Reset all context including selected text."""
        self.selected_text = None
        self.context_label.hide()
        self.ignore_button.hide()
        self.context_frame.hide()  # Also hide the frame

    def set_selected_text(self, text: str):
        """Set the selected text and update UI."""
        self.selected_text = text
        if text:
            self.context_frame.show()  # Show frame when there's text
            self.context_label.setText(f"Selected Text: {text[:100]}..." if len(
                text) > 100 else f"Selected Text: {text}")
            self.context_label.show()
            self.ignore_button.show()
        else:
            self.context_label.hide()
            self.ignore_button.hide()
            self.context_frame.hide()  # Hide frame when empty
            self.selected_text = None
    
    def eventFilter(self, obj, event):
        """Handle key events."""
        if obj is self.input_field and event.type() == QEvent.Type.KeyPress:
            key_event = event

            # Show dropdown on @ key only when properly spaced
            if key_event.text() == '@':
                # Get the text and cursor position
                cursor = self.input_field.textCursor()
                text = self.input_field.toPlainText()
                pos = cursor.position()
                
                # Check if @ is at the beginning or has a space before it
                is_start_or_after_space = pos == 0 or (pos > 0 and text[pos-1] in [' ', '\n', '\t'])
                
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
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, extra)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, extra)
        
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
        # Reload settings from disk
        self.settings.load_settings()

        self.model_selector.clear()
        selected_models = self.settings.get_selected_models()

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
            display_text = f"{name[:30]}... ({provider_display})" if len(name) > 30 else f"{name} ({provider_display})"
            
            # Full text for tooltip
            full_text = f"{name}\nProvider: {provider_display}"
            
            self.model_selector.addItem(display_text, model)
            # Set tooltip for the current index
            self.model_selector.setItemData(index, full_text, Qt.ItemDataRole.ToolTipRole)
            
            # If this is the default model, store its index
            if default_model_id and model['id'] == default_model_id:
                default_index = index

        self.model_selector.setEnabled(True)

        # Set the default model as current
        self.model_selector.setCurrentIndex(default_index)

        # Configure size policy to expand horizontally
        self.model_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    def get_selected_model(self):
        """Get the currently selected model ID."""
        current_index = self.model_selector.currentIndex()
        if current_index >= 0:
            model_info = self.model_selector.itemData(current_index)
            if model_info and 'id' in model_info:
                return model_info
        return None
    
    def _handle_mode_button_click(self, clicked_button):
        """Handle mode change between Chat and Compose buttons."""
        # Update button states
        is_compose = clicked_button == self.compose_button
        
        # Update visual states
        self.chat_button.setProperty("class", "segment-button")
        self.compose_button.setProperty("class", "segment-button")
        clicked_button.setProperty("class", "segment-button active")
        
        # Refresh style
        self.chat_button.style().unpolish(self.chat_button)
        self.chat_button.style().polish(self.chat_button)
        self.compose_button.style().unpolish(self.compose_button)
        self.compose_button.style().polish(self.compose_button)
        
        # Emit signal to inform parent
        self.mode_changed.emit(is_compose)
    
    def is_compose_mode(self):
        """Check if compose mode is active."""
        return self.compose_button.property("class") == "segment-button active"
    
    def enable_input(self, enabled=True):
        """Enable or disable the input field."""
        self.input_field.setEnabled(enabled)
    
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
        """Clear the input field."""
        self.input_field.clear()
    
    def _handle_submit(self):
        """Handle submit action."""
        query = self.get_query()
        if query:
            # Replace @mentions with chunk content
            query = self._replace_chunks(query)
            
            # Check if this is a web search query
            self.is_web_search = "#web" in query.lower()
            
            # Show loading state
            self.enable_input(False)
            self.show_progress(True)
            
            # Emit signal with query
            self.submit_query.emit(query)
    
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
        """Get the current context dictionary."""
        context = {}
        
        # Add selected text if available
        if self.selected_text:
            context['selected_text'] = self.selected_text
            
        # Add mode to context
        context['mode'] = 'compose' if self.compose_button.property("class") == "segment-button active" else 'chat'
        
        return context 