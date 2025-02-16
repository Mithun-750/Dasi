from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QFrame, QLabel, QPushButton, QHBoxLayout, QProgressBar,
                             QGridLayout, QComboBox, QSizePolicy, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QClipboard, QIcon, QPixmap
from typing import Callable, Optional, Tuple
import sys
import os
from .settings import Settings
import logging


class UISignals(QObject):
    """Signals for UI operations."""
    show_window = pyqtSignal(int, int)  # x, y coordinates
    process_response = pyqtSignal(str)  # Response text
    process_error = pyqtSignal(str)  # Error message


class QueryWorker(QThread):
    """Worker thread for processing queries."""

    def __init__(self, process_fn: Callable[[str, Optional[Callable[[str], None]], Optional[str]], str],
                 query: str, signals: UISignals, model: Optional[str] = None):
        super().__init__()
        self.process_fn = process_fn
        self.query = query
        self.signals = signals
        self.model = model
        self.is_stopped = False

    def run(self):
        """Process the query and emit result."""
        try:
            # Pass a callback to handle streaming updates
            def stream_callback(partial_response: str):
                if not self.is_stopped:
                    self.signals.process_response.emit(partial_response)

            result = self.process_fn(self.query, stream_callback, self.model)
            if not self.is_stopped and not result:
                self.signals.process_error.emit("No response received")
            # Signal completion
            if not self.is_stopped:
                self.signals.process_response.emit("<COMPLETE>")
        except Exception as e:
            if not self.is_stopped:
                self.signals.process_error.emit(str(e))
        finally:
            self.quit()

    def stop(self):
        """Stop the worker cleanly."""
        self.is_stopped = True


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
        super().__init__()
        self.process_query = process_query
        self.signals = signals
        self.old_pos = None
        self.worker = None
        self.selected_text = None  # Store selected text
        self.last_response = None  # Store last response
        self.conversation_context = {}  # Store conversation context
        self.settings = Settings()  # Initialize settings

        # Connect to settings signals
        self.settings.models_changed.connect(self.update_model_selector)

        # Window flags
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.setup_ui()

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

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
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
        self.input_field.setPlaceholderText("Type your query...")
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

        # Response preview (hidden by default)
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)
        self.response_preview.setFixedWidth(300)
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
        self.reject_button = QPushButton("Reject")

        # Add stop button to layout but don't show it yet
        self.action_layout.addWidget(self.stop_button)

        # Configure accept/reject buttons
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self._handle_accept)
        self.reject_button = QPushButton("Reject")
        self.reject_button.clicked.connect(self._handle_reject)

        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.reject_button)

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
        """)

        # Set up key bindings
        self.input_field.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """Handle key events."""
        from PyQt6.QtCore import QEvent
        if (obj is self.input_field or obj is self.response_preview) and event.type() == QEvent.Type.KeyPress:
            # The event is already a QKeyEvent when it comes from Qt
            key_event = event

            # Handle Return key (submit) - only for input field
            if obj is self.input_field and key_event.key() == Qt.Key.Key_Return and not key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._handle_submit()
                return True

            # Handle Escape key (close)
            if key_event.key() == Qt.Key.Key_Escape:
                self._handle_escape()
                return True

            # Handle Shift+Return (newline) - only for input field
            if obj is self.input_field and key_event.key() == Qt.Key.Key_Return and key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                return False  # Let Qt handle it normally

        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Handle global key events."""
        if event.key() == Qt.Key.Key_Escape:
            self._handle_escape()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _handle_escape(self):
        """Handle escape key press."""
        self.hide()
        self.input_field.clear()
        self.reset_context()
        self.right_panel.hide()
        self.setFixedWidth(320)
        # Clear clipboard selection
        clipboard = QApplication.clipboard()
        clipboard.clear(QClipboard.Mode.Selection)

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

    def _handle_stop(self):
        """Handle stop button click."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.terminate()
            self.worker.wait()
            # Switch to accept/reject buttons and keep the content
            self.progress_bar.hide()
            self.input_field.setEnabled(True)
            self.stop_button.hide()
            self.insert_method.show()
            self.accept_button.show()
            self.reject_button.show()

    def _handle_submit(self):
        """Handle submit action."""
        query = self.input_field.toPlainText().strip()
        if query:
            # Show loading state and stop button
            self.input_field.setEnabled(False)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.progress_bar.show()
            self.stop_button.show()
            self.insert_method.hide()
            self.accept_button.hide()
            self.reject_button.hide()

            # Build context dictionary
            context = {}

            # Add selected text if available
            if self.selected_text:
                context['selected_text'] = self.selected_text

            # Add last response if available
            if self.last_response:
                context['last_response'] = self.last_response

            # Add mode to context
            context['mode'] = 'compose' if self.compose_mode.isChecked() else 'chat'

            # Format query with context
            if context:
                full_query = "Context:\n"
                if 'selected_text' in context:
                    full_query += f"Selected Text:\n{context['selected_text']}\n\n"
                if 'last_response' in context:
                    full_query += f"Last Response:\n{context['last_response']}\n\n"
                full_query += f"Mode: {context['mode']}\n\n"
                full_query += f"Query:\n{query}"
            else:
                full_query = query

            # Clear input field for next query
            self.input_field.clear()

            # Get selected model
            current_index = self.model_selector.currentIndex()
            model = None
            if current_index >= 0 and current_index < self.model_selector.count():
                model_info = self.model_selector.itemData(current_index)
                if isinstance(model_info, dict) and 'id' in model_info:
                    model = model_info['id']
                    logging.info(
                        f"Selected model: {model_info['name']} (ID: {model})")

            # Process query in background
            self.worker = QueryWorker(
                self.process_query, full_query, self.signals, model)
            self.worker.start()

    def _handle_error(self, error_msg: str):
        """Handle query error."""
        # Hide loading state
        self.progress_bar.hide()
        self.input_field.setEnabled(True)

        # Show error in preview
        self.response_preview.setText(f"Error: {error_msg}")
        self.response_preview.show()

        # Show reject button only, hide stop button
        self.action_frame.show()
        self.stop_button.hide()
        self.accept_button.hide()
        self.reject_button.show()

        # Adjust window size
        self.setFixedHeight(250)

    def _handle_response(self, response: str):
        """Handle query response (runs in main thread)."""
        # Check for completion signal
        if response == "<COMPLETE>":
            self.progress_bar.hide()
            self.input_field.setEnabled(True)
            self.stop_button.hide()
            if self.compose_mode.isChecked():
                self.insert_method.show()
                self.accept_button.show()
                self.reject_button.show()
            return

        # Store the response
        self.last_response = response

        # Show response preview
        self.response_preview.setText(response)
        self.response_preview.show()

        # Show action buttons and right panel
        self.action_frame.show()
        if self.compose_mode.isChecked():
            self.insert_method.show()
            self.accept_button.show()
            self.reject_button.show()
        else:
            self.insert_method.hide()
            self.accept_button.hide()
            self.reject_button.hide()
        self.right_panel.show()

        # Adjust window size
        self.setFixedWidth(650)

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
            query = f"!{method}:{response}"

            # Process the response with selected method
            self.process_query(query)

        self.right_panel.hide()

        # Reset window size
        self.setFixedWidth(320)

    def _handle_reject(self):
        """Reject the generated response."""
        # Hide response preview, buttons and right panel
        self.right_panel.hide()

        # Reset window size
        self.setFixedWidth(320)

        # Reset context
        self.reset_context()

        # Focus input field
        self.input_field.setFocus()

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
        # Update model selector when window is shown
        self.update_model_selector()

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
            self.reject_button.show()
        else:
            self.insert_method.hide()
            self.accept_button.hide()
            self.reject_button.hide()


class CopilotUI:
    def _show_window(self, x: int, y: int):
        """Show window at specified coordinates (runs in main thread)."""
        try:
            # First reset all context and input
            self.window.reset_context()
            self.window.input_field.clear()

            # Get selected text from clipboard
            clipboard = QApplication.clipboard()
            selected_text = clipboard.text(QClipboard.Mode.Selection)

            # Only set selected text if there's new text selected
            if selected_text and selected_text.strip():
                self.window.set_selected_text(selected_text.strip())

            # Position window near cursor with screen bounds check
            screen = self.app.primaryScreen().geometry()
            x = min(max(x + 10, 0), screen.width() - self.window.width())
            y = min(max(y + 10, 0), screen.height() - self.window.height())

            # Show and activate window
            self.window.move(x, y)
            self.window.show()
            self.window.activateWindow()
            self.window.raise_()
            self.window.input_field.setFocus()

        except Exception as e:
            logging.error(f"Error showing window: {str(e)}", exc_info=True)

    def __init__(self, process_query: Callable[[str], str]):
        """Initialize UI with a callback for processing queries."""
        self.process_query = process_query

        # Create QApplication in the main thread
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

        # Create signals object
        self.signals = UISignals()

        # Create window in main thread
        self.window = DasiWindow(self.process_query, self.signals)
        self.window.setFixedSize(320, 350)
        self.window.hide()

        # Connect signals
        self.signals.show_window.connect(self._show_window)
        self.signals.process_response.connect(self.window._handle_response)
        self.signals.process_error.connect(self.window._handle_error)

    def show_popup(self, x: int, y: int):
        """Emit signal to show popup window."""
        self.signals.show_window.emit(x, y)

    def run(self):
        """Start the UI event loop."""
        self.app.exec()
