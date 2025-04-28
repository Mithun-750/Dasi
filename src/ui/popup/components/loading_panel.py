from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


class LoadingPanel(QWidget):
    """
    Panel for showing a loading state after tool call confirmation while waiting for results.
    """
    # Signal to indicate when this component should be hidden
    finished = pyqtSignal()

    def __init__(self, tool_name, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self.dots_counter = 0
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        self.setObjectName("loadingContainer")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(12)
        self.setFixedWidth(330)

        # Title
        title = QLabel("Executing Tool")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; color: #e67e22; font-weight: bold;")
        layout.addWidget(title)

        # Info message
        self.info_label = QLabel(self._get_info_text())
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "font-size: 14px; color: #e0e0e0; margin-top: 8px; font-weight: 500;")
        self.info_label.setFixedWidth(290)
        layout.addWidget(self.info_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #333333;
                border-radius: 4px;
                height: 8px;
                margin: 8px 0;
            }
            QProgressBar::chunk {
                background-color: #e67e22;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Processing message
        self.status_label = QLabel("Processing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "font-size: 13px; color: #aaaaaa; margin-top: 4px;")
        layout.addWidget(self.status_label)

        self.setStyleSheet("""
            #loadingContainer {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
        """)

    def _setup_timer(self):
        """Setup a timer for animated dots and progress indication"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(500)  # Update every 0.5 seconds

    def _update_animation(self):
        """Update the animation for loading indicator"""
        self.dots_counter = (self.dots_counter + 1) % 4
        dots = "." * self.dots_counter
        self.status_label.setText(f"Processing{dots}")

    def _get_info_text(self):
        """Get info text based on the tool being used"""
        if self.tool_name == "web_search":
            return "Searching the web and processing results...\nThis may take a moment."
        elif self.tool_name == "system_info":
            return "Gathering system information...\nThis should be quick."
        else:
            return f"Running tool: {self.tool_name}...\nPlease wait while results are processed."

    def stop_animation(self):
        """Stop the animation and prepare for removal"""
        self.timer.stop()
        self.finished.emit()

    def show_complete(self):
        """Update the display to show completion status"""
        self.timer.stop()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText("Complete!")
        self.status_label.setStyleSheet(
            "font-size: 13px; color: #e67e22; margin-top: 4px; font-weight: bold;")

        # Set up a timer to emit the finished signal after a short delay
        QTimer.singleShot(1000, self.finished.emit)
