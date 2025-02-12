from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QFrame, QLabel, QPushButton, QHBoxLayout, QProgressBar)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from typing import Callable, Optional, Tuple
import sys


class UISignals(QObject):
    """Signals for UI operations."""
    show_window = pyqtSignal(int, int)  # x, y coordinates
    process_response = pyqtSignal(str)  # Response text
    process_error = pyqtSignal(str)  # Error message


class QueryWorker(QThread):
    """Worker thread for processing queries."""
    def __init__(self, process_fn: Callable[[str], str], query: str, signals: UISignals):
        super().__init__()
        self.process_fn = process_fn
        self.query = query
        self.signals = signals
    
    def run(self):
        """Process the query and emit result."""
        try:
            result = self.process_fn(self.query)
            if result:
                self.signals.process_response.emit(result)
            else:
                self.signals.process_error.emit("No response received")
        except Exception as e:
            self.signals.process_error.emit(str(e))
        finally:
            self.quit()


class DasiWindow(QWidget):
    """Main popup window for Dasi."""
    def __init__(self, process_query: Callable[[str], str], signals: UISignals):
        super().__init__()
        self.process_query = process_query
        self.signals = signals
        self.old_pos = None
        self.worker = None
        
        # Window flags
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
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
        
        # Header with title and drag support
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 5, 10, 5)
        title = QLabel("Dasi")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header.setLayout(header_layout)
        
        # Input area
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Type your query...")
        self.input_field.setFixedHeight(80)
        
        # Loading progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.hide()
        
        # Response preview (hidden by default)
        self.response_preview = QTextEdit()
        self.response_preview.setReadOnly(True)
        self.response_preview.setFixedHeight(100)
        self.response_preview.hide()
        
        # Action buttons (hidden by default)
        self.action_frame = QFrame()
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(5, 0, 5, 5)
        
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self._handle_accept)
        self.reject_button = QPushButton("Reject")
        self.reject_button.clicked.connect(self._handle_reject)
        
        action_layout.addWidget(self.accept_button)
        action_layout.addWidget(self.reject_button)
        self.action_frame.setLayout(action_layout)
        self.action_frame.hide()
        
        # Add widgets to layout
        frame_layout.addWidget(header)
        frame_layout.addWidget(self.input_field)
        frame_layout.addWidget(self.progress_bar)
        frame_layout.addWidget(self.response_preview)
        frame_layout.addWidget(self.action_frame)
        
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
                background-color: #363636;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 5px;
            }
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #4a4a4a;
                font-size: 12px;
                margin: 5px;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                color: white;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QProgressBar {
                border: none;
                background-color: #363636;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
            }
        """)
        
        # Set up key bindings
        self.input_field.installEventFilter(self)
    
    def eventFilter(self, obj, event) -> bool:
        """Handle key events."""
        from PyQt6.QtCore import QEvent
        if obj is self.input_field and event.type() == QEvent.Type.KeyPress:
            # The event is already a QKeyEvent when it comes from Qt
            key_event = event
            
            # Handle Return key (submit)
            if key_event.key() == Qt.Key.Key_Return and not key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._handle_submit()
                return True
            
            # Handle Escape key (close)
            if key_event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
            
            # Handle Shift+Return (newline)
            if key_event.key() == Qt.Key.Key_Return and key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                return False  # Let Qt handle it normally
        
        return super().eventFilter(obj, event)
    
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
            # Show loading state
            self.input_field.setEnabled(False)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.progress_bar.show()
            
            # Process query in background
            self.worker = QueryWorker(self.process_query, query, self.signals)
            self.worker.start()
            
    def _handle_error(self, error_msg: str):
        """Handle query error."""
        # Hide loading state
        self.progress_bar.hide()
        self.input_field.setEnabled(True)
        
        # Show error in preview
        self.response_preview.setText(f"Error: {error_msg}")
        self.response_preview.show()
        
        # Show reject button only
        self.action_frame.show()
        self.accept_button.hide()
        
        # Adjust window size
        self.setFixedHeight(250)
    
    def _handle_response(self, response: str):
        """Handle query response (runs in main thread)."""
        # Hide loading state
        self.progress_bar.hide()
        self.input_field.setEnabled(True)
        
        # Show response preview
        self.response_preview.setText(response)
        self.response_preview.show()
        
        # Show action buttons
        self.action_frame.show()
        self.accept_button.show()
        
        # Adjust window size
        self.setFixedHeight(250)
    
    def _handle_accept(self):
        """Accept the generated response."""
        response = self.response_preview.toPlainText()
        if response:
            self.close()
            # Add prefix to indicate this is a response to be typed
            self.process_query("!" + response)
    
    def _handle_reject(self):
        """Reject the generated response."""
        # Hide response preview and buttons
        self.response_preview.hide()
        self.action_frame.hide()
        
        # Reset window size
        self.setFixedHeight(180)
        
        # Focus input field
        self.input_field.setFocus()


class CopilotUI:
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
        self.window.setFixedSize(320, 180)
        self.window.hide()
        
        # Connect signals
        self.signals.show_window.connect(self._show_window)
        self.signals.process_response.connect(self.window._handle_response)
        self.signals.process_error.connect(self.window._handle_error)
    
    def _show_window(self, x: int, y: int):
        """Show window at specified coordinates (runs in main thread)."""
        # Position window near cursor
        screen = self.app.primaryScreen().geometry()
        x = min(max(x, 0), screen.width() - self.window.width())
        y = min(max(y, 0), screen.height() - self.window.height())
        
        # Show window
        self.window.move(x, y)
        self.window.show()
        self.window.activateWindow()
        self.window.raise_()
        self.window.input_field.setFocus()
        self.window.input_field.clear()
    
    def show_popup(self, x: int, y: int):
        """Emit signal to show popup window."""
        self.signals.show_window.emit(x, y)
    
    def run(self):
        """Start the UI event loop."""
        self.app.exec()
