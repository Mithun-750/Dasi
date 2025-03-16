from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QClipboard
from typing import Callable
import sys
import logging
from .window import DasiWindow
from ..components.ui_signals import UISignals


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
            
            # Calculate the total width when expanded with response panel
            # The window starts at 340px width and expands to 680px when showing response
            expanded_width = 680  # Total width when response panel is shown
            
            # Calculate the position to ensure there's enough space on the right
            # If we're too close to the right edge, shift left to make room for response panel
            right_edge_distance = screen.width() - x
            if right_edge_distance < expanded_width:
                # Shift left to ensure the expanded window fits on screen
                x = max(0, screen.width() - expanded_width)
            else:
                # Add a small offset from cursor position
                x = max(0, x + 10)
            
            # Ensure the window is within screen bounds
            x = min(x, screen.width() - self.window.width())
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
        self.window.setFixedSize(340, 350)
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