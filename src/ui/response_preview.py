def set_text(self, text: str):
    """Set the text content of the preview."""
    if text.startswith("⚠️"):
        # Style error messages
        self.setHtml(f"""
            <div style='
                background-color: #3f2828; 
                border-radius: 4px; 
                padding: 10px; 
                margin: 5px;
                border: 1px solid #ff4444;
                color: #ff9999;
                font-family: {self.font_family};
                font-size: {self.font_size}px;
            '>
                {text.replace("⚠️", "")}
            </div>
        """)
    else:
        # Regular text styling
        self.setPlainText(text)
