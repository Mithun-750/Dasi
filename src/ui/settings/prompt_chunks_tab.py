from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QMessageBox, QFrame, QScrollArea, QStackedWidget,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPalette, QCursor
import os
import re
from pathlib import Path
import logging
from .general_tab import SectionFrame  # Import SectionFrame from general_tab


class ChunkCard(QFrame):
    """A card widget representing a prompt chunk."""

    def __init__(self, title: str, content: str, on_click=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.content = content
        self.on_click = on_click
        self.setup_ui()
        # Set cursor to pointer
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def setup_ui(self):
        self.setObjectName("chunkCard")
        self.setStyleSheet("""
            #chunkCard {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            #chunkCard:hover {
                background-color: #2a2a2a;
                border: 1px solid #e67e22;
            }
            #chunkCard QLabel {
                color: #ffffff;
                background-color: transparent;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        # Restore original height
        self.setFixedHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)  # Restore original spacing

        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet(
            "font-size: 14px; font-weight: 500; color: #ffffff; background-color: transparent;")
        title_label.setMaximumHeight(20)  # Restore original height
        layout.addWidget(title_label)

        # Preview of content
        content_label = QLabel()
        content_label.setWordWrap(True)
        content_label.setStyleSheet("""
            color: #aaaaaa; 
            font-size: 12px;
            padding-bottom: 4px;
            background-color: transparent;
        """)

        # Set for original layout but allow more text to be visible
        content_label.setMaximumHeight(90)

        # Keep the truncation improvements
        if len(self.content) > 500:
            preview = self.content[:500] + "..."
        else:
            preview = self.content

        # Set the text directly and let wordwrap handle display
        content_label.setText(preview)
        content_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(content_label)

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.title)


class CreateCard(ChunkCard):
    """A special card for creating new chunks."""

    def __init__(self, on_click=None, parent=None):
        super().__init__("Create New Chunk",
                         "Click to create a new prompt chunk", on_click, parent)
        self.setObjectName("createCard")
        # Set cursor to pointer
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("""
            #createCard {
                background-color: #e67e22;
                border: 1px solid #d35400;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            #createCard:hover {
                background-color: #f39c12;
                border: 1px solid #e67e22;
            }
            #createCard QLabel {
                color: #ffffff;
                background-color: transparent;
            }
        """)

        # Override the child labels' styles directly
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QLabel):
                if i == 0:  # Title label
                    widget.setStyleSheet(
                        "font-size: 14px; font-weight: 600; color: #ffffff; background-color: transparent;")
                else:  # Content label
                    widget.setStyleSheet(
                        "color: #ffffff; font-size: 12px; padding-bottom: 4px; background-color: transparent;")


class ChunkEditor(QWidget):
    """Editor widget for a prompt chunk."""

    def __init__(self, title: str, content: str, on_save, on_delete, on_back, parent=None):
        super().__init__(parent)
        self.original_title = title
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_back = on_back
        self.setup_ui(title, content)

    def _format_title_input(self, text: str):
        """Format title in real-time to be URL-friendly."""
        cursor_pos = self.title_input.cursorPosition()
        # Remove any non-alphanumeric characters (except underscores)
        clean_text = ''.join(c for c in text if c.isalnum()
                             or c == '_' or c.isspace())
        # Replace spaces with underscores and convert to lowercase
        formatted_text = clean_text.replace(' ', '_').lower()
        # Set the formatted text
        self.title_input.setText(formatted_text)
        # Restore cursor position, adjusting for any removed characters
        new_pos = min(cursor_pos, len(formatted_text))
        self.title_input.setCursorPosition(new_pos)

    def setup_ui(self, title: str, content: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header with title - using a SectionFrame inspired design
        header = QFrame()
        header.setObjectName("editorHeader")
        header.setStyleSheet("""
            #editorHeader {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(0)

        self.title_input = QLineEdit(title)
        self.title_input.setPlaceholderText("Enter chunk title...")
        self.title_input.textChanged.connect(
            self._format_title_input)  # Connect the formatting function
        self.title_input.setStyleSheet("""
            QLineEdit {
                border: none;
                padding: 8px;
                font-size: 14px;
                color: white;
                background: transparent;
            }
            QLineEdit:focus {
                border: none;
                outline: none;
            }
        """)

        header_layout.addWidget(self.title_input)
        layout.addWidget(header)

        # Editor
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "Enter your prompt chunk content here...")
        self.editor.setText(content)
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 16px;
                font-family: monospace;
                font-size: 13px;
                color: #e0e0e0;
            }
            QTextEdit:focus {
                border: 1px solid #e67e22;
            }
        """)
        layout.addWidget(self.editor)

        # Buttons container at the bottom
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(8)

        # Back button on the left
        back_button = QPushButton("← Back")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #aaaaaa;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                color: #e67e22;
            }
        """)
        back_button.clicked.connect(self.on_back)

        # Save and Delete buttons on the right
        save_button = QPushButton("Save Changes")
        save_button.setProperty("class", "primary")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
        """)
        save_button.clicked.connect(self.save_changes)

        delete_button = QPushButton("Delete")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 38, 38, 0.8);
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(220, 38, 38, 1.0);
            }
        """)
        delete_button.clicked.connect(self.delete_chunk)

        # Add buttons to layout
        button_layout.addWidget(back_button)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(delete_button)

        layout.addWidget(button_container)

    def save_changes(self):
        new_title = self.title_input.text().strip()
        content = self.editor.toPlainText().strip()
        self.on_save(self.original_title, new_title, content)

    def delete_chunk(self):
        self.on_delete(self.original_title)


class PromptChunksTab(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.init_ui()
        self.load_chunks()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 0, 16)  # Match general_tab padding

        # Create stacked widget for main content
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(
            "background-color: transparent; border: none;")

        # Create and set up the chunks list page
        self.chunks_page = QWidget()
        self.chunks_page.setStyleSheet(
            "background-color: transparent; border: none;")
        chunks_layout = QVBoxLayout(self.chunks_page)
        chunks_layout.setSpacing(12)
        chunks_layout.setContentsMargins(0, 0, 0, 0)

        # Create a section frame for the chunks list
        chunks_section = SectionFrame(
            "Prompt Chunks",
            "Create and manage prompt templates that can be invoked using @mentions in your conversations."
        )
        chunks_section.setStyleSheet("""
            QFrame.card {
                background-color: transparent;
                border: none;
                border-radius: 0;
            }
            QLabel {
                background-color: transparent;
            }
        """)

        # Search container
        search_container = QWidget()
        search_container.setProperty("class", "transparent-container")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search chunks...")
        self.search_input.setClearButtonEnabled(True)  # Add clear button
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #e67e22;
            }
        """)

        # Explicitly disconnect any existing connections to prevent duplicates
        try:
            self.search_input.textChanged.disconnect()
        except:
            pass

        # Connect the signal
        self.search_input.textChanged.connect(self.filter_chunks)

        # Add stretch factor 1 to make it take full width
        search_layout.addWidget(self.search_input, 1)

        chunks_section.layout.addWidget(search_container)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a !important;
                width: 10px !important;
                margin: 0px 0px 0px 8px !important;
                border-radius: 5px !important;
                border: none !important;
            }
            
            QScrollBar::handle:vertical {
                background-color: #333333 !important;
                min-height: 30px !important;
                border-radius: 5px !important;
                border: none !important;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #e67e22 !important;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px !important;
                border: none !important;
                background: none !important;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none !important;
                border: none !important;
            }
        """)

        # Container for cards
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet(
            "background-color: transparent; border: none;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        chunks_section.layout.addWidget(scroll)

        chunks_layout.addWidget(chunks_section)

        # Add chunks page to stack
        self.stack.addWidget(self.chunks_page)

        # Create editor page (will be populated when needed)
        self.editor_page = QWidget()
        self.editor_page.setStyleSheet(
            "background-color: transparent; border: none;")
        self.editor_layout = QVBoxLayout(self.editor_page)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.editor_page)

        # Add stack to main layout
        layout.addWidget(self.stack)

    def sanitize_title(self, title: str) -> str:
        """Convert title to URL-friendly format."""
        sanitized = re.sub(r'[^\w\s]', '', title)
        return sanitized.replace(' ', '_').lower()

    def load_chunks(self):
        """Load and display all chunks as cards."""
        # Clear existing cards except the last one (create card)
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add create card
        create_card = CreateCard(on_click=lambda _: self.create_new_chunk())
        self.cards_layout.insertWidget(0, create_card)

        # Load and add chunk cards
        for file_path in self.chunks_dir.glob("*.md"):
            title = file_path.stem
            content = file_path.read_text()
            card = ChunkCard(title, content, on_click=self.edit_chunk)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def filter_chunks(self, search_text: str):
        """Filter chunks based on search text."""
        search_text = search_text.lower().strip()

        # Log for debugging
        logging.info(f"Filtering chunks with search text: '{search_text}'")

        # Counter for visible cards (excluding create card)
        visible_count = 0

        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()

                # Handle the create card
                if isinstance(widget, CreateCard):
                    widget.setVisible(True)  # Always show create card
                    continue

                # Handle chunk cards
                if isinstance(widget, ChunkCard):
                    # Empty search shows all
                    if not search_text:
                        widget.setVisible(True)
                        visible_count += 1
                        continue

                    # Check if search text matches title or content
                    title_match = search_text in widget.title.lower()
                    content_match = search_text in widget.content.lower()
                    matches = title_match or content_match

                    widget.setVisible(matches)
                    if matches:
                        visible_count += 1

                    logging.debug(
                        f"Chunk '{widget.title}': visible={matches}, title_match={title_match}, content_match={content_match}")

        # Log total visible
        logging.info(f"Total visible chunks after filtering: {visible_count}")

    def create_new_chunk(self):
        """Show editor for creating a new chunk."""
        editor = ChunkEditor(
            "",
            "",
            on_save=self.save_chunk,
            on_delete=self.delete_chunk,
            on_back=lambda: self.stack.setCurrentIndex(0)
        )
        # Clear editor layout and add new editor
        while self.editor_layout.count():
            item = self.editor_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.editor_layout.addWidget(editor)
        self.stack.setCurrentIndex(1)

    def edit_chunk(self, title: str):
        """Show editor for existing chunk."""
        file_path = self.chunks_dir / f"{title}.md"
        if file_path.exists():
            content = file_path.read_text()
            editor = ChunkEditor(
                title,
                content,
                on_save=self.save_chunk,
                on_delete=self.delete_chunk,
                on_back=lambda: self.stack.setCurrentIndex(0)
            )
            # Clear editor layout and add new editor
            while self.editor_layout.count():
                item = self.editor_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.editor_layout.addWidget(editor)
            self.stack.setCurrentIndex(1)

    def save_chunk(self, old_title: str, new_title: str, content: str):
        """Save a chunk with potential title change."""
        try:
            if not new_title:
                QMessageBox.warning(
                    self, "Error", "Please enter a chunk title.")
                return

            new_title = self.sanitize_title(new_title)
            new_file_path = self.chunks_dir / f"{new_title}.md"
            old_file_path = self.chunks_dir / \
                f"{old_title}.md" if old_title else None

            # Check if we're creating a new file or renaming
            if old_file_path and old_file_path != new_file_path and new_file_path.exists():
                QMessageBox.warning(
                    self, "Error", "A chunk with this title already exists.")
                return

            # Save content to new file
            new_file_path.write_text(content)

            # If this was a rename, delete the old file
            if old_file_path and old_file_path != new_file_path and old_file_path.exists():
                old_file_path.unlink()

            # Reload chunks and go back to list
            self.load_chunks()
            self.stack.setCurrentIndex(0)
            QMessageBox.information(
                self, "Success", "Chunk saved successfully.")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save chunk: {str(e)}")

    def delete_chunk(self, title: str):
        """Delete a chunk."""
        if not title:  # Don't try to delete new unsaved chunk
            self.stack.setCurrentIndex(0)
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this chunk?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                file_path = self.chunks_dir / f"{title}.md"
                if file_path.exists():
                    file_path.unlink()
                self.load_chunks()
                self.stack.setCurrentIndex(0)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to delete chunk: {str(e)}")
