from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from typing import Optional
from pathlib import Path
import re


class MentionHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for @mentions in the input field."""

    def __init__(self, parent=None, chunks_dir: Optional[Path] = None):
        super().__init__(parent)
        # Format for @mentions (blue)
        self.mention_format = QTextCharFormat()
        self.mention_format.setBackground(
            QColor("#1a3c6e"))  # Darker blue background
        self.mention_format.setForeground(QColor("#ffffff"))  # White text

        # Format for #web search (orange)
        self.web_search_format = QTextCharFormat()
        self.web_search_format.setBackground(
            QColor("#c35a00"))  # Darker orange background
        self.web_search_format.setForeground(QColor("#ffffff"))  # White text

        # Format for URL links with # (green)
        self.url_scrape_format = QTextCharFormat()
        self.url_scrape_format.setBackground(
            QColor("#19703d"))  # Darker green background
        self.url_scrape_format.setForeground(QColor("#ffffff"))  # White text

        self.chunks_dir = chunks_dir
        self.available_chunks = set()
        self.update_available_chunks()

    def update_available_chunks(self):
        """Update the set of available chunk titles."""
        self.available_chunks.clear()
        if self.chunks_dir and self.chunks_dir.exists():
            for file_path in self.chunks_dir.glob("*.md"):
                self.available_chunks.add(file_path.stem.lower())

    def highlightBlock(self, text: str):
        """Highlight @mentions, #web, and URL# patterns in the text."""
        # Match @word patterns for chunks
        chunk_pattern = r'@\w+(?:_\w+)*'
        for match in re.finditer(chunk_pattern, text):
            start = match.start()
            length = match.end() - start
            # Remove @ and convert to lowercase
            mention = text[start+1:start+length].lower()

            # Only highlight if the chunk exists
            if mention in self.available_chunks:
                self.setFormat(start, length, self.mention_format)
            # No formatting for invalid mentions - they'll use the default text color

        # Match #web pattern
        web_pattern = r'#web\b'
        for match in re.finditer(web_pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.web_search_format)

        # Match URL followed by # pattern
        url_after_pattern = r'(https?://[^\s]+)#'
        for match in re.finditer(url_after_pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.url_scrape_format)

        # Match # followed by URL pattern
        url_before_pattern = r'#(https?://[^\s]+)'
        for match in re.finditer(url_before_pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.url_scrape_format)
