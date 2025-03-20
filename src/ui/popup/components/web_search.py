from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QProgressBar)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QMovie
import os
import sys
import logging

class WebSearchPanel(QWidget):
    """Web search loading panel component for the Dasi window."""
    
    # Signals
    search_stopped = pyqtSignal()  # Signal emitted when search is stopped by user
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize properties
        self.loading_animation = None
        self.dot_timer = None
        self.dot_count = 0
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        self.setObjectName("loadingContainer")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Set minimum width for the loading container to prevent text cutoff
        self.setMinimumWidth(300)
        self.setMaximumWidth(340)
        
        # Create the loading animation label
        self.loading_animation_label = QLabel()
        self.loading_animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_animation_label.setMinimumSize(140, 140)
        self.loading_animation_label.setMaximumSize(180, 180)
        
        # Setup loading animation
        self._setup_loading_animation()
        
        # Create a label for the search message
        self.loading_text_label = QLabel("Searching the web for information...")
        self.loading_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_text_label.setStyleSheet("""
            font-size: 15px; 
            color: #f0f0f0; 
            margin-top: 10px;
            font-weight: 500;
            letter-spacing: 0.3px;
        """)
        self.loading_text_label.setWordWrap(True)
        self.loading_text_label.setMinimumWidth(300)
        
        # Create a label for additional information
        self.loading_info_label = QLabel("This may take a moment as we gather relevant information from the web.")
        self.loading_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_info_label.setStyleSheet("""
            font-size: 13px; 
            color: #b0b0b0; 
            margin-top: 5px;
            font-style: italic;
            letter-spacing: 0.2px;
        """)
        self.loading_info_label.setWordWrap(True)
        self.loading_info_label.setMinimumWidth(300)
        
        # Create a progress bar for the loading container
        self.loading_progress_bar = QProgressBar()
        self.loading_progress_bar.setObjectName("loadingProgressBar")
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate progress
        self.loading_progress_bar.setFixedHeight(4)
        self.loading_progress_bar.setTextVisible(False)
        
        # Create a container for the progress bar to ensure proper margins
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 10, 0, 10)
        progress_layout.addWidget(self.loading_progress_bar)
        
        # Add a stop button directly in the loading container
        self.loading_stop_button = QPushButton("Stop Search")
        self.loading_stop_button.setObjectName("loadingStopButton")
        self.loading_stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.loading_stop_button.setStyleSheet("""
            #loadingStopButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            #loadingStopButton:hover {
                background-color: #ff6666;
            }
            #loadingStopButton:pressed {
                background-color: #c0392b;
            }
        """)
        self.loading_stop_button.clicked.connect(self._handle_stop)
        
        # Create a container for the button to center it
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.addWidget(self.loading_stop_button)
        
        # Add widgets to the layout
        layout.addWidget(self.loading_animation_label)
        layout.addWidget(self.loading_text_label)
        layout.addWidget(self.loading_info_label)
        layout.addWidget(progress_container)
        layout.addWidget(button_container)
        
        # Style the container
        self.setStyleSheet("""
            #loadingContainer {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
            #loadingProgressBar {
                border: none;
                background-color: #2a2a2a;
                height: 4px;
            }
            #loadingProgressBar::chunk {
                background-color: #e67e22;
            }
        """)
        
    def _setup_loading_animation(self):
        """Set up the loading animation - either GIF or text-based."""
        # Get the absolute path to the assets directory
        if getattr(sys, 'frozen', False):
            # If we're running as a bundled app
            base_path = sys._MEIPASS
        else:
            # If we're running in development
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # Try to find a loading.gif file in the assets directory
        potential_gif_paths = [
            os.path.join(base_path, 'src', 'assets', 'loading.gif'),
            os.path.join(base_path, 'assets', 'loading.gif'),
        ]
        
        gif_path = None
        for path in potential_gif_paths:
            if os.path.exists(path):
                gif_path = path
                break
        
        # If a GIF is found, use it, otherwise use text-based animation
        if gif_path:
            self.loading_animation = QMovie(gif_path)
            self.loading_animation.setScaledSize(QSize(140, 140))
            self.loading_animation_label.setMovie(self.loading_animation)
            logging.info(f"Using GIF animation from {gif_path}")
        else:
            # Create a text-based animation as fallback
            self.loading_animation_label.setText("Searching")
            self.loading_animation_label.setStyleSheet("font-size: 18px; color: #cccccc; font-weight: bold;")
            self.dot_timer = QTimer(self)
            self.dot_timer.timeout.connect(self._update_loading_text)
            logging.warning("Loading GIF not found, using text-based animation")
    
    def start(self, search_term=None):
        """Start the web search animation and show search term if provided."""
        # Show the loading animation
        if isinstance(self.loading_animation, QMovie):
            self.loading_animation.start()
        else:
            self.dot_count = 0  # Reset dot count
            self.dot_timer.start(500)  # Update every 500ms
        
        # Start the progress bar animation
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Update loading text with search term if provided
        if search_term:
            self.loading_text_label.setText(f"Searching the web for: {search_term}")
        else:
            self.loading_text_label.setText("Searching the web...")
        
        # Reset the info label to the default message
        self.loading_info_label.setText("This may take a moment as we gather relevant information from the web.")
        
        # Show the panel
        self.show()
    
    def stop(self):
        """Stop the web search animation."""
        # Stop the loading animation
        if isinstance(self.loading_animation, QMovie):
            self.loading_animation.stop()
        elif self.dot_timer and self.dot_timer.isActive():
            self.dot_timer.stop()
        
        # Set progress bar to complete
        self.loading_progress_bar.setRange(0, 100)
        self.loading_progress_bar.setValue(100)
        
        # Hide the panel
        self.hide()
    
    def _handle_stop(self):
        """Handle stop button click."""
        # Emit signal to notify parent
        self.search_stopped.emit()
    
    def _update_loading_text(self):
        """Update the loading text animation."""
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.loading_animation_label.setText(f"Searching{dots}")
        
        # Rotate through different informational messages
        info_messages = [
            "This may take a moment as we gather relevant information from the web.",
            "We're searching multiple sources to find the most accurate information.",
            "Web search results will be used to provide up-to-date information.",
            "You can stop the search at any time by clicking the Stop button below."
        ]
        
        # Update the info message every 4 cycles (2 seconds)
        if self.dot_count == 0:
            current_text = self.loading_info_label.text()
            current_index = info_messages.index(current_text) if current_text in info_messages else -1
            next_index = (current_index + 1) % len(info_messages)
            self.loading_info_label.setText(info_messages[next_index])
    
    def hideEvent(self, event):
        """Handle hide event to clean up resources."""
        # Stop any running animations
        if isinstance(self.loading_animation, QMovie):
            self.loading_animation.stop()
        elif self.dot_timer and self.dot_timer.isActive():
            self.dot_timer.stop()
        
        super().hideEvent(event) 