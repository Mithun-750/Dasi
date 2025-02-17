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


class ChunkCard(QFrame):
    """A card widget representing a prompt chunk."""
    def __init__(self, title: str, content: str, on_click=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.content = content
        self.on_click = on_click
        self.setup_ui()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))  # Set cursor to pointer

    def setup_ui(self):
        self.setObjectName("chunkCard")
        self.setStyleSheet("""
            #chunkCard {
                background-color: #363636;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            #chunkCard:hover {
                background-color: #404040;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        # Preview of content
        preview = self.content[:150] + "..." if len(self.content) > 150 else self.content
        content_label = QLabel(preview)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        layout.addWidget(content_label)

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.title)


class CreateCard(ChunkCard):
    """A special card for creating new chunks."""
    def __init__(self, on_click=None, parent=None):
        super().__init__("Create New Chunk", "Click to create a new prompt chunk", on_click, parent)
        self.setObjectName("createCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))  # Set cursor to pointer
        self.setStyleSheet("""
            #createCard {
                background-color: #2b5c99;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            #createCard:hover {
                background-color: #366bb3;
            }
            QLabel {
                color: #ffffff;
            }
        """)


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
        clean_text = ''.join(c for c in text if c.isalnum() or c == '_' or c.isspace())
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
        layout.setSpacing(20)

        # Header with title
        header = QFrame()
        header.setObjectName("editorHeader")
        header.setStyleSheet("""
            #editorHeader {
                background-color: #363636;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(0)

        self.title_input = QLineEdit(title)
        self.title_input.setPlaceholderText("Enter chunk title...")
        self.title_input.textChanged.connect(self._format_title_input)  # Connect the formatting function
        self.title_input.setStyleSheet("""
            QLineEdit {
                border: none;
                padding: 0;
                font-size: 14px;
                color: white;
                background: transparent;
            }
        """)

        header_layout.addWidget(self.title_input)
        layout.addWidget(header)

        # Editor
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Enter your prompt chunk content here...")
        self.editor.setText(content)
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                border: none;
                border-radius: 8px;
                padding: 16px;
                font-family: monospace;
                font-size: 13px;
                color: white;
            }
        """)
        layout.addWidget(self.editor)

        # Buttons container at the bottom
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Back button on the left
        back_button = QPushButton("← Back")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #cccccc;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        back_button.clicked.connect(self.on_back)

        # Save and Delete buttons on the right
        save_button = QPushButton("Save Changes")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2b5c99;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
        """)
        save_button.clicked.connect(self.save_changes)

        delete_button = QPushButton("Delete")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6666;
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
        self.init_ui()
        self.load_chunks()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Create stacked widget for main content
        self.stack = QStackedWidget()

        # Create and set up the chunks list page
        self.chunks_page = QWidget()
        chunks_layout = QVBoxLayout(self.chunks_page)
        chunks_layout.setSpacing(20)
        chunks_layout.setContentsMargins(0, 0, 0, 0)

        # Header with title and search
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Prompt Chunks")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search chunks...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                color: white;
                max-width: 250px;
            }
        """)
        self.search_input.textChanged.connect(self.filter_chunks)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.search_input)

        chunks_layout.addWidget(header)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

        # Container for cards
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        chunks_layout.addWidget(scroll)

        # Add chunks page to stack
        self.stack.addWidget(self.chunks_page)

        # Create editor page (will be populated when needed)
        self.editor_page = QWidget()
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
        search_text = search_text.lower()
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, CreateCard):
                    widget.setVisible(True)  # Always show create card
                elif isinstance(widget, ChunkCard):
                    matches = (search_text in widget.title.lower() or 
                             search_text in widget.content.lower())
                    widget.setVisible(matches)

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
                QMessageBox.warning(self, "Error", "Please enter a chunk title.")
                return

            new_title = self.sanitize_title(new_title)
            new_file_path = self.chunks_dir / f"{new_title}.md"
            old_file_path = self.chunks_dir / f"{old_title}.md" if old_title else None

            # Check if we're creating a new file or renaming
            if old_file_path and old_file_path != new_file_path and new_file_path.exists():
                QMessageBox.warning(self, "Error", "A chunk with this title already exists.")
                return

            # Save content to new file
            new_file_path.write_text(content)

            # If this was a rename, delete the old file
            if old_file_path and old_file_path != new_file_path and old_file_path.exists():
                old_file_path.unlink()

            # Reload chunks and go back to list
            self.load_chunks()
            self.stack.setCurrentIndex(0)
            QMessageBox.information(self, "Success", "Chunk saved successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save chunk: {str(e)}")

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
                QMessageBox.critical(self, "Error", f"Failed to delete chunk: {str(e)}") 