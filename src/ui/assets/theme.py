import os
import qdarktheme
from PyQt6.QtCore import QFile, QTextStream
from PyQt6.QtWidgets import QApplication
import sys
import logging


def load_stylesheet():
    """Load the custom stylesheet from the QSS file."""
    # Handle PyInstaller frozen vs development path differences
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller frozen app
        base_path = sys._MEIPASS
        style_file = os.path.join(base_path, 'assets', 'style.qss')
        logging.info(f"Looking for stylesheet at (frozen): {style_file}")
    else:
        # Running in development
        style_file = os.path.join(os.path.dirname(__file__), 'style.qss')
        logging.info(f"Looking for stylesheet at (dev): {style_file}")
    
    if os.path.exists(style_file):
        file = QFile(style_file)
        file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text)
        stream = QTextStream(file)
        stylesheet = stream.readAll()
        file.close()
        logging.info("Stylesheet loaded successfully")
        return stylesheet
    else:
        logging.warning(f"Stylesheet file not found at: {style_file}")
    return ""


def apply_theme(app, theme="dark", use_custom_stylesheet=True):
    """Apply the theme to the application.
    
    Args:
        app: The QApplication instance
        theme: The theme to apply ("dark", "light", or "auto")
        use_custom_stylesheet: Whether to use the custom stylesheet
    """
    # Set the application style to Fusion for better cross-platform consistency
    app.setStyle('Fusion')
    
    # Apply the qdarktheme
    qdarktheme.setup_theme(theme)
    
    # Apply our custom stylesheet on top if requested
    if use_custom_stylesheet:
        custom_stylesheet = load_stylesheet()
        if custom_stylesheet:
            # Combine the qdarktheme stylesheet with our custom one
            app.setStyleSheet(app.styleSheet() + custom_stylesheet) 