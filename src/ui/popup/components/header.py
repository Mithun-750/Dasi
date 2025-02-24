from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt
import os
import sys
import logging

class Header(QFrame):
    """Header component for the popup window."""
    def __init__(self, on_close=None, on_reset_session=None):
        super().__init__()
        self.setObjectName("header")
        self._setup_ui(on_close, on_reset_session)

    def _setup_ui(self, on_close, on_reset_session):
        """Set up the UI components."""
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
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
            scaled_pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, 
                                        Qt.TransformationMode.SmoothTransformation)
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
        if on_reset_session:
            self.reset_session_button.clicked.connect(on_reset_session)
        self.reset_session_button.setFixedWidth(100)
        self.reset_session_button.hide()  # Hide by default

        # Add close button
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        if on_close:
            close_button.clicked.connect(on_close)
        close_button.setFixedSize(24, 24)

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.reset_session_button)
        header_layout.addWidget(close_button)
        self.setLayout(header_layout)

        self.setStyleSheet("""
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

    def show_reset_button(self):
        """Show the reset session button."""
        self.reset_session_button.show()

    def hide_reset_button(self):
        """Hide the reset session button."""
        self.reset_session_button.hide()
