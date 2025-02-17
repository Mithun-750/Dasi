from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QTextEdit,
    QLineEdit,
    QMessageBox,
    QFrame,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt
import os
import re
from pathlib import Path
import logging


class PromptChunksTab(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.chunks_dir = Path(self.settings.config_dir) / 'prompt_chunks'
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.current_chunk = None
        self.init_ui()
        self.load_chunks()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Prompt Chunks")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Description
        description = QLabel(
            "Create and manage reusable prompt chunks. Use them in your queries by typing '@' followed by the chunk title."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(description)

        # Main content area
        content = QHBoxLayout()

        # Left side - List of chunks
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Add chunk button and title input
        add_section = QHBoxLayout()
        self.chunk_title = QLineEdit()
        self.chunk_title.setPlaceholderText("Enter chunk title...")
        self.chunk_title.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #363636;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
        """)
        # Connect textChanged signal to auto-format the title
        self.chunk_title.textChanged.connect(self._format_title_input)
        
        add_button = QPushButton("Add")
        add_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #2b5c99;
                border: none;
                border-radius: 4px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
        """)
        add_button.clicked.connect(self.add_chunk)
        
        add_section.addWidget(self.chunk_title)
        add_section.addWidget(add_button)
        left_layout.addLayout(add_section)

        # List of chunks
        self.chunks_list = QListWidget()
        self.chunks_list.setStyleSheet("""
            QListWidget {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #2b5c99;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
        """)
        self.chunks_list.currentItemChanged.connect(self.chunk_selected)
        left_layout.addWidget(self.chunks_list)

        # Right side - Chunk editor
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Editor label
        editor_label = QLabel("Chunk Content")
        editor_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(editor_label)

        # Editor
        self.chunk_editor = QTextEdit()
        self.chunk_editor.setStyleSheet("""
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-family: monospace;
                font-size: 13px;
            }
        """)
        self.chunk_editor.setPlaceholderText("Enter your prompt chunk content here...")
        right_layout.addWidget(self.chunk_editor)

        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save")
        self.save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #2b5c99;
                border: none;
                border-radius: 4px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
        """)
        self.save_button.clicked.connect(self.save_chunk)
        self.save_button.setEnabled(False)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #ff4444;
                border: none;
                border-radius: 4px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        self.delete_button.clicked.connect(self.delete_chunk)
        self.delete_button.setEnabled(False)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        right_layout.addLayout(button_layout)

        # Add panels to content layout
        content.addWidget(left_panel, 1)
        content.addWidget(right_panel, 2)

        layout.addLayout(content)

    def _format_title_input(self, text: str):
        """Format the title input to be URL-friendly in real-time."""
        # Remove any characters that aren't alphanumeric, spaces, or underscores
        clean_text = re.sub(r'[^\w\s]', '', text)
        # Replace spaces with underscores and convert to lowercase
        formatted_text = clean_text.replace(' ', '_').lower()
        
        if formatted_text != text:
            # Temporarily block the signal to prevent recursion
            self.chunk_title.blockSignals(True)
            # Set the cursor position
            cursor_pos = self.chunk_title.cursorPosition()
            # Update the text
            self.chunk_title.setText(formatted_text)
            # Restore the cursor position
            self.chunk_title.setCursorPosition(cursor_pos)
            self.chunk_title.blockSignals(False)

    def sanitize_title(self, title):
        """Convert title to URL-friendly format using underscores."""
        # Remove any characters that aren't alphanumeric, spaces, or underscores
        sanitized = re.sub(r'[^\w\s]', '', title)
        # Replace spaces with underscores and convert to lowercase
        return sanitized.replace(' ', '_').lower()

    def add_chunk(self):
        """Add a new chunk."""
        title = self.chunk_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a chunk title.")
            return

        sanitized_title = self.sanitize_title(title)
        file_path = self.chunks_dir / f"{sanitized_title}.md"

        if file_path.exists():
            QMessageBox.warning(self, "Error", "A chunk with this title already exists.")
            return

        # Create empty file
        file_path.write_text("")

        # Add to list
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.chunks_list.addItem(item)
        
        # Clear title input
        self.chunk_title.clear()
        
        # Select new item
        self.chunks_list.setCurrentItem(item)

    def load_chunks(self):
        """Load existing chunks."""
        self.chunks_list.clear()
        for file_path in self.chunks_dir.glob("*.md"):
            # Use the filename as is, without converting to title case
            title = file_path.stem
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            self.chunks_list.addItem(item)

    def chunk_selected(self, current, previous):
        """Handle chunk selection."""
        if current:
            file_path = Path(current.data(Qt.ItemDataRole.UserRole))
            self.current_chunk = file_path
            if file_path.exists():
                self.chunk_editor.setText(file_path.read_text())
            self.save_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        else:
            self.current_chunk = None
            self.chunk_editor.clear()
            self.save_button.setEnabled(False)
            self.delete_button.setEnabled(False)

    def save_chunk(self):
        """Save the current chunk."""
        if self.current_chunk:
            try:
                self.current_chunk.write_text(self.chunk_editor.toPlainText())
                QMessageBox.information(self, "Success", "Chunk saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save chunk: {str(e)}")

    def delete_chunk(self):
        """Delete the current chunk."""
        if self.current_chunk:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                "Are you sure you want to delete this chunk?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.current_chunk.unlink()
                    self.chunks_list.takeItem(self.chunks_list.currentRow())
                    self.chunk_editor.clear()
                    self.current_chunk = None
                    self.save_button.setEnabled(False)
                    self.delete_button.setEnabled(False)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete chunk: {str(e)}") 