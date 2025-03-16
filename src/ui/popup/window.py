from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QFrame, QLabel, QPushButton, QHBoxLayout, QProgressBar,
                             QGridLayout, QComboBox, QSizePolicy, QRadioButton, QButtonGroup,
                             QCompleter, QListView, QLineEdit, QFileDialog, QMessageBox)
from PyQt6.QtCore import (Qt, QPoint, QThread, QObject, QSize, 
                          QStringListModel, QModelIndex, QAbstractListModel, QEvent, pyqtSignal, QTimer)
from PyQt6.QtGui import QFont, QClipboard, QIcon, QPixmap, QTextCursor, QMovie
from typing import Callable, Optional, Tuple, List
import sys
import os
import logging
from pathlib import Path
from ..settings import Settings
from ..components.chunk_dropdown import ChunkDropdown
from ..components.mention_highlighter import MentionHighlighter
from ..components.query_worker import QueryWorker
from ..components.ui_signals import UISignals
import re
import uuid
from datetime import datetime

# Import LLMHandler for filename suggestions
from llm_handler import LLMHandler


class DasiWindow(QWidget):
    def reset_context(self):
        """Reset all context including selected text and last response."""
        self.selected_text = None
        self.last_response = None
        self.conversation_context = {}
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

    """Main popup window for Dasi."""

    def __init__(self, process_query: Callable[[str], str], signals: UISignals):
        # Initialize session ID
        self.session_id = str(uuid.uuid4())
        
        super().__init__()
        self.process_query = process_query
        self.signals = signals
        self.old_pos = None
        self.worker = None
        self.selected_text = None  # Store selected text
        self.last_response = None  # Store last response
        self.conversation_context = {}  # Store conversation context
        self.settings = Settings()  # Initialize settings
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'
        self.chunk_dropdown = None  # Will be initialized in setup_ui
        self.highlighter = None  # Initialize highlighter reference
        self.loading_animation = None  # Will be initialized in setup_ui
        self.is_web_search = False  # Flag to track if current query is a web search

        # Connect to settings signals
        self.settings.models_changed.connect(self.update_model_selector)

        # Window flags
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.setup_ui()
        
        # Add syntax highlighter with chunks directory
        self.highlighter = MentionHighlighter(self.input_field.document(), self.chunks_dir)
        
        # Setup chunk dropdown
        self.setup_chunk_dropdown()
        
        # Setup loading animation
        self.setup_loading_animation()

    def setup_ui(self):
        """Set up the UI components."""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Main frame with border radius
        self.main_frame = QFrame()
        self.main_frame.setObjectName("mainFrame")
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Header with logo and title
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        # Add logo
        logo_label = QLabel()
        logo_label.setObjectName("logoLabel")
        
        # Get the absolute path to the icon
        if getattr(sys, 'frozen', False):
            # If we're running as a bundled app
            base_path = sys._MEIPASS
        else:
            # If we're running in development
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Try multiple icon paths
        potential_icon_paths = [
            os.path.join(base_path, 'src', 'assets', 'Dasi.png'),
            os.path.join(base_path, 'assets', 'Dasi.png'),
        ]

        icon_path = None
        for path in potential_icon_paths:
            if os.path.exists(path):
                icon_path = path
                break

        if icon_path:
            pixmap = QPixmap(icon_path)
            # Scale the logo to 20x20 pixels while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logging.warning("Logo not found")

        # Title with custom font
        title = QLabel("Dasi")
        title.setObjectName("titleLabel")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))

        # Add reset session button before close button
        self.reset_session_button = QPushButton("Reset Session")
        self.reset_session_button.setObjectName("resetSessionButton")
        self.reset_session_button.clicked.connect(self._handle_reset_session)
        self.reset_session_button.setFixedWidth(100)
        self.reset_session_button.hide()  # Hide by default

        # Add close button
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.clicked.connect(self._handle_escape)
        close_button.setFixedSize(24, 24)

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.reset_session_button)
        header_layout.addWidget(close_button)
        header.setLayout(header_layout)

        # Content area with horizontal layout
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)

        # Left side - Input area
        left_panel = QFrame()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # Set minimum width for consistent UI
        left_panel.setMinimumWidth(310)  # Added to ensure input field has adequate width

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
        left_layout.addWidget(context_frame)

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

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Type your query... (Use #web to search the internet)")
        self.input_field.setMinimumHeight(80)

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

        left_layout.addWidget(self.input_field, 1)
        left_layout.addWidget(control_bar)
        left_layout.addWidget(self.progress_bar)
        left_panel.setLayout(left_layout)

        # Right side - Preview and buttons
        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        self.right_layout = right_layout  # Store reference to the layout
        
        # Set a fixed width for the right panel to ensure consistency
        right_panel.setFixedWidth(360)  # Increased from 330px to 360px

        # Response preview (hidden by default)
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)  # Start as read-only
        self.response_preview.setFixedWidth(340)  # Increased from 320px to 340px
        self.response_preview.setStyleSheet("""
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #4a4a4a;
                font-size: 12px;
                color: #ffffff;
                font-family: "Helvetica", sans-serif;
            }
            QTextEdit[editable="true"] {
                background-color: #404040;
                border: 1px solid #505050;
            }
            QTextEdit[editable="true"]:focus {
                border: 1px solid #606060;
            }
        """)
        self.response_preview.hide()

        # Action buttons (hidden by default)
        self.action_frame = QFrame()
        self.action_layout = QVBoxLayout()  # Vertical layout for combo box above buttons
        self.action_layout.setContentsMargins(5, 0, 5, 5)

        # Create stop button (hidden by default)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self._handle_stop)
        self.stop_button.hide()

        # Create insertion method selector
        self.insert_method = QComboBox()
        self.insert_method.setObjectName("insertMethod")
        self.insert_method.addItem("⚡ Copy/Paste", "paste")
        self.insert_method.addItem("⌨ Type Text", "type")
        self.insert_method.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Create accept/reject buttons
        self.accept_button = QPushButton("Accept")
        self.export_button = QPushButton("Export")

        # Add stop button to layout but don't show it yet
        self.action_layout.addWidget(self.stop_button)

        # Configure accept/export buttons
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self._handle_accept)
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._handle_export)

        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.export_button)

        # Add widgets to action layout vertically
        self.action_layout.addWidget(self.insert_method)
        self.action_layout.addLayout(button_layout)
        self.action_frame.setLayout(self.action_layout)
        self.action_frame.hide()

        right_layout.addWidget(self.response_preview, 1)
        right_layout.addWidget(self.action_frame)
        right_panel.setLayout(right_layout)
        right_panel.hide()
        self.right_panel = right_panel

        # Add panels to content layout
        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(right_panel, 0)

        # Add all components to main frame
        frame_layout.addWidget(header)
        frame_layout.addLayout(content_layout)

        self.main_frame.setLayout(frame_layout)
        layout.addWidget(self.main_frame)
        self.setLayout(layout)

        # Set up styling
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                color: #ffffff;
            }
            #mainFrame {
                background-color: #2b2b2b;
                border-radius: 10px;
                border: 1px solid #3f3f3f;
            }
            #header {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #363636, stop:1 #2b2b2b);
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #404040;
            }
            #logoLabel {
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            #titleLabel {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }
            #closeButton {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 20px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            #closeButton:hover {
                color: #ffffff;
                background-color: #ff4444;
                border-radius: 12px;
            }
            #rightPanel {
                background-color: #323232;
                border-radius: 5px;
                padding: 5px;
            }
            #contextFrame {
                background: transparent;
            }
            #contextLabel {
                color: #888888;
                font-size: 11px;
                padding: 4px 6px;
                background-color: #323232;
                border-radius: 3px;
            }
            #ignoreButton {
                background-color: #464646;
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
                background-color: #565656;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #4a4a4a;
                font-size: 12px;
                color: #ffffff;
                font-family: "Helvetica", sans-serif;
            }
            QTextEdit::selection {
                background-color: #4a4a4a;
                color: #ffffff;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                color: white;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            #stopButton {
                background-color: #ff4444;
                min-width: 60px;
            }
            #stopButton:hover {
                background-color: #ff6666;
            }
            #insertMethod {
                background-color: #363636;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 5px 8px;
                color: #cccccc;
                min-height: 28px;
                font-size: 11px;
            }
            #insertMethod::drop-down {
                border: none;
                width: 20px;
                padding-right: 8px;
            }
            #insertMethod::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #888;
                margin-right: 4px;
            }
            #insertMethod:hover {
                background-color: #404040;
                border-color: #5a5a5a;
                color: white;
            }
            #insertMethod QAbstractItemView {
                background-color: #363636;
                border: 1px solid #4a4a4a;
                color: #cccccc;
                selection-background-color: #4a4a4a;
                selection-color: white;
                outline: none;
            }
            #insertMethod QAbstractItemView::item {
                padding: 5px 8px;
                min-height: 24px;
            }
            #insertMethod QAbstractItemView::item:hover {
                background-color: #404040;
                color: white;
            }
            QProgressBar {
                border: none;
                background-color: #363636;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
            }
            #contextLabel {
                color: #888888;
                font-size: 11px;
                padding: 2px 5px;
                background-color: #323232;
                border-radius: 3px;
            }
            #resetSessionButton {
                background-color: #404040;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
                color: #cccccc;
                font-size: 11px;
            }
            #resetSessionButton:hover {
                background-color: #505050;
                color: white;
            }
        """)

        # Set up key bindings
        self.input_field.installEventFilter(self)

    def setup_chunk_dropdown(self):
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

    def get_word_under_cursor(self) -> Tuple[str, int]:
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

    def eventFilter(self, obj, event) -> bool:
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

    def _reset_ui_after_stop(self):
        """Reset UI elements after stopping an operation."""
        # Re-enable input field
        self.input_field.setEnabled(True)
        
        # Hide loading indicators
        self.progress_bar.hide()
        self.stop_button.hide()
        
        # Hide loading animation if it's active
        if hasattr(self, 'loading_animation') and self.loading_animation:
            if isinstance(self.loading_animation, QMovie):
                self.loading_animation.stop()
            else:
                self.dot_timer.stop()
            self.loading_container.hide()
            
            # Also stop the loading progress bar
            if hasattr(self, 'loading_progress_bar'):
                self.loading_progress_bar.setRange(0, 100)
                self.loading_progress_bar.setValue(100)
        
        # Hide panels and collapse UI
        self.response_preview.hide()
        self.right_panel.hide()
        self.loading_container.hide()
        self.action_frame.hide()  # Hide action buttons
        self.setFixedWidth(340)   # Reset to input-only width
        
        # Reset web search flag
        self.is_web_search = False

    def _handle_stop(self):
        """Handle stop button click."""
        if self.worker and self.worker.isRunning():
            try:
                # First, attempt to cancel any ongoing web search
                if self.is_web_search:
                    try:
                        # Get the Dasi instance from the instance manager
                        from instance_manager import DasiInstanceManager
                        dasi_instance = DasiInstanceManager.get_instance()
                        
                        if dasi_instance and dasi_instance.llm_handler and dasi_instance.llm_handler.web_search_handler:
                            logging.info("Cancelling ongoing web search operation")
                            dasi_instance.llm_handler.web_search_handler.cancel_search()
                        else:
                            logging.warning("Could not access web search handler for cancellation")
                    except Exception as e:
                        logging.error(f"Error cancelling web search: {str(e)}")
                
                # Signal worker to stop
                self.worker.stop()
                
                # Use the safer termination method with timeout
                self.worker.terminate_safely()
                
                # Reset UI to clean state
                self._reset_ui_after_stop()
                
            except Exception as e:
                # Catch any exceptions during the stop process to prevent app crashes
                logging.error(f"Error during stop operation: {str(e)}")
                # Try to restore UI to a usable state
                self._reset_ui_after_stop()

    def _handle_escape(self):
        """Handle escape key press."""
        try:
            # Cancel any ongoing web search if needed
            if self.is_web_search and self.worker and self.worker.isRunning():
                try:
                    # Get the Dasi instance from the instance manager
                    from instance_manager import DasiInstanceManager
                    dasi_instance = DasiInstanceManager.get_instance()
                    
                    if dasi_instance and dasi_instance.llm_handler and dasi_instance.llm_handler.web_search_handler:
                        logging.info("Cancelling ongoing web search operation on ESC")
                        dasi_instance.llm_handler.web_search_handler.cancel_search()
                        
                        # Signal worker to stop
                        self.worker.stop()
                        
                        # Use the safer termination method with timeout
                        self.worker.terminate_safely()
                except Exception as e:
                    logging.error(f"Error cancelling web search on ESC: {str(e)}")
            
            # Reset UI elements
            self._reset_ui_after_stop()
            
            # Additionally for escape, hide the window and clear input
            self.hide()
            self.input_field.clear()
            self.reset_context()
            
            # Clear clipboard selection
            clipboard = QApplication.clipboard()
            clipboard.clear(QClipboard.Mode.Selection)
            
        except Exception as e:
            # Catch any exceptions to prevent app crashes
            logging.error(f"Error handling escape key: {str(e)}")
            # Try to restore to a clean state
            self.hide()
            self.is_web_search = False
    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """Handle mouse release for dragging."""
        self.old_pos = None

    def _handle_submit(self):
        """Handle submit action."""
        query = self.input_field.toPlainText().strip()
        if query:
            # Replace @mentions with chunk content
            query = self._replace_chunks(query)
            
            # Check if this is a web search query
            self.is_web_search = "#web" in query.lower()

            # Show loading state and stop button
            self.input_field.setEnabled(False)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.progress_bar.show()
            
            # Hide the main stop button if we're showing the loading animation
            if self.is_web_search:
                self.stop_button.hide()
            else:
                self.stop_button.show()
                
            self.insert_method.hide()
            self.accept_button.hide()
            self.export_button.hide()
            
            # Show loading animation for web searches
            if self.is_web_search:
                # Hide the response preview and show the loading animation
                self.response_preview.hide()
                self.loading_container.show()
                self.right_panel.show()
                self.setFixedWidth(680)  # Increased from 650px to 680px to match the wider preview
                
                # Start the animation
                if isinstance(self.loading_animation, QMovie):
                    self.loading_animation.start()
                else:
                    self.dot_timer.start(500)  # Update every 500ms
                
                # Update loading text
                search_term = query.replace("#web", "").strip()
                if search_term:
                    self.loading_text_label.setText(f"Searching the web for: {search_term}")
                else:
                    self.loading_text_label.setText("Searching the web...")
                    
                # Reset the info label to the first message
                self.loading_info_label.setText("This may take a moment as we gather relevant information from the web.")
                
                # Start the progress bar animation
                self.loading_progress_bar.setRange(0, 0)  # Indeterminate progress

            # Build context dictionary
            context = {}

            # Add selected text if available
            if self.selected_text:
                context['selected_text'] = self.selected_text

            # Add mode to context
            context['mode'] = 'compose' if self.compose_mode.isChecked() else 'chat'

            # Format query with context
            if context:
                full_query = "Context:\n"
                if 'selected_text' in context:
                    full_query += f"=====SELECTED_TEXT=====<text selected by the user>\n{context['selected_text']}\n=======================\n\n"
                full_query += f"=====MODE=====<user selected mode>\n{context['mode']}\n=======================\n\n"
                full_query += f"Query:\n{query}"
            else:
                full_query = query

            # Get selected model
            current_index = self.model_selector.currentIndex()
            model = None
            if current_index >= 0 and current_index < self.model_selector.count():
                model_info = self.model_selector.itemData(current_index)
                if isinstance(model_info, dict) and 'id' in model_info:
                    model = model_info['id']
                    logging.info(
                        f"Selected model: {model_info['name']} (ID: {model})")

            # Process query in background with session ID
            self.worker = QueryWorker(
                self.process_query, full_query, self.signals, model, self.session_id)
            self.worker.start()

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

    def _handle_error(self, error_msg: str):
        """Handle query error."""
        # Hide loading state
        self.progress_bar.hide()
        self.stop_button.hide()
        
        # Hide loading animation if it's active
        if hasattr(self, 'loading_animation') and self.loading_animation:
            if isinstance(self.loading_animation, QMovie):
                self.loading_animation.stop()
            else:
                self.dot_timer.stop()
            self.loading_container.hide()
        
        # Re-enable input field with existing content
        self.input_field.setEnabled(True)

        # Show error in preview
        self.response_preview.setText(f"Error: {error_msg}")
        self.response_preview.show()

        # Show export button only
        self.action_frame.show()
        self.accept_button.hide()
        self.export_button.show()

        # Adjust window size
        self.setFixedHeight(250)

    def _handle_response(self, response: str):
        """Handle query response (runs in main thread)."""
        # Check for completion signal
        if response == "<COMPLETE>":
            self.progress_bar.hide()
            self.stop_button.hide()
            
            # Hide loading animation if it's active
            if hasattr(self, 'loading_animation') and self.loading_animation:
                if isinstance(self.loading_animation, QMovie):
                    self.loading_animation.stop()
                else:
                    self.dot_timer.stop()
                self.loading_container.hide()
            
            # Reset web search flag
            self.is_web_search = False
            
            # Clear and re-enable input field only on successful completion
            self.input_field.clear()
            self.input_field.setEnabled(True)
            
            # Show reset session button since we now have history
            self.reset_session_button.show()
            
            if self.compose_mode.isChecked():
                # Make response preview editable in compose mode
                self.response_preview.setReadOnly(False)
                self.response_preview.setProperty("editable", True)
                self.response_preview.style().unpolish(self.response_preview)
                self.response_preview.style().polish(self.response_preview)
                # Add a hint that it's editable
                self.response_preview.setPlaceholderText("You can edit this response before accepting...")
                
                self.insert_method.show()
                self.accept_button.show()
                self.export_button.show()
            return

        # Store the response
        self.last_response = response

        # If we were showing the loading animation, hide it and show the response preview
        if self.is_web_search and self.loading_container.isVisible():
            # Only hide the loading container when we have a substantial response
            # This prevents flickering between loading and very short initial responses
            if len(response) > 50:
                self.loading_container.hide()
                
                # Stop the animation
                if isinstance(self.loading_animation, QMovie):
                    self.loading_animation.stop()
                else:
                    self.dot_timer.stop()
                    
                # Stop the loading progress bar
                if hasattr(self, 'loading_progress_bar'):
                    self.loading_progress_bar.setRange(0, 100)
                    self.loading_progress_bar.setValue(100)

        # Show response preview (as read-only during streaming)
        self.response_preview.setReadOnly(True)
        self.response_preview.setProperty("editable", False)
        self.response_preview.style().unpolish(self.response_preview)
        self.response_preview.style().polish(self.response_preview)
        self.response_preview.setText(response)
        
        # Auto-scroll to bottom
        scrollbar = self.response_preview.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        self.response_preview.show()
        self.right_panel.show()

        # During streaming, only show stop button
        self.action_frame.show()
        self.insert_method.hide()
        self.accept_button.hide()
        self.export_button.hide()
        self.stop_button.show()

        # Adjust window size - keep consistent with web search width
        self.setFixedWidth(680)  # Increased from 650px to 680px to accommodate the wider right panel

    def _handle_accept(self):
        """Accept the generated response."""
        response = self.response_preview.toPlainText()
        if response:
            self.hide()
            self.input_field.clear()
            self.reset_context()
            # Clear clipboard selection
            clipboard = QApplication.clipboard()
            clipboard.clear(QClipboard.Mode.Selection)

            # Get selected insertion method
            method = self.insert_method.currentData()

            # Format query with method and response
            # Remove any leading colon that might be in the response
            if response.startswith(':'):
                response = response[1:].lstrip()
                
            query = f"!{method}:{response}"

            # Process the response with selected method
            self.process_query(query)

            # Reset response preview to read-only state
            self.response_preview.setReadOnly(True)
            self.response_preview.setProperty("editable", False)
            self.response_preview.style().unpolish(self.response_preview)
            self.response_preview.style().polish(self.response_preview)

        self.right_panel.hide()

        # Reset window size
        self.setFixedWidth(340)  # Input-only mode width

    def _handle_export(self):
        """Export the generated response to a markdown file."""
        response = self.response_preview.toPlainText()
        if response:
            # Show loading state in the export button
            original_text = self.export_button.text()
            self.export_button.setText("Cancel")
            
            # Create a worker thread for filename suggestion
            class FilenameWorker(QThread):
                finished = pyqtSignal(str)
                error = pyqtSignal(str)
                
                def __init__(self, content, session_id):
                    super().__init__()
                    self.content = content
                    self.session_id = session_id
                    self.is_stopped = False
                
                def run(self):
                    try:
                        if not self.is_stopped:
                            llm_handler = LLMHandler()
                            filename = llm_handler.suggest_filename(
                                content=self.content,
                                session_id=self.session_id
                            )
                            self.finished.emit(filename)
                    except Exception as e:
                        self.error.emit(str(e))
                
                def stop(self):
                    self.is_stopped = True
            
            # Create and configure the worker
            self.filename_worker = FilenameWorker(response, self.session_id)
            
            def handle_filename_ready(suggested_filename):
                # Restore button state
                self.export_button.setText(original_text)
                self.export_button.setEnabled(True)
                # Restore the original click handler
                self.export_button.clicked.disconnect()
                self.export_button.clicked.connect(self._handle_export)
                
                try:
                    # Get the default export path from settings
                    default_path = self.settings.get('general', 'export_path', default=os.path.expanduser("~/Documents"))
                    
                    # Combine default path with suggested filename
                    default_filepath = os.path.join(default_path, suggested_filename)
                    
                    # Open file dialog with suggested name and default path
                    filename, _ = QFileDialog.getSaveFileName(
                        self,
                        "Save Response",
                        default_filepath,
                        "Markdown Files (*.md);;All Files (*)"
                    )
                    
                    if filename:  # Only save if user didn't cancel
                        # Write response to file
                        with open(filename, "w") as f:
                            f.write(response)
                
                except Exception as e:
                    logging.error(f"Error during export: {str(e)}", exc_info=True)
                    self._handle_export_error(response)
            
            def handle_filename_error(error):
                logging.error(f"Error getting filename suggestion: {error}")
                self._handle_export_error(response)
            
            # Connect signals
            self.filename_worker.finished.connect(handle_filename_ready)
            self.filename_worker.error.connect(handle_filename_error)
            
            # Update export button to allow cancellation
            self.export_button.clicked.disconnect()
            self.export_button.clicked.connect(self._cancel_export)
            
            # Start the worker
            self.filename_worker.start()
    
    def _cancel_export(self):
        """Cancel the export operation."""
        if hasattr(self, 'filename_worker') and self.filename_worker.isRunning():
            self.filename_worker.stop()
            self.filename_worker.wait()
            
            # Restore export button
            self.export_button.setText("Export")
            self.export_button.clicked.disconnect()
            self.export_button.clicked.connect(self._handle_export)
    
    def _handle_export_error(self, response: str):
        """Handle export errors by falling back to timestamp-based filename."""
        try:
            # Restore button state
            self.export_button.setText("Export")
            self.export_button.clicked.disconnect()
            self.export_button.clicked.connect(self._handle_export)
            self.export_button.setEnabled(True)
            
            # Use timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suggested_filename = f"dasi_response_{timestamp}.md"
            default_path = self.settings.get('general', 'export_path', default=os.path.expanduser("~/Documents"))
            default_filepath = os.path.join(default_path, suggested_filename)
            
            # Open file dialog with fallback name
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Response",
                default_filepath,
                "Markdown Files (*.md);;All Files (*)"
            )
            
            if filename:  # Only save if user didn't cancel
                # Write response to file
                with open(filename, "w") as f:
                    f.write(response)
        
        except Exception as e:
            logging.error(f"Error during export fallback: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export response: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

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

    def showEvent(self, event):
        """Called when the window becomes visible."""
        super().showEvent(event)
        # Update model selector and chunk titles when window is shown
        self.update_model_selector()
        self.update_chunk_titles()

    def get_selected_model(self) -> str:
        """Get the currently selected model ID."""
        current_index = self.model_selector.currentIndex()
        if current_index >= 0:
            model_info = self.model_selector.itemData(current_index)
            if model_info:
                return model_info['id']
        return None

    def _handle_mode_change(self, button):
        """Handle mode change between Chat and Compose."""
        is_compose = button == self.compose_mode
        # Show/hide action elements based on mode
        if is_compose:
            self.insert_method.show()
            self.accept_button.show()
            self.export_button.show()
        else:
            self.insert_method.hide()
            self.accept_button.hide()
            self.export_button.hide()

    def keyPressEvent(self, event):
        """Handle global key events for the window."""
        if event.key() == Qt.Key.Key_Escape:
            self._handle_escape()
        else:
            super().keyPressEvent(event)

    def _handle_reset_session(self):
        """Handle reset session button click."""
        # Store current selected text
        current_selected_text = self.selected_text
        
        # Generate new session ID
        self.session_id = str(uuid.uuid4())
        # Clear conversation history in LLM handler
        self.process_query(f"!clear_session:{self.session_id}")
        
        # Reset UI but preserve selected text
        self.reset_context()
        if current_selected_text:
            self.set_selected_text(current_selected_text)
            
        self.input_field.clear()
        self.response_preview.clear()
        self.right_panel.hide()
        self.setFixedWidth(340)  # Input-only mode width
        # Hide reset button since history is now cleared
        self.reset_session_button.hide()

    def setup_loading_animation(self):
        """Set up the loading animation widget."""
        # Create a container for the loading animation
        self.loading_container = QWidget()
        self.loading_container.setObjectName("loadingContainer")
        loading_layout = QVBoxLayout(self.loading_container)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setContentsMargins(30, 30, 30, 30)  # Reduced top/bottom margins
        loading_layout.setSpacing(15)  # Reduced spacing
        
        # Set minimum width for the loading container to prevent text cutoff
        self.loading_container.setMinimumWidth(300)  # Increased from 320px to 340px
        self.loading_container.setMaximumWidth(340)  # Increased from 320px to 340px
        
        # Create the loading animation label
        self.loading_animation_label = QLabel()
        self.loading_animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_animation_label.setMinimumSize(140, 140)  # Slightly smaller
        self.loading_animation_label.setMaximumSize(180, 180)  # Slightly smaller
        
        # Get the absolute path to the assets directory
        if getattr(sys, 'frozen', False):
            # If we're running as a bundled app
            base_path = sys._MEIPASS
        else:
            # If we're running in development
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Try to find a loading.gif file in the assets directory
        potential_gif_paths = [
            os.path.join(base_path, 'src', 'assets', 'loading.gif'),
            os.path.join(base_path, 'assets', 'loading.gif'),
        ]
        
        gif_path = None
        for path in potential_gif_paths:
            if os.path.exists(path):
                gif_path = path
                break
        
        # If no loading.gif is found, we'll create a text-based animation
        if gif_path:
            self.loading_animation = QMovie(gif_path)
            self.loading_animation.setScaledSize(QSize(140, 140))  # Slightly smaller
            self.loading_animation_label.setMovie(self.loading_animation)
            logging.info(f"Using GIF animation from {gif_path}")
        else:
            # Create a text-based animation as fallback
            self.loading_animation_label.setText("Searching")
            self.loading_animation_label.setStyleSheet("font-size: 18px; color: #cccccc; font-weight: bold;")
            self.dot_timer = QTimer(self)
            self.dot_timer.timeout.connect(self._update_loading_text)
            self.dot_count = 0
            logging.warning("Loading GIF not found, using text-based animation")
        
        # Create a label for the search message
        self.loading_text_label = QLabel("Searching the web for information...")
        self.loading_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_text_label.setStyleSheet("""
            font-size: 15px; 
            color: #f0f0f0; 
            margin-top: 10px;
            font-weight: 500;
            letter-spacing: 0.3px;
        """)
        self.loading_text_label.setWordWrap(True)
        self.loading_text_label.setMinimumWidth(300)  # Increased from 300px to 320px
        
        # Create a label for additional information
        self.loading_info_label = QLabel("This may take a moment as we gather relevant information from the web.")
        self.loading_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_info_label.setStyleSheet("""
            font-size: 13px; 
            color: #b0b0b0; 
            margin-top: 5px;
            font-style: italic;
            letter-spacing: 0.2px;
        """)
        self.loading_info_label.setWordWrap(True)
        self.loading_info_label.setMinimumWidth(300)  # Increased from 300px to 320px
        
        # Create a progress bar for the loading container
        self.loading_progress_bar = QProgressBar()
        self.loading_progress_bar.setObjectName("loadingProgressBar")
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate progress
        self.loading_progress_bar.setFixedHeight(4)
        self.loading_progress_bar.setTextVisible(False)
        
        # Create a container for the progress bar to ensure proper margins
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 10, 0, 10)  # Add vertical margins
        progress_layout.addWidget(self.loading_progress_bar)
        
        # Add widgets to the layout
        loading_layout.addWidget(self.loading_animation_label)
        loading_layout.addWidget(self.loading_text_label)
        loading_layout.addWidget(self.loading_info_label)
        loading_layout.addWidget(progress_container)
        
        # Add a stop button directly in the loading container
        self.loading_stop_button = QPushButton("Stop Search")
        self.loading_stop_button.setObjectName("loadingStopButton")
        self.loading_stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.loading_stop_button.setStyleSheet("""
            #loadingStopButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 20px;  /* Increased horizontal padding */
                font-size: 13px;
                font-weight: 600;
            }
            #loadingStopButton:hover {
                background-color: #ff6666;
            }
            #loadingStopButton:pressed {
                background-color: #c0392b;
            }
        """)
        self.loading_stop_button.clicked.connect(self._handle_stop)
        
        # Create a container for the button to center it
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.addWidget(self.loading_stop_button)
        
        loading_layout.addWidget(button_container)
        
        # Style the container
        self.loading_container.setStyleSheet("""
            #loadingContainer {
                background-color: rgba(30, 30, 46, 40);  /* Even more translucent dark background */
                border-radius: 10px;
                border: 1px solid rgba(58, 63, 75, 60);  /* More translucent border */
            }
            #loadingProgressBar {
                border: none;
                background-color: rgba(45, 45, 61, 80);  /* More translucent progress bar background */
                height: 4px;
            }
            #loadingProgressBar::chunk {
                background-color: rgba(74, 158, 255, 180);  /* Slightly translucent progress bar */
            }
        """)
        
        # Hide the container initially
        self.loading_container.hide()
        
        # Add the loading container to the right panel
        self.right_layout.insertWidget(0, self.loading_container, 1)
    
    def _update_loading_text(self):
        """Update the loading text animation."""
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.loading_animation_label.setText(f"Searching{dots}")
        
        # Rotate through different informational messages
        info_messages = [
            "This may take a moment as we gather relevant information from the web.",
            "We're searching multiple sources to find the most accurate information.",
            "Web search results will be used to provide up-to-date information.",
            "You can stop the search at any time by clicking the Stop button below."
        ]
        
        # Update the info message every 4 cycles (2 seconds)
        if self.dot_count == 0:
            current_text = self.loading_info_label.text()
            current_index = info_messages.index(current_text) if current_text in info_messages else -1
            next_index = (current_index + 1) % len(info_messages)
            self.loading_info_label.setText(info_messages[next_index])

    def hideEvent(self, event):
        """Handle hide event to clean up resources."""
        # Stop any running animations
        if hasattr(self, 'loading_animation') and self.loading_animation:
            if isinstance(self.loading_animation, QMovie):
                self.loading_animation.stop()
            elif hasattr(self, 'dot_timer') and self.dot_timer.isActive():
                self.dot_timer.stop()
        
        super().hideEvent(event)

