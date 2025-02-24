from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                            QPushButton, QProgressBar, QComboBox, QApplication)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QClipboard
from typing import Callable, Optional
import uuid
import logging
from pathlib import Path

from .components.header import Header
from .components.control_bar import ControlBar
from .components.input_field import InputField, ContextLabel
from .components.response_preview import ResponsePreview
from .components.chunk_dropdown import ChunkDropdown
from .signals import UISignals
from .workers import QueryWorker

class DasiWindow(QWidget):
    """Main popup window for Dasi."""
    def __init__(self, process_query: Callable[[str], str], signals: UISignals, settings):
        # Initialize session ID
        self.session_id = str(uuid.uuid4())
        
        super().__init__()
        self.process_query = process_query
        self.signals = signals
        self.settings = settings
        self.old_pos = None
        self.worker = None
        self.selected_text = None  # Store selected text
        self.last_response = None  # Store last response
        self.conversation_context = {}  # Store conversation context
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'

        # Window flags
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                          Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._setup_ui()
        self._setup_chunk_dropdown()

    def _setup_ui(self):
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

        # Add header
        self.header = Header(self._handle_escape, self._handle_reset_session)
        frame_layout.addWidget(self.header)

        # Content area with horizontal layout
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)

        # Left side - Input area
        left_panel = QFrame()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        # Add context label
        self.context_label = ContextLabel()
        self.context_label.ignore_button.clicked.connect(self.reset_context)
        left_layout.addWidget(self.context_label)

        # Add input field
        self.input_field = InputField(self.chunks_dir)
        self.input_field.submit_triggered.connect(self._handle_submit)
        left_layout.addWidget(self.input_field, 1)

        # Add control bar
        self.control_bar = ControlBar(self.settings)
        self.control_bar.mode_changed.connect(self._handle_mode_change)
        left_layout.addWidget(self.control_bar)

        # Loading progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.hide()
        left_layout.addWidget(self.progress_bar)

        left_panel.setLayout(left_layout)

        # Right side - Preview and buttons
        self.right_panel = QFrame()
        self.right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        # Add response preview
        self.response_preview = ResponsePreview()
        right_layout.addWidget(self.response_preview, 1)

        # Action buttons frame
        self.action_frame = QFrame()
        action_layout = QVBoxLayout()
        action_layout.setContentsMargins(5, 0, 5, 5)

        # Create stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self._handle_stop)
        self.stop_button.hide()
        action_layout.addWidget(self.stop_button)

        # Create insertion method selector
        self.insert_method = QComboBox()
        self.insert_method.setObjectName("insertMethod")
        self.insert_method.addItem("⚡ Copy/Paste", "paste")
        self.insert_method.addItem("⌨ Type Text", "type")
        action_layout.addWidget(self.insert_method)

        # Create accept/reject buttons layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)

        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self._handle_accept)
        self.reject_button = QPushButton("Reject")
        self.reject_button.clicked.connect(self._handle_reject)

        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.reject_button)
        action_layout.addLayout(button_layout)

        self.action_frame.setLayout(action_layout)
        right_layout.addWidget(self.action_frame)
        self.right_panel.setLayout(right_layout)
        self.right_panel.hide()

        # Add panels to content layout
        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(self.right_panel, 0)

        # Add content to main frame
        frame_layout.addLayout(content_layout)
        self.main_frame.setLayout(frame_layout)
        layout.addWidget(self.main_frame)
        self.setLayout(layout)

        # Set up styling
        self._setup_styles()

    def _setup_chunk_dropdown(self):
        """Set up the chunk selection dropdown."""
        self.chunk_dropdown = ChunkDropdown(self.input_field)
        self.chunk_dropdown.itemSelected.connect(self._insert_chunk)
        self.update_chunk_titles()

    def _setup_styles(self):
        """Set up window styles."""
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
            #rightPanel {
                background-color: #323232;
                border-radius: 5px;
                padding: 5px;
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
            QProgressBar {
                border: none;
                background-color: #363636;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
            }
        """)

    def update_chunk_titles(self):
        """Update the list of available chunk titles."""
        self.chunk_titles = []
        if self.chunks_dir.exists():
            for file_path in self.chunks_dir.glob("*.md"):
                title = file_path.stem
                self.chunk_titles.append(title)
        
        # Update input field highlighter
        self.input_field.update_chunks_dir(self.chunks_dir)

    def _insert_chunk(self, chunk_title: str):
        """Insert the selected chunk at cursor position."""
        # This is now handled by the InputField component
        pass

    def reset_context(self):
        """Reset all context including selected text and last response."""
        self.selected_text = None
        self.last_response = None
        self.conversation_context = {}
        self.context_label.hide()

    def set_selected_text(self, text: str):
        """Set the selected text and update UI."""
        self.selected_text = text
        self.context_label.set_text(text)

    def _handle_escape(self):
        """Handle escape key press."""
        self.hide()
        self.input_field.clear_text()
        self.reset_context()
        self.right_panel.hide()
        self.setFixedWidth(320)
        # Clear clipboard selection
        clipboard = QApplication.clipboard()
        clipboard.clear(QClipboard.Mode.Selection)

    def _handle_stop(self):
        """Handle stop button click."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.terminate()
            self.worker.wait()
            # Re-enable input field with existing content
            self.input_field.setEnabled(True)
            # Hide loading indicators
            self.progress_bar.hide()
            self.stop_button.hide()
            # Show appropriate buttons based on mode
            if self.control_bar.is_compose_mode():
                self.insert_method.show()
                self.accept_button.show()
                self.reject_button.show()

    def _handle_submit(self):
        """Handle submit action."""
        query = self.input_field.get_text()
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

            # Add mode to context
            context['mode'] = 'compose' if self.control_bar.is_compose_mode() else 'chat'

            # Format query with context
            if context:
                full_query = "Context:\n"
                if 'selected_text' in context:
                    full_query += f"Selected Text:\n{context['selected_text']}\n\n"
                full_query += f"Mode: {context['mode']}\n\n"
                full_query += f"Query:\n{query}"
            else:
                full_query = query

            # Get selected model
            model = self.control_bar.get_selected_model()
            model_id = model['id'] if model else None

            # Process query in background with session ID
            self.worker = QueryWorker(
                self.process_query, full_query, self.signals, model_id, self.session_id)
            self.worker.start()

    def _handle_mode_change(self, is_compose: bool):
        """Handle mode change between Chat and Compose."""
        if is_compose:
            self.insert_method.show()
            self.accept_button.show()
            self.reject_button.show()
        else:
            self.insert_method.hide()
            self.accept_button.hide()
            self.reject_button.hide()

    def _handle_accept(self):
        """Accept the generated response."""
        response = self.response_preview.get_text()
        if response:
            self.hide()
            self.input_field.clear_text()
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

            # Reset response preview to read-only state
            self.response_preview.set_editable(False)

        self.right_panel.hide()
        self.setFixedWidth(320)

    def _handle_reject(self):
        """Reject the generated response."""
        # Hide response preview, buttons and right panel
        self.right_panel.hide()
        self.setFixedWidth(320)

        if not self.control_bar.is_compose_mode():
            self.reset_context()
        else:
            # In compose mode, only clear the last response
            self.last_response = None
            # Hide context label if there's no selected text
            if not self.selected_text:
                self.context_label.hide()

        # Focus input field
        self.input_field.setFocus()

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
            
        self.input_field.clear_text()
        self.response_preview.clear_text()
        self.right_panel.hide()
        self.setFixedWidth(320)
        # Hide reset button since history is now cleared
        self.header.hide_reset_button()

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

    def keyPressEvent(self, event):
        """Handle global key events for the window."""
        if event.key() == Qt.Key.Key_Escape:
            self._handle_escape()
        else:
            super().keyPressEvent(event)

    def _handle_response(self, response: str):
        """Handle query response (runs in main thread)."""
        # Check for completion signal
        if response == "<COMPLETE>":
            self.progress_bar.hide()
            self.stop_button.hide()
            
            # Clear and re-enable input field only on successful completion
            self.input_field.clear_text()
            self.input_field.setEnabled(True)
            
            # Show reset session button since we now have history
            self.header.show_reset_button()
            
            if self.control_bar.is_compose_mode():
                # Make response preview editable in compose mode
                self.response_preview.set_editable(True)
                # Show action buttons
                self.insert_method.show()
                self.accept_button.show()
                self.reject_button.show()
            return

        # Store the response
        self.last_response = response

        # Show response preview
        self.response_preview.append_text(response)
        self.response_preview.show()

        # Show action buttons and right panel
        self.action_frame.show()
        if self.control_bar.is_compose_mode():
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

    def _handle_error(self, error_msg: str):
        """Handle query error."""
        # Hide loading state
        self.progress_bar.hide()
        self.stop_button.hide()
        # Re-enable input field with existing content
        self.input_field.setEnabled(True)

        # Show error in preview
        self.response_preview.clear_text()
        self.response_preview.append_text(f"Error: {error_msg}")
        self.response_preview.show()

        # Show reject button only
        self.action_frame.show()
        self.accept_button.hide()
        self.reject_button.show()
        self.right_panel.show()

        # Adjust window size
        self.setFixedWidth(650)
