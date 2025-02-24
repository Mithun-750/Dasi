from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from typing import Optional
from pathlib import Path
import re

class MentionHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for @mentions in the input field."""
    def __init__(self, parent=None, chunks_dir: Optional[Path] = None):
        super().__init__(parent)
        self.mention_format = QTextCharFormat()
        self.mention_format.setBackground(QColor("#2b5c99"))  # Blue background
        self.mention_format.setForeground(QColor("#ffffff"))  # White text
        
        self.invalid_mention_format = QTextCharFormat()
        self.invalid_mention_format.setForeground(QColor("#888888"))  # Gray text for invalid mentions
        
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
        """Highlight @mentions in the text."""
        # Match @word patterns
        pattern = r'@\w+(?:_\w+)*'
        for match in re.finditer(pattern, text):
            start = match.start()
            length = match.end() - start
            mention = text[start+1:start+length].lower()  # Remove @ and convert to lowercase
            
            # Apply appropriate format based on whether the chunk exists
            if mention in self.available_chunks:
                self.setFormat(start, length, self.mention_format)
            else:
                self.setFormat(start, length, self.invalid_mention_format)
