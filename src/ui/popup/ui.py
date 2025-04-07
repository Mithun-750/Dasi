from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QClipboard
from PyQt6.QtCore import QTimer, QEvent, Qt
from typing import Callable
import sys
import logging
import platform
import time
from .window import DasiWindow
from ..components.ui_signals import UISignals


class CopilotUI:
    def _show_window(self, x: int, y: int):
        """Show window at specified coordinates (runs in main thread)."""
        try:
            # First reset all context and input
            self.window.reset_context()
            self.window.input_panel.clear_input()

            # Get selected text from clipboard
            clipboard = QApplication.clipboard()
            selected_text = clipboard.text(QClipboard.Mode.Selection)

            # Only set selected text if there's new text selected and it's at least 4 characters
            if selected_text and selected_text.strip() and len(selected_text.strip()) >= 4:
                self.window.set_selected_text(selected_text.strip())

            # Position window near cursor with screen bounds check
            screen = self.app.primaryScreen().geometry()
            x = min(max(x + 10, 0), screen.width() - self.window.width())
            y = min(max(y + 10, 0), screen.height() - self.window.height())

            # Move the window first (without showing)
            self.window.move(x, y)

            # Optimized window showing sequence for Windows
            if platform.system() == 'Windows':
                # For Windows, use a specific sequence for better focus handling

                # 1. First move and show without activating
                # This prevents Windows' focus-stealing prevention from kicking in
                self.window.setAttribute(
                    Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                self.window.show()

                # 2. Then, after a minimal delay, forcefully activate the window
                # This sequence works better on Windows
                QTimer.singleShot(30, lambda: self._activate_window_windows())
            else:
                # Standard approach for other platforms
                self.window.show()
                self.window.activateWindow()
                self.window.raise_()
                self.window.input_panel.input_field.setFocus()

        except Exception as e:
            logging.error(f"Error showing window: {str(e)}", exc_info=True)

    def _activate_window_windows(self):
        """Special activation sequence for Windows"""
        try:
            # 1. First make sure we're not showing without activating anymore
            self.window.setAttribute(
                Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

            # 2. Then activate the window and raise it to the top
            self.window.activateWindow()
            self.window.raise_()

            # 3. Force the window to be the foreground window using Windows-specific APIs
            try:
                import ctypes
                # Get the window ID
                window_id = self.window.winId()
                # Use SetForegroundWindow to force focus
                ctypes.windll.user32.SetForegroundWindow(int(window_id))
            except Exception as e:
                logging.debug(f"Non-critical Windows API error: {str(e)}")

            # 4. Focus the input field
            self.window.input_panel.input_field.setFocus()

            # 5. Schedule another focus attempt after a short delay
            QTimer.singleShot(50, self._delayed_focus)
        except Exception as e:
            logging.error(
                f"Error during Windows activation: {str(e)}", exc_info=True)

    def _delayed_focus(self):
        """Second stage of focus setting with delay"""
        try:
            # Try again with explicit focus reason
            self.window.activateWindow()
            self.window.input_panel.input_field.setFocus(
                Qt.FocusReason.ActiveWindowFocusReason)

            # Set up a third attempt after another delay
            QTimer.singleShot(50, self._final_focus)
        except Exception as e:
            logging.error(
                f"Error during delayed focus: {str(e)}", exc_info=True)

    def _final_focus(self):
        """Final attempt to ensure focus"""
        try:
            # One more focused attempt
            self.window.input_panel.input_field.setFocus()

            # Force the cursor to be visible
            if hasattr(self.window.input_panel.input_field, 'setCursorVisible'):
                self.window.input_panel.input_field.setCursorVisible(True)
        except Exception as e:
            logging.error(f"Error during final focus: {str(e)}", exc_info=True)

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
