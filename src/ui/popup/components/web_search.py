from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QProgressBar)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QMovie
import os
import sys
import logging
import random  # Add random module for random phrase selection


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
        self.phrase_timer = None  # New timer for phrase rotation
        self.current_phrase_index = 0  # Track current phrase index

        # Fun phrases that will rotate every 5 seconds
        self.fun_phrases = [
            ["Exploring the cosmic darshan...",
                "Consulting modern digital sages for ancient wisdom..."],
            ["Embarking on a yatra through the web...",
                "Suchanā Grahaṇa - the age-old art of gathering digital jñāna..."],
            ["Invoking wisdom from the digital mandir...",
                "Decoding sacred cyber symbols..."],
            ["Riding the data dhara...",
                "Weaving through the bustling digital bazaar..."],
            ["Releasing our digital sher on the prowl...",
                "Following the fragrant trail of timeless lore..."],
            ["Plunging into the ocean of data...",
                "Hunting for pearls of ancient wisdom..."],
            ["Exploring other dimensions of digital existence...",
                "Seeking answers in multiple cosmic realms..."],
            ["Consulting the digital mandali of search engines...",
                "Pooling the wisdom of cyber gurus..."],
            ["Dispatching our stealthy digital warriors...",
                "They navigate the web with the silence of rishis..."],
            ["Reviving slumbering algorithms...",
                "Summoning ancient digital devtas to guide our quest..."],
            ["Sending out knowledge messengers...",
                "Orbiting the globe for treasures of wisdom..."],
            ["Unlocking secret digital vaults...",
                "Diving into the archives of hidden lore..."],
            ["Consulting the digital pandits...",
                "They guard the sacred repositories of knowledge..."],
            ["Unraveling the digital mandala...",
                "No magic, just the raw truth of search results..."]
        ]

        # Setup UI
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        self.setObjectName("loadingContainer")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Reduced top margin from 20px to 10px
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(8)  # Reduced spacing further from 12px to 8px

        # Set width for the loading container to prevent text cutoff
        self.setFixedWidth(330)  # Match the width of preview panel

        # Create the loading animation label
        self.loading_animation_label = QLabel()
        self.loading_animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_animation_label.setFixedSize(
            120, 120)  # Reduced size for better proportion

        # Create animation container for better alignment
        animation_container = QWidget()
        animation_layout = QVBoxLayout(animation_container)
        animation_layout.setContentsMargins(
            0, 0, 0, 0)  # Removed top margin completely
        animation_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        animation_layout.addWidget(self.loading_animation_label)

        # Setup loading animation
        self._setup_loading_animation()

        # Set fixed height for animation container to ensure full visibility
        # Reduced from 130px to 120px to match animation size
        animation_container.setMinimumHeight(120)

        # Create a label for the search message
        self.loading_text_label = QLabel(
            "Searching the web for information...")
        self.loading_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_text_label.setStyleSheet("""
            font-size: 14px; 
            color: #e0e0e0; 
            margin-top: 8px;
            font-weight: 500;
            letter-spacing: 0.3px;
        """)
        self.loading_text_label.setWordWrap(True)
        # Fixed width with some margin for wrapping
        self.loading_text_label.setFixedWidth(290)

        # Create a label for additional information
        self.loading_info_label = QLabel(
            "This may take a moment as we gather relevant information from the web.")
        self.loading_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_info_label.setStyleSheet("""
            font-size: 12px; 
            color: #b0b0b0; 
            margin-top: 5px;
            margin-bottom: 5px;
            font-style: italic;
            letter-spacing: 0.2px;
            line-height: 1.3;
        """)
        self.loading_info_label.setWordWrap(True)
        # Fixed width with some margin for wrapping
        self.loading_info_label.setFixedWidth(290)
        # Taller to accommodate multiple lines
        self.loading_info_label.setMinimumHeight(60)

        # Create a progress bar for the loading container
        self.loading_progress_bar = QProgressBar()
        self.loading_progress_bar.setObjectName("loadingProgressBar")
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate progress
        self.loading_progress_bar.setFixedHeight(4)
        self.loading_progress_bar.setTextVisible(False)

        # Create a container for the progress bar to ensure proper margins
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 8, 0, 8)  # Reduced margins
        progress_layout.addWidget(self.loading_progress_bar)

        # Add a stop button directly in the loading container with modern styling
        self.loading_stop_button = QPushButton("Stop Search")
        self.loading_stop_button.setObjectName("loadingStopButton")
        self.loading_stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Set fixed width for better appearance
        self.loading_stop_button.setFixedWidth(140)
        self.loading_stop_button.setMinimumHeight(
            30)  # Match height with other buttons
        self.loading_stop_button.setStyleSheet("""
            #loadingStopButton {
                background-color: #99322b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-size: 12px;
                font-weight: 600;
            }
            #loadingStopButton:hover {
                background-color: #b33e36;
            }
            #loadingStopButton:pressed {
                background-color: #7d2922;
            }
        """)
        self.loading_stop_button.clicked.connect(self._handle_stop)

        # Create a container for the button to center it
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.addWidget(self.loading_stop_button)

        # Add widgets to the layout
        layout.addWidget(animation_container)
        layout.addWidget(self.loading_text_label)
        layout.addWidget(self.loading_info_label)
        layout.addWidget(progress_container)
        layout.addWidget(button_container)

        # Style the container to match other components
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
            base_path = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
            self.loading_animation.setScaledSize(
                QSize(120, 120))  # Reduced size to match the label
            self.loading_animation_label.setMovie(self.loading_animation)
        else:
            # Create a text-based animation as fallback with improved styling
            self.loading_animation_label.setText("Searching")
            self.loading_animation_label.setStyleSheet("""
                font-size: 18px;
                color: #e67e22;
                font-weight: bold;
                background-color: #2a2a2a;
                border-radius: 60px;
                border: 2px solid #333;
            """)
            self.dot_timer = QTimer(self)
            self.dot_timer.timeout.connect(self._update_loading_text)
            logging.warning(
                "Loading GIF not found, using text-based animation")

    def start(self, search_term=None):
        """Start the web search animation and show search term if provided."""
        # Show the loading animation
        if isinstance(self.loading_animation, QMovie):
            self.loading_animation.start()
        else:
            self.dot_count = 0  # Reset dot count
            self.dot_timer.start(500)  # Update every 500ms
            # Set initial text for text-based animation
            self.loading_animation_label.setText("Exploring")

        # Start the progress bar animation
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate progress

        # Reset phrase index
        self.current_phrase_index = 0

        # Update loading text with initial phrase
        self._update_phrase()

        # Start the phrase rotation timer - update phrases every 5 seconds
        self.phrase_timer = QTimer(self)
        self.phrase_timer.timeout.connect(self._update_phrase)
        self.phrase_timer.start(5000)  # 5000ms = 5 seconds

        # Show the panel
        self.show()

    def _update_phrase(self):
        """Update the fun phrases displayed in the loading panel."""
        if not self.isVisible():
            return

        # Don't update if we're showing a query
        current_info_text = self.loading_info_label.text()
        if "\"" in current_info_text and not current_info_text.startswith("\""):
            return

        # Select a random phrase pair instead of sequential
        phrase_pair = random.choice(self.fun_phrases)
        self.loading_text_label.setText(phrase_pair[0])

        # Only update info label if not showing a query
        if "\"" not in current_info_text or (current_info_text.startswith("\"") and current_info_text.endswith("\"")):
            self.loading_info_label.setText(phrase_pair[1])

    def stop(self):
        """Stop the web search animation."""
        # Stop the loading animation
        if isinstance(self.loading_animation, QMovie):
            self.loading_animation.stop()
        elif self.dot_timer and self.dot_timer.isActive():
            self.dot_timer.stop()

        # Stop the phrase timer
        if self.phrase_timer and self.phrase_timer.isActive():
            self.phrase_timer.stop()

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

        # Get the current text without dots
        current_text = self.loading_animation_label.text()
        base_text = current_text.rstrip('.')

        # Set text with updated dots
        self.loading_animation_label.setText(f"{base_text}{dots}")

    def _update_to_search_message(self, search_term):
        """Update the message to show we're now searching with the optimized query."""
        # This method is now obsolete as we use the phrase rotation timer instead
        pass

    def update_with_optimized_query(self, original_query, optimized_query):
        """Update the message to show the optimized query."""
        if self.isVisible() and original_query != optimized_query:  # Only update if still visible and queries are different
            # Keep the current heading but update the query text

            # Format the query to make it more readable
            max_length = 60  # Maximum length for the query line

            # Helper function to wrap long queries
            def wrap_query(query, max_len):
                if len(query) <= max_len:
                    return query

                # Find a good breaking point (space) near the max length
                breaking_point = query[:max_len].rfind(' ')
                if breaking_point == -1:  # No space found, just truncate
                    return f"{query[:max_len]}..."

                return f"{query[:breaking_point]}..."

            # Format and show only the optimized query
            formatted_optimized = wrap_query(optimized_query, max_length)

            query_text = f"\"{formatted_optimized}\""
            self.loading_info_label.setText(query_text)

    def hideEvent(self, event):
        """Handle hide event to clean up resources."""
        # Stop any running animations
        if isinstance(self.loading_animation, QMovie):
            self.loading_animation.stop()
        elif self.dot_timer and self.dot_timer.isActive():
            self.dot_timer.stop()

        # Stop the phrase timer
        if self.phrase_timer and self.phrase_timer.isActive():
            self.phrase_timer.stop()

        super().hideEvent(event)
