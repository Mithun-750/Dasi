from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QFrame, QLabel, 
                             QPushButton, QHBoxLayout, QProgressBar, QGridLayout, 
                             QComboBox, QSizePolicy, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel, QEvent
from PyQt6.QtGui import QFont
from typing import Callable, Optional, Dict, Any
from pathlib import Path
import logging
import re

from ...settings import Settings
from ...components.chunk_dropdown import ChunkDropdown
from ...components.mention_highlighter import MentionHighlighter


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
        layout.setSpacing(5)
        
        # Context area with label and ignore button
        context_frame = QFrame()
        context_frame.setObjectName("contextFrame")
        context_layout = QVBoxLayout()
        context_layout.setContentsMargins(3, 3, 3, 3)
        context_layout.setSpacing(0)
        context_frame.setLayout(context_layout)

        # Create container for the context area
        container = QWidget()
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
        layout.addWidget(context_frame)

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
        self.input_field.setPlaceholderText("Type your query... (Use #web to search the internet)")
        self.input_field.setMinimumHeight(80)
        
        # Set up key bindings
        self.input_field.installEventFilter(self)

        # Create control bar for mode and model selection
        control_bar = QFrame()
        control_bar.setObjectName("controlBar")
        control_bar.setStyleSheet("""
            #controlBar {
                background-color: #363636;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        control_layout = QVBoxLayout(control_bar)
        control_layout.setContentsMargins(8, 4, 8, 4)
        control_layout.setSpacing(8)

        # Create mode selector container
        mode_container = QFrame()
        mode_container.setObjectName("modeContainer")
        mode_layout = QHBoxLayout(mode_container)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)

        # Create radio buttons
        self.mode_group = QButtonGroup()
        self.chat_mode = QRadioButton("Chat")
        self.compose_mode = QRadioButton("Compose")
        self.chat_mode.setChecked(True)  # Default to chat mode
        
        # Style radio buttons
        radio_style = """
            QRadioButton {
                color: #cccccc;
                font-size: 12px;
                padding: 6px 12px;
                border-radius: 3px;
                background-color: transparent;
                border: none;
                text-align: center;
            }
            QRadioButton:hover {
                background-color: #404040;
            }
            QRadioButton:checked {
                color: white;
                background-color: #2b5c99;
            }
            QRadioButton::indicator {
                width: 0px;
                height: 0px;
            }
        """
        self.chat_mode.setStyleSheet(radio_style)
        self.compose_mode.setStyleSheet(radio_style)
        
        # Set size policies to make buttons expand horizontally
        self.chat_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.compose_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Add to button group
        self.mode_group.addButton(self.chat_mode)
        self.mode_group.addButton(self.compose_mode)
        
        # Connect mode change signal
        self.mode_group.buttonClicked.connect(self._handle_mode_change)
        
        mode_layout.addWidget(self.chat_mode)
        mode_layout.addWidget(self.compose_mode)

        # Create model selector container
        model_container = QWidget()
        model_layout = QHBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)

        self.model_selector = QComboBox()
        self.model_selector.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 12px;
                color: #cccccc;
            }
            QComboBox:hover {
                border-color: #4a4a4a;
                background-color: #323232;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #888;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                selection-background-color: #2b5c99;
                selection-color: white;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 8px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #363636;
            }
            QComboBox::item {
                color: #cccccc;
            }
            QComboBox::drop-down:button {
                border: none;
            }
        """)
        self.update_model_selector()

        model_layout.addWidget(self.model_selector)

        # Add all elements to control bar vertically
        control_layout.addWidget(mode_container)
        control_layout.addWidget(model_container)

        # Loading progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.hide()

        layout.addWidget(self.input_field, 1)
        layout.addWidget(control_bar)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)
    
    def reset_context(self):
        """Reset all context including selected text."""
        self.selected_text = None
        self.context_label.hide()
        self.ignore_button.hide()

    def set_selected_text(self, text: str):
        """Set the selected text and update UI."""
        self.selected_text = text
        if text:
            self.context_label.setText(f"Selected Text: {text[:100]}..." if len(
                text) > 100 else f"Selected Text: {text}")
            self.context_label.show()
            self.ignore_button.show()
        else:
            self.context_label.hide()
            self.ignore_button.hide()
            self.selected_text = None
    
    def eventFilter(self, obj, event):
        """Handle key events."""
        if obj is self.input_field and event.type() == QEvent.Type.KeyPress:
            key_event = event

            # Show dropdown on @ key
            if key_event.text() == '@':
                self.chunk_dropdown.update_items(self.chunk_titles)
                self.chunk_dropdown.show()
                return False  # Let the @ be typed

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
        self.model_selector.setMaxVisibleItems(10)  # Show max 10 items in dropdown
    
    def get_selected_model(self):
        """Get the currently selected model ID."""
        current_index = self.model_selector.currentIndex()
        if current_index >= 0:
            model_info = self.model_selector.itemData(current_index)
            if model_info and 'id' in model_info:
                return model_info
        return None
    
    def is_compose_mode(self):
        """Check if compose mode is active."""
        return self.compose_mode.isChecked()
    
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
    
    def _handle_mode_change(self, button):
        """Handle mode change between Chat and Compose."""
        is_compose = button == self.compose_mode
        # Emit signal to inform parent
        self.mode_changed.emit(is_compose)
    
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
        context['mode'] = 'compose' if self.compose_mode.isChecked() else 'chat'
        
        return context 