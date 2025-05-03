from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, QUrl, pyqtSlot, Qt
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtGui import QClipboard
from PyQt6.QtWidgets import QApplication
import os
import logging
import tempfile
import sys


class Document(QObject):
    """Document object to pass to JavaScript via WebChannel."""

    textChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.m_text = ""

    def get_text(self):
        return self.m_text

    def set_text(self, text):
        if self.m_text == text:
            return
        self.m_text = text
        self.textChanged.emit(self.m_text)

    text = pyqtProperty(str, fget=get_text, fset=set_text, notify=textChanged)

    @pyqtSlot(str)
    def copy_to_clipboard(self, text):
        """Slot to copy text to the system clipboard using QApplication."""
        try:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                logging.info(
                    f"Copied {len(text)} characters to clipboard via Python slot.")
            else:
                logging.warning(
                    "Could not get clipboard instance in Document slot.")
        except Exception as e:
            logging.error(
                f"Error copying to clipboard via Python slot: {e}", exc_info=True)


class MarkdownRenderer(QWidget):
    """Component for rendering markdown content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_html_template()

        # Set size policy to be more flexible
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Minimum)
        self.setMaximumHeight(400)  # Keep max height to prevent overflow

    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Web engine view for markdown rendering
        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        # Set size policy to make the web view adapt to content
        self.web_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.web_view.loadFinished.connect(self._adjust_height)

        # Style the web view
        self.web_view.setStyleSheet("""
            QWebEngineView {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        # Set up web channel for JS communication
        self.document = Document()
        self.channel = QWebChannel()
        self.channel.registerObject("content", self.document)
        self.web_view.page().setWebChannel(self.channel)

        # Add web view to layout
        layout.addWidget(self.web_view)
        self.setLayout(layout)

        # Connect signals
        self.document.textChanged.connect(self._update_content)

        # Make sure the widget and its contents are visible
        self.show()
        self.web_view.show()

    def _setup_html_template(self):
        """Set up the HTML template for rendering markdown."""
        # Get the absolute path to the assets directory
        if getattr(sys, 'frozen', False):
            # If we're running as a bundled app
            base_path = sys._MEIPASS
        else:
            # If we're running in development
            base_path = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        # Try multiple possible paths for marked.js
        possible_paths = [
            os.path.join(base_path, 'assets', 'js', 'marked.min.js'),
            os.path.join(base_path, 'src', 'assets', 'js', 'marked.min.js'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', '..', '..', 'assets', 'js', 'marked.min.js')
        ]

        marked_js_content = None
        for path in possible_paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    marked_js_content = f.read()
                    logging.info(f"Successfully loaded marked.js from {path}")
                    break
            except Exception as e:
                logging.debug(
                    f"Could not load marked.js from {path}: {str(e)}")

        if marked_js_content is None:
            logging.error(
                "Could not find marked.js in any of the expected locations")
            marked_js_content = ""  # Empty string as fallback

        # Create HTML template with marked.js embedded
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Markdown Preview</title>
            <script>
                // Embed marked.js directly
                %s
            </script>
            <script src="qrc:/qtwebchannel/qwebchannel.js"></script>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.5;
                    color: #e0e0e0;
                    background-color: #1e1e1e;
                    padding: 8px;
                    margin: 0;
                    font-size: 14px;
                    overflow-y: auto;
                }
                
                html {
                    overflow: auto;
                }
                
                #markdown-content {
                    /* Content should only be as tall as needed */
                }
                
                /* Common text styling */
                h1, h2, h3, h4, h5, h6 {
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                    font-weight: 600;
                    color: #ffffff;
                }
                
                /* Scrollbar styling */
                ::-webkit-scrollbar {
                    width: 8px;
                    height: 8px;
                }
                
                ::-webkit-scrollbar-track {
                    background: transparent;
                    border-radius: 4px;
                }
                
                ::-webkit-scrollbar-thumb {
                    background: #4a4a4a;
                    border-radius: 4px;
                    transition: background 0.2s ease;
                }
                
                ::-webkit-scrollbar-thumb:hover {
                    background: #e67e22;
                }
                
                ::-webkit-scrollbar-corner {
                    background: transparent;
                }
                
                /* Hide scrollbar when not hovering */
                ::-webkit-scrollbar-thumb:vertical:hover,
                ::-webkit-scrollbar-thumb:horizontal:hover {
                    background: #e67e22;
                }
                
                ::-webkit-scrollbar-thumb:vertical,
                ::-webkit-scrollbar-thumb:horizontal {
                    min-height: 30px;
                }
                
                /* Text selection */
                ::selection {
                    background-color: rgba(230, 126, 34, 0.4);
                }
                
                h1 { font-size: 1.8em; border-bottom: 1px solid #333; padding-bottom: 0.2em; }
                
                h2 { font-size: 1.5em; border-bottom: 1px solid #333; padding-bottom: 0.2em; }
                h3 { font-size: 1.3em; }
                h4 { font-size: 1.1em; }
                
                p {
                    margin: 0.7em 0;
                }
                
                a {
                    color: #e67e22;
                    text-decoration: none;
                }
                
                a:hover {
                    text-decoration: underline;
                }
                
                pre {
                    position: relative; /* Needed for absolute positioning of the button */
                    background-color: #2a2a2a;
                    border-radius: 4px;
                    padding: 0.5em;
                    overflow-x: auto;
                    margin: 1em 0;
                }
                
                /* Style for the copy button */
                .copy-button {
                    position: absolute;
                    top: 4px;
                    right: 4px;
                    background-color: #4a4a4a;
                    color: #e0e0e0;
                    border: none;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 0.8em;
                    cursor: pointer;
                    opacity: 0; /* Hidden by default */
                    transition: opacity 0.2s ease, background-color 0.2s ease;
                }

                pre:hover .copy-button {
                    opacity: 1; /* Show on hover */
                }
                
                .copy-button:hover {
                    background-color: #e67e22;
                    color: #1e1e1e;
                }
                
                .copy-button.copied {
                    background-color: #27ae60; /* Green when copied */
                    color: #ffffff;
                }
                
                code {
                    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
                    background-color: #2a2a2a;
                    padding: 0.2em 0.4em;
                    border-radius: 3px;
                    font-size: 85%%;
                }
                
                pre code {
                    padding: 0;
                    background: none;
                }
                
                blockquote {
                    border-left: 4px solid #e67e22;
                    margin: 1em 0;
                    padding: 0 1em;
                    color: #9e9e9e;
                }
                
                table {
                    border-collapse: collapse;
                    width: 100%%;
                    margin: 1em 0;
                }
                
                table, th, td {
                    border: 1px solid #333;
                }
                
                th, td {
                    padding: 0.5em;
                    text-align: left;
                }
                
                th {
                    background-color: #2a2a2a;
                }
                
                ul, ol {
                    padding-left: 2em;
                    margin: 0.7em 0;
                }
                
                li {
                    margin: 0.3em 0;
                }
                
                hr {
                    border: none;
                    border-top: 1px solid #333;
                    margin: 1.5em 0;
                }
                
                img {
                    max-width: 100%%;
                    height: auto;
                    border-radius: 4px;
                }
                
                .task-list-item {
                    list-style-type: none;
                    position: relative;
                    padding-left: 1.5em;
                }
                
                .task-list-item input {
                    position: absolute;
                    left: 0;
                    top: 0.25em;
                }
            </style>
        </head>
        <body>
            <div id="markdown-content"></div>
            
            <script>
                'use strict';
                
                let webChannelContent = null; // Variable to hold the content object
                
                // Wait for marked to be available
                function initializeMarked() {
                    if (typeof marked === 'undefined') {
                        console.error('marked is not defined');
                        return;
                    }
                    
                    // Configure marked.js options
                    marked.setOptions({
                        breaks: true,           // Add line breaks on single line breaks
                        gfm: true,              // Use GitHub Flavored Markdown
                        headerIds: true,        // Generate IDs for headers
                        mangle: false,          // Don't mangle header IDs
                    });
                    
                    // Handle content updates
                    var updateContent = function(text) {
                        try {
                            // Preprocess text to ensure fences are on new lines
                            const processedText = (text || '').replace(/([^\\n])(```)/g, '$1\\n$2');
                            document.getElementById('markdown-content').innerHTML = marked.parse(processedText);
                        } catch (e) {
                            console.error('Error parsing markdown:', e);
                            document.getElementById('markdown-content').innerHTML = '<p style="color: #ff6b6b;">Error rendering markdown</p>';
                        }
                        addCopyButtons(); // Add copy buttons after rendering
                    };
                    
                    // Function to add copy buttons to code blocks
                    function addCopyButtons() {
                        const codeBlocks = document.querySelectorAll('pre');
                        codeBlocks.forEach(block => {
                            // Avoid adding button if it already exists
                            if (block.querySelector('.copy-button')) {
                                return;
                            }
                            
                            const button = document.createElement('button');
                            button.textContent = 'Copy';
                            button.className = 'copy-button';
                            
                            button.addEventListener('click', () => {
                                // Find the 'code' element inside 'pre' or use 'pre' itself
                                const codeElement = block.querySelector('code');
                                const textToCopy = codeElement ? codeElement.innerText : block.innerText.replace(/\\nCopy$/, ''); // Fallback + remove trailing button text if needed

                                try {
                                    // Call the Python slot via the web channel using the accessible variable
                                    if (webChannelContent) {
                                        webChannelContent.copy_to_clipboard(textToCopy);
                                    } else {
                                        console.error('webChannelContent is not initialized');
                                        throw new Error('Web channel content object not available.');
                                    }

                                    // Provide immediate feedback (assuming success for now)
                                    button.textContent = 'Copied!';
                                    button.classList.add('copied');
                                    setTimeout(() => {
                                        button.textContent = 'Copy';
                                        button.classList.remove('copied');
                                    }, 2000);
                                } catch (err) {
                                    console.error('Failed to call copy_to_clipboard slot: ', err);
                                    button.textContent = 'Error';
                                    setTimeout(() => {
                                        button.textContent = 'Copy';
                                    }, 2000);
                                }
                            });
                            
                            block.appendChild(button);
                        });
                    }

                    // Set up WebChannel to receive content updates
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        var content = channel.objects.content;
                        webChannelContent = content; // Assign to the broader scoped variable
                        updateContent(content.text);
                        content.textChanged.connect(updateContent);
                    });
                }
                
                // Initialize when the document is ready
                document.addEventListener('DOMContentLoaded', initializeMarked);
            </script>
        </body>
        </html>
        """ % marked_js_content

        # Create a temporary HTML file
        temp_dir = tempfile.gettempdir()
        self.html_path = os.path.join(temp_dir, "dasi_markdown_preview.html")

        try:
            with open(self.html_path, 'w', encoding='utf-8') as f:
                f.write(html_template)

            # Load the HTML file
            self.web_view.load(QUrl.fromLocalFile(self.html_path))
            logging.info("Successfully created and loaded HTML template")
        except Exception as e:
            logging.error(f"Error setting up markdown renderer: {str(e)}")
            # Add fallback HTML content in case of error
            fallback_html = """
            <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Error</title>
            <style>body { background-color: #1e1e1e; color: #e0e0e0; font-family: sans-serif; padding: 1em; }</style>
            </head><body><p>Error loading markdown renderer.</p></body></html>
            """
            self.web_view.setHtml(fallback_html)

    def set_markdown(self, markdown_text):
        """Set the markdown content to be rendered."""
        if not isinstance(markdown_text, str):
            logging.warning(
                f"Expected string for markdown_text, got {type(markdown_text)}")
            markdown_text = str(markdown_text)
        self.document.set_text(markdown_text)

        # Ensure the widget is visible
        self.show()
        self.web_view.show()

        # Trigger height adjustment after a short delay to let the content render
        self.web_view.page().runJavaScript("""
            // Defer execution to ensure content is rendered
            setTimeout(function() {
                document.body.offsetHeight;
            }, 50);
        """, self._set_height)

    def _update_content(self, text):
        """Update the content (handled by JavaScript)."""
        # This is just a placeholder. The actual update happens via WebChannel in JavaScript.
        pass

    def get_plain_text(self):
        """Get the plain text content from the markdown (not rendered HTML)."""
        return self.document.get_text()

    @pyqtSlot(result=str)
    def copy_text(self):
        """Copy plain text to clipboard (can be called from JS)."""
        return self.document.get_text()

    def clear(self):
        """Clear the markdown content."""
        self.document.set_text("")

    def showEvent(self, event):
        """Handle show events to ensure proper visibility."""
        super().showEvent(event)
        self.web_view.show()

    def hideEvent(self, event):
        """Handle hide events."""
        super().hideEvent(event)
        self.web_view.hide()

    def _adjust_height(self, success):
        """Adjust height based on content after page is loaded."""
        if success:
            self.web_view.page().runJavaScript("""
                document.body.offsetHeight;
            """, self._set_height)

    def _set_height(self, height):
        """Set the height of the web view based on content."""
        if height and height > 0:
            # Add a small buffer for padding
            content_height = height + 16
            # Limit height to max 400px
            content_height = min(content_height, 400)
            # Set height
            self.web_view.setMinimumHeight(content_height)
            self.setMinimumHeight(content_height)

            # Refresh the layout
            self.updateGeometry()
