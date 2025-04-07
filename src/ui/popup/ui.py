from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QClipboard
from PyQt6.QtCore import QTimer, QEvent, Qt
from typing import Callable
import sys
import logging
import platform
import time
import pythoncom
from .window import DasiWindow
from ..components.ui_signals import UISignals


class CopilotUI:
    # Signal handler method - runs on the main thread
    def _show_window(self, x: int, y: int):
        """Show window at specified coordinates (runs in main thread)."""
        try:
            # Ensure window exists
            if not hasattr(self, 'window') or self.window is None:
                logging.error("Window reference missing. Cannot show.")
                return

            # Reset window state
            self.window.reset_context()
            self.window.input_panel.clear_input()

            # Handle clipboard reading on the main thread
            self._get_selected_text()  # Reads clipboard safely

            # Calculate screen-safe position
            screen = self.app.primaryScreen().geometry()
            window_width = self.window.width() if self.window.width(
            ) > 0 else 340  # Use default if width is 0
            window_height = self.window.height() if self.window.height(
            ) > 0 else 350  # Use default if height is 0
            x = min(max(x + 10, 0), screen.width() - window_width)
            y = min(max(y + 10, 0), screen.height() - window_height)

            # Position the window
            self.window.move(x, y)

            # Show, activate, raise, and focus - standard sequence
            self.window.show()
            self.window.activateWindow()  # Make it the active window
            self.window.raise_()         # Bring it to the front
            # Set keyboard focus to input field
            self.window.input_panel.input_field.setFocus()

            # Minimal Windows-specific enhancement (optional, but can help)
            if platform.system() == 'Windows':
                try:
                    # Gently try to ensure foreground status
                    import ctypes
                    hwnd = int(self.window.winId())
                    if hwnd:
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception as e:
                    logging.debug(f"Non-critical Windows API error: {str(e)}")

        except Exception as e:
            logging.error(f"Error showing window: {str(e)}", exc_info=True)

    def _get_selected_text(self):
        """Get selected text (runs on main thread) with COM init/uninit for Windows."""
        selected_text_result = ""
        com_initialized = False
        try:
            if platform.system() == 'Windows':
                try:
                    pythoncom.CoInitialize()
                    com_initialized = True
                except Exception as e:
                    logging.debug(f"COM initialization failed: {str(e)}")

            clipboard = QApplication.clipboard()
            if clipboard:
                # Try standard clipboard first
                clipboard_text = clipboard.text(QClipboard.Mode.Clipboard)
                if clipboard_text and len(clipboard_text.strip()) >= 4:
                    selected_text_result = clipboard_text.strip()
                    logging.debug(
                        f"Using clipboard text: {selected_text_result[:30]}...")
                else:
                    # Then try selection buffer (less reliable on Windows but worth trying)
                    selection_text = clipboard.text(QClipboard.Mode.Selection)
                    if selection_text and len(selection_text.strip()) >= 4:
                        selected_text_result = selection_text.strip()
                        logging.debug(
                            f"Using selection text: {selected_text_result[:30]}...")

            # Set the text in the UI if found
            if selected_text_result:
                if hasattr(self, 'window') and self.window is not None:
                    self.window.set_selected_text(selected_text_result)

        except Exception as e:
            logging.error(
                f"Error getting selected text: {str(e)}", exc_info=True)
        finally:
            if com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception as e:
                    logging.debug(f"COM uninitialization failed: {str(e)}")

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
        self.window.hide()  # Start hidden

        # Connect signals
        self.signals.show_window.connect(
            self._show_window)  # Connect signal to the slot
        self.signals.process_response.connect(self.window._handle_response)
        self.signals.process_error.connect(self.window._handle_error)

    def show_popup(self, x: int, y: int):
        """Trigger the signal to show the popup window (thread-safe)."""
        # This method is called from the hotkey listener thread.
        # Emitting the signal marshals the call to the main UI thread.
        self.signals.show_window.emit(x, y)

    def run(self):
        """Start the UI event loop."""
        self.app.exec()
