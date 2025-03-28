from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QFrame, QLabel, QPushButton, QHBoxLayout, QFileDialog, QMessageBox)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal)
from PyQt6.QtGui import QFont, QClipboard, QPixmap
from typing import Callable,  List
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

# Import components
from .components.input_panel import InputPanel
from .components.web_search import WebSearchPanel
from .components.preview_panel import PreviewPanel


class DasiWindow(QWidget):
    def reset_context(self):
        """Reset all context including selected text and last response."""
        self.last_response = None
        self.conversation_context = {}
        self.input_panel.reset_context()

    def set_selected_text(self, text: str):
        """Set the selected text and update UI."""
        self.input_panel.set_selected_text(text)

    """Main popup window for Dasi."""

    def __init__(self, process_query: Callable[[str], str], signals: UISignals):
        # Initialize session ID
        self.session_id = str(uuid.uuid4())

        super().__init__()
        self.process_query = process_query
        self.signals = signals
        self.old_pos = None
        self.worker = None
        self.last_response = None  # Store last response
        self.conversation_context = {}  # Store conversation context
        self.settings = Settings()  # Initialize settings
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'
        self.is_web_search = False  # Flag to track if current query is a web search

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
        self.main_frame.setProperty("class", "card")
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Header with logo and title
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 8, 10, 8)
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
            base_path = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))

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
            scaled_pixmap = pixmap.scaled(
                20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logging.warning("Logo not found")

        # Title with custom font
        title = QLabel("Dasi")
        title.setObjectName("titleLabel")
        title.setProperty("class", "header-title")

        # Add reset session button before close button
        self.reset_session_button = QPushButton("Reset Session")
        self.reset_session_button.setObjectName("resetSessionButton")
        self.reset_session_button.setProperty("class", "header-button")
        self.reset_session_button.clicked.connect(self._handle_reset_session)
        self.reset_session_button.setFixedWidth(100)
        self.reset_session_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_session_button.hide()  # Hide by default

        # Add close button
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setProperty("class", "header-button")
        close_button.clicked.connect(self._handle_escape)
        close_button.setFixedSize(24, 24)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.reset_session_button)
        header_layout.addWidget(close_button)
        header.setLayout(header_layout)

        # Content area with horizontal layout
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        # Left side - Input area (now using InputPanel component)
        self.input_panel = InputPanel()
        self.input_panel.submit_query.connect(self._handle_input_submit)
        self.input_panel.mode_changed.connect(self._handle_mode_change)

        # Right side - Preview and buttons
        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")
        right_panel.setProperty("class", "transparent-container")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self.right_layout = right_layout  # Store reference to the layout

        # Set a fixed width for the right panel to ensure consistency
        right_panel.setFixedWidth(360)  # Increased from 330px to 360px

        # Create stop button (hidden by default)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setProperty("class", "danger")
        self.stop_button.setStyleSheet("margin: 8px 0;")
        self.stop_button.clicked.connect(self._handle_stop)
        self.stop_button.hide()

        # Create preview panel
        self.preview_panel = PreviewPanel()
        self.preview_panel.use_clicked.connect(self._handle_use)
        self.preview_panel.export_clicked.connect(self._handle_export)

        # Ensure the preview panel has enough height for dropdown expansion
        self.preview_panel.setMinimumHeight(200)

        # Web search loading panel (hidden by default)
        self.web_search_panel = WebSearchPanel()
        self.web_search_panel.search_stopped.connect(self._handle_stop)
        self.web_search_panel.hide()

        # Add elements to right panel
        right_layout.addWidget(self.preview_panel)  # Remove stretch factor
        right_layout.addWidget(self.web_search_panel)  # Remove stretch factor
        right_layout.addWidget(self.stop_button)  # Move stop button to bottom
        right_panel.setLayout(right_layout)
        right_panel.hide()
        self.right_panel = right_panel

        # Add panels to content layout
        content_layout.addWidget(self.input_panel, 1)
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
                color: #e0e0e0;
            }
            .card {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
            #mainFrame {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
            #header {
                background-color: #222222;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #333333;
            }
            #logoLabel {
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            .header-title, #titleLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 600;
                font-size: 15px;
                letter-spacing: 0.5px;
            }
            .header-button {
                border-radius: 4px;
                border: none;
            }
            #closeButton {
                background-color: transparent;
                color: #888888;
                font-size: 20px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                border-radius: 12px;
                text-align: center;
                line-height: 20px;
            }
            #closeButton:hover {
                color: #ffffff;
            }
            #rightPanel {
                background-color: transparent;
                padding: 0;
            }
            #contextFrame {
                background: transparent;
            }
            #contextLabel {
                color: #888888;
                font-size: 11px;
                padding: 6px 8px;
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
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton.primary {
                background-color: #2b5c99;
            }
            QPushButton.primary:hover {
                background-color: #366bB3;
            }
            QPushButton.danger, #stopButton {
                background-color: #99322b;
            }
            QPushButton.danger:hover, #stopButton:hover {
                background-color: #b33e36;
            }
            #resetSessionButton {
                background-color: rgba(42, 42, 42, 0.5);
                color: #cccccc;
                font-size: 11px;
                padding: 5px 10px;
                margin-right: 6px;
                font-weight: 500;
                letter-spacing: 0.3px;
                border: 1px solid rgba(80, 80, 80, 0.3);
            }
            #resetSessionButton:hover {
                background-color: #e67e22;
                color: white;
                border: 1px solid #e67e22;
            }
            QProgressBar {
                border: none;
                background-color: #2a2a2a;
                border-radius: 1px;
                height: 2px;
            }
            QProgressBar::chunk {
                background-color: #2b5c99;
            }
        """)

    def _handle_input_submit(self, query: str):
        """Handle query submitted from the input panel."""
        if query:
            # Check if this is a web search query (check for #web anywhere in the query)
            self.is_web_search = "#web" in query.lower()

            # Show stop button at bottom
            if not self.is_web_search:
                self.stop_button.show()

            # Hide preview panel actions
            self.preview_panel.show_actions(False)

            # Show web search panel for web searches
            if self.is_web_search:
                # Hide the response preview and show the web search panel
                self.preview_panel.hide()  # Hide preview panel completely
                # Get search term by removing the #web tag
                search_term = query.lower().replace("#web", "", 1).strip()
                self.web_search_panel.start(search_term)
                self.right_panel.show()
                self.setFixedWidth(680)  # Wider width for web search panel
            else:
                # Regular query - hide web search panel
                self.web_search_panel.hide()
                self.preview_panel.show()  # Show preview panel

            # Build context dictionary
            context = self.input_panel.get_context()

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
            model_info = self.input_panel.get_selected_model()
            model = None
            if model_info and 'id' in model_info:
                model = model_info['id']

            # Process query in background with session ID
            self.worker = QueryWorker(
                self.process_query, full_query, self.signals, model, self.session_id)
            self.worker.start()

    def _reset_ui_after_stop(self):
        """Reset UI elements after stopping an operation."""
        # Re-enable input field
        self.input_panel.enable_input(True)

        # Hide loading indicators
        self.input_panel.show_progress(False)
        self.stop_button.hide()

        # Stop web search panel if it's active
        self.web_search_panel.stop()
        self.web_search_panel.hide()  # Hide web search panel

        # Show preview panel
        self.preview_panel.show()
        self.preview_panel.show_preview(False)
        self.right_panel.hide()
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
                            dasi_instance.llm_handler.web_search_handler.cancel_search()
                        else:
                            logging.warning(
                                "Could not access web search handler for cancellation")
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
                        dasi_instance.llm_handler.web_search_handler.cancel_search()

                        # Signal worker to stop
                        self.worker.stop()

                        # Use the safer termination method with timeout
                        self.worker.terminate_safely()
                except Exception as e:
                    logging.error(
                        f"Error cancelling web search on ESC: {str(e)}")

            # Reset UI elements
            self._reset_ui_after_stop()

            # Additionally for escape, hide the window and clear input
            self.hide()
            self.input_panel.clear_input()
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

    def _handle_mode_change(self, is_compose: bool):
        """Handle mode change between Chat and Compose."""
        # Show/hide action elements based on mode
        if is_compose:
            # Use plain text for compose mode
            self.preview_panel.set_chat_mode(False)
            self.preview_panel.show_actions(True)
        else:
            self.preview_panel.set_chat_mode(
                True)  # Use markdown for chat mode
            self.preview_panel.show_actions(False)

    def _handle_error(self, error_msg: str):
        """Handle query error."""
        # Hide loading state
        self.input_panel.show_progress(False)
        self.stop_button.hide()

        # Stop web search panel if it's active
        self.web_search_panel.stop()

        # Re-enable input field with existing content
        self.input_panel.enable_input(True)

        # Show error in preview
        self.preview_panel.set_response(f"Error: {error_msg}")
        self.preview_panel.show_preview(True)
        self.preview_panel.show_actions(True)
        self.preview_panel.accept_button.hide()  # Hide accept button for errors
        self.right_panel.show()

        # Adjust window size
        self.setFixedHeight(250)

    def _handle_response(self, response: str):
        """Handle query response (runs in main thread)."""
        # Check for completion signal
        if response == "<COMPLETE>":
            self.input_panel.show_progress(False)
            self.stop_button.hide()

            # Stop web search panel if it's active
            self.web_search_panel.stop()

            # Reset web search flag
            self.is_web_search = False

            # Clear and re-enable input field only on successful completion
            self.input_panel.clear_input()
            self.input_panel.enable_input(True)

            # Show reset session button since we now have history
            self.reset_session_button.show()

            if self.input_panel.is_compose_mode():
                # Make response preview editable in compose mode
                self.preview_panel.set_editable(True)
                self.preview_panel.show_actions(True)
            else:
                # For chat mode, ensure we're using markdown renderer
                self.preview_panel.set_chat_mode(True)
            return

        # Store the response
        self.last_response = response

        # Check for optimized search query information in web search responses
        if self.is_web_search and self.web_search_panel.isVisible():
            # Look for the original and optimized query information
            # This would be in the format that the LLMHandler puts into the response
            original_query_match = re.search(
                r"Original Query: (.+)$", response, re.MULTILINE)
            optimized_query_match = re.search(
                r"Optimized Query: (.+)$", response, re.MULTILINE)

            if original_query_match and optimized_query_match:
                original_query = original_query_match.group(1).strip()
                optimized_query = optimized_query_match.group(1).strip()

                # Update the web search panel with the optimized query
                self.web_search_panel.update_with_optimized_query(
                    original_query, optimized_query)

        # If we were showing the web search panel and have a substantial response, hide it
        if self.is_web_search and self.web_search_panel.isVisible():
            # Only hide the web search panel when we have a substantial response
            # This prevents flickering between loading and very short initial responses
            if len(response) > 50:
                self.web_search_panel.stop()
                self.web_search_panel.hide()  # Hide web search panel
                self.preview_panel.show()  # Show preview panel

        # Show response preview (as read-only during streaming)
        self.preview_panel.set_response(response)
        self.preview_panel.set_editable(False)
        self.preview_panel.show_preview(True)
        self.right_panel.show()

        # During streaming, only show stop button at bottom
        self.preview_panel.show_actions(False)
        self.stop_button.show()

        # Adjust window size - keep consistent with web search width
        # Increased from 650px to 680px to accommodate the wider right panel
        self.setFixedWidth(680)

    def _handle_use(self, method: str, response: str):
        """Handle using the response - either by copying/pasting or typing it out."""
        self.hide()
        self.input_panel.clear_input()
        self.reset_context()
        # Clear clipboard selection
        clipboard = QApplication.clipboard()
        clipboard.clear(QClipboard.Mode.Selection)

        # Format query with method and response
        query = f"!{method}:{response}"

        # Process the response with selected method
        self.process_query(query)

        # Reset response preview to read-only state
        self.preview_panel.set_editable(False)

        self.right_panel.hide()

        # Reset window size
        self.setFixedWidth(340)  # Input-only mode width

    def _handle_export(self, response: str):
        """Export the generated response to a markdown file."""
        # Show loading state in the export button
        original_text = self.preview_panel.export_button.text()
        self.preview_panel.export_button.setText("Cancel")

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
            self.preview_panel.export_button.setText(original_text)
            self.preview_panel.export_button.setEnabled(True)
            # Restore the original click handler
            self.preview_panel.export_button.clicked.disconnect()
            self.preview_panel.export_button.clicked.connect(
                self.preview_panel._handle_export)

            try:
                # Get the default export path from settings
                default_path = self.settings.get(
                    'general', 'export_path', default=os.path.expanduser("~/Documents"))

                # Combine default path with suggested filename
                default_filepath = os.path.join(
                    default_path, suggested_filename)

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
        self.preview_panel.export_button.clicked.disconnect()
        self.preview_panel.export_button.clicked.connect(self._cancel_export)

        # Start the worker
        self.filename_worker.start()

    def _cancel_export(self):
        """Cancel the export operation."""
        if hasattr(self, 'filename_worker') and self.filename_worker.isRunning():
            self.filename_worker.stop()
            self.filename_worker.wait()

            # Restore export button
            self.preview_panel.export_button.setText("Export")
            self.preview_panel.export_button.clicked.disconnect()
            self.preview_panel.export_button.clicked.connect(
                self.preview_panel._handle_export)

    def _handle_export_error(self, response: str):
        """Handle export errors by falling back to timestamp-based filename."""
        try:
            # Restore button state
            self.preview_panel.export_button.setText("Export")
            self.preview_panel.export_button.clicked.disconnect()
            self.preview_panel.export_button.clicked.connect(
                self.preview_panel._handle_export)
            self.preview_panel.export_button.setEnabled(True)

            # Use timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suggested_filename = f"dasi_response_{timestamp}.md"
            default_path = self.settings.get(
                'general', 'export_path', default=os.path.expanduser("~/Documents"))
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
            logging.error(
                f"Error during export fallback: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export response: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def keyPressEvent(self, event):
        """Handle global key events for the window."""
        if event.key() == Qt.Key.Key_Escape:
            self._handle_escape()
        # Add global Shift+Backspace handler to reset selected text
        elif event.key() == Qt.Key.Key_Backspace and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.input_panel.reset_context()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _handle_reset_session(self):
        """Handle reset session button click."""
        # Store current selected text
        current_selected_text = self.input_panel.selected_text

        # Generate new session ID
        self.session_id = str(uuid.uuid4())
        # Clear conversation history in LLM handler
        self.process_query(f"!clear_session:{self.session_id}")

        # Reset UI but preserve selected text
        self.reset_context()
        if current_selected_text:
            self.input_panel.set_selected_text(current_selected_text)

        self.input_panel.clear_input()
        self.preview_panel.clear()
        self.right_panel.hide()
        self.setFixedWidth(340)  # Input-only mode width
        # Hide reset button since history is now cleared
        self.reset_session_button.hide()

    def showEvent(self, event):
        """Called when the window becomes visible."""
        super().showEvent(event)
        # Update chunk titles when window is shown
        self.input_panel.update_chunk_titles()

    def hideEvent(self, event):
        """Handle hide event to clean up resources."""
        # Make sure all animations are stopped
        self.web_search_panel.stop()

        super().hideEvent(event)
