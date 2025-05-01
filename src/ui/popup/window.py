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

# Import LangGraphHandler directly from core
from core.langgraph_handler import LangGraphHandler
from core.instance_manager import DasiInstanceManager  # Import DasiInstanceManager

# Import components
from .components.input_panel import InputPanel
from .components.web_search import WebSearchPanel
from .components.preview_panel import PreviewPanel
from .components.confirmation_panel import ConfirmationPanel
from .components.loading_panel import LoadingPanel
from core.tools.tool_call_handler import ToolCallHandler


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

        # Use shared tool call handler from instance manager
        self.tool_call_handler = DasiInstanceManager.get_tool_call_handler()
        self.confirmation_panel = None
        self.current_loading_panel = None  # Add this to track the active loading panel

        # Window flags
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.setup_ui()
        self._setup_tool_call_signals()

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
        self.reset_session_button = QPushButton()
        self.reset_session_button.setObjectName("resetSessionButton")
        self.reset_session_button.setProperty("class", "header-button")
        self.reset_session_button.clicked.connect(self._handle_reset_session)
        self.reset_session_button.setFixedSize(24, 24)
        self.reset_session_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Set tooltip for the reset button
        self.reset_session_button.setToolTip("Reset Session")
        # Add trash bin icon using text as a unicode character since we're not loading external resources
        self.reset_session_button.setText("🗑️")
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
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Set a fixed size for the stop button to prevent expansion issues
        self.stop_button.setFixedWidth(330)
        self.stop_button.setFixedHeight(30)
        self.stop_button.setStyleSheet("""
            QPushButton#stopButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 8px;
                min-height: 18px;
                max-height: 18px;
            }
            QPushButton#stopButton:hover {
                background-color: #ef4444;
            }
            QPushButton#stopButton:pressed {
                background-color: #b91c1c;
            }
        """)
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
                background-color: transparent;
                color: #888888;
                font-size: 14px;
                margin-top: 2px;
                padding: 0px;
                margin-right: 6px;
                font-weight: bold;
                border: none;
                border-radius: 12px;
                text-align: center;
                line-height: 24px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
            }
            #resetSessionButton:hover {
                background-color: transparent;
                color: #ffffff;
                border: none;
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

    def _handle_input_submit(self, query: str, model_info=None):
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

            # Format query with context (except image_data)
            full_query = "Context:\n"
            if 'selected_text' in context:
                full_query += f"=====SELECTED_TEXT=====<text selected by the user>\n{context['selected_text']}\n=======================\n\n"

            # CHANGE: Don't include image_data in the query text!
            # Instead, extract it for direct passing to the worker
            image_data = None
            if 'image_data' in context:
                image_data = context['image_data']
                # Add a note about image presence but don't include the actual base64 data
                full_query += f"=====IMAGE=====<image data is attached separately>\n=====================\n\n"

            full_query += f"=====MODE=====<user selected mode>\n{context['mode']}\n=======================\n\n"
            full_query += f"Query:\n{query}"

            # Get model ID from the model_info parameter
            model = None
            if model_info and 'id' in model_info:
                model = model_info['id']
                logging.info(f"Using selected model: {model}")

            # Process query in background with session ID
            self.worker = QueryWorker(
                self.process_query, full_query, self.signals, model, self.session_id, image_data)
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
        self.right_panel.show()

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
            self.input_panel.set_focus()

            # Show reset session button since we now have history
            self.reset_session_button.show()

            if self.input_panel.is_compose_mode():
                # For compose mode, process the response to handle backticks but preserve language
                self.preview_panel.process_final_response()

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

    def _handle_export(self):
        """Handle export button click."""
        if self.last_response:
            try:
                # Use LangGraphHandler directly for filename suggestion
                # Get the handler instance from the main application
                # Note: This assumes a way to access the main app's handler instance.
                # If DasiInstanceManager is used, we can get it from there.
                dasi_instance = DasiInstanceManager.get_instance()
                if dasi_instance and hasattr(dasi_instance, 'llm_handler') and isinstance(dasi_instance.llm_handler, LangGraphHandler):
                    langgraph_handler = dasi_instance.llm_handler
                else:
                    # Fallback: Create a temporary instance if needed (not ideal)
                    logging.warning(
                        "Could not get main LangGraphHandler instance, creating temporary one for filename suggestion.")
                    langgraph_handler = LangGraphHandler()

                # Use the handler's method
                suggested_filename = langgraph_handler.suggest_filename(
                    self.last_response, self.session_id)

                # Rest of the export logic...
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "Export Response", suggested_filename, "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)")

                if save_path:
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(self.last_response)
                    logging.info(f"Response exported to {save_path}")
            except Exception as e:
                logging.error(f"Error exporting file: {str(e)}", exc_info=True)
                QMessageBox.warning(self, "Export Error",
                                    f"Failed to export file: {str(e)}")

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

        # Store current input text
        current_input_text = self.input_panel.get_query()

        # Generate new session ID
        self.session_id = str(uuid.uuid4())
        # Clear conversation history in LLM handler
        self.process_query(f"!clear_session:{self.session_id}")

        # Reset UI but preserve selected text
        self.reset_context()
        if current_selected_text:
            self.input_panel.set_selected_text(current_selected_text)

        # Don't clear the input field - removed: self.input_panel.clear_input()
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

    def _setup_tool_call_signals(self):
        """Connect tool call handler signals to UI slots."""
        self.tool_call_handler.tool_call_requested.connect(
            self._show_confirmation_panel)
        self.tool_call_handler.tool_call_accepted.connect(
            self._show_loading_panel)
        self.tool_call_handler.tool_call_completed.connect(
            self._handle_tool_call_completed)
        self.tool_call_handler.tool_call_processing.connect(
            self._handle_tool_call_processing)

    def _show_confirmation_panel(self, tool_call_info):
        """Show the confirmation panel for a tool call."""
        # Hide other panels
        self.preview_panel.hide()
        self.web_search_panel.hide()
        self.stop_button.hide()
        # Remove old confirmation panel if present
        if self.confirmation_panel:
            self.right_layout.removeWidget(self.confirmation_panel)
            self.confirmation_panel.deleteLater()
            self.confirmation_panel = None
        # Create and show new confirmation panel
        self.confirmation_panel = ConfirmationPanel(
            tool_call_info["tool"], tool_call_info["args"])
        self.confirmation_panel.accepted.connect(
            lambda: self.tool_call_handler.handle_user_response(True))
        self.confirmation_panel.rejected.connect(
            lambda: self.tool_call_handler.handle_user_response(False))
        self.right_layout.insertWidget(0, self.confirmation_panel)
        self.confirmation_panel.show()
        self.right_panel.show()
        # Use wider width like web search panel for better display
        self.setFixedWidth(680)

    def _show_loading_panel(self, tool_call_info):
        """Show the loading panel immediately after tool call acceptance."""
        tool = tool_call_info.get("tool", "unknown")

        # Remove confirmation panel if it exists
        if self.confirmation_panel:
            self.right_layout.removeWidget(self.confirmation_panel)
            self.confirmation_panel.deleteLater()
            self.confirmation_panel = None

        # Remove any previous loading panel just in case
        if self.current_loading_panel:
            self._remove_loading_panel(self.current_loading_panel)

        # Create and show the new loading panel
        loading_panel = LoadingPanel(tool)
        self.current_loading_panel = loading_panel  # Store reference
        self.right_layout.insertWidget(0, loading_panel)
        loading_panel.show()
        self.right_panel.show()

        # Connect loading panel's finished signal to remove it when done
        loading_panel.finished.connect(
            lambda lp=loading_panel: self._remove_loading_panel(lp))

        # Set fixed width
        self.setFixedWidth(680)

    def _handle_tool_call_completed(self, result_info):
        """Handle completion of a tool call (update the loading panel)."""
        # If a loading panel exists, update its state
        if self.current_loading_panel:
            # Mark loading as complete
            self.current_loading_panel.show_complete()
        else:
            # This case shouldn't happen with the new flow, but log if it does
            logging.warning("Tool call completed but no loading panel found.")
            # Fallback: Ensure preview panel is visible for the response
            self.preview_panel.show_preview(True)
            self.preview_panel.show()
            self.right_panel.show()
            self.setFixedWidth(680)

    def _remove_loading_panel(self, loading_panel):
        """Remove the loading panel from the layout."""
        if loading_panel:
            self.right_layout.removeWidget(loading_panel)
            loading_panel.deleteLater()
            if self.current_loading_panel == loading_panel:
                self.current_loading_panel = None

        # After removing the loading panel, ensure the preview panel is visible
        # This allows the next streamed LLM response (that interprets the tool results) to be seen
        self.preview_panel.show_preview(True)
        self.preview_panel.show()
        self.right_panel.show()  # Ensure right panel is shown
        self.setFixedWidth(680)  # Ensure correct width

    def _handle_tool_call_processing(self, tool_name):
        """Handle the signal that the LLM is processing tool results."""
        logging.info(f"LLM is processing {tool_name} results")

        # Ensure the preview panel is visible and ready to receive the LLM's follow-up response
        self.preview_panel.set_response(
            "Processing tool results...\nGenerating response...")
        self.preview_panel.show()
        self.preview_panel.show_preview(True)

        # Make right panel visible if not already
        self.right_panel.show()

        # Adjust window width consistently with other tool operations
        self.setFixedWidth(680)
