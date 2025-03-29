import os
import qdarktheme
from PyQt6.QtCore import QFile, QTextStream
from PyQt6.QtWidgets import QApplication
import sys
import logging
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt


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


def apply_scrollbar_styles(app):
    """Apply consistent scrollbar styling to the application."""
    scrollbar_stylesheet = """
        /* Vertical Scrollbar */
        QScrollBar:vertical {
            background-color: #1a1a1a;
            width: 10px;
            margin: 0px 0px 0px 8px;
            border-radius: 5px;
            border: none;
        }
        
        QScrollBar::handle:vertical {
            background-color: #333333;
            min-height: 30px;
            border-radius: 5px;
            border: none;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #e67e22;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            border: none;
            background: none;
        }
        
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
            border: none;
        }
        
        /* Horizontal Scrollbar */
        QScrollBar:horizontal {
            background-color: #1a1a1a;
            height: 10px;
            margin: 8px 0px 0px 0px;
            border-radius: 5px;
            border: none;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #333333;
            min-width: 30px;
            border-radius: 5px;
            border: none;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #e67e22;
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
            border: none;
            background: none;
        }
        
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
            border: none;
        }
    """

    # Get current stylesheet
    current_stylesheet = app.styleSheet()

    # Combine with scrollbar styles
    combined_stylesheet = current_stylesheet + "\n" + scrollbar_stylesheet

    # Apply combined stylesheet
    app.setStyleSheet(combined_stylesheet)


def apply_theme(app, theme="dark", use_custom_stylesheet=True):
    """Apply the theme to the application.

    Args:
        app (QApplication): The application instance
        theme (str, optional): The theme to apply. Defaults to "dark".
        use_custom_stylesheet (bool, optional): Whether to use custom stylesheet. Defaults to True.
    """
    # Set fusion style for better cross-platform consistency
    app.setStyle('Fusion')

    # Apply qdarktheme
    qdarktheme.setup_theme(theme)

    # Apply custom stylesheet on top if requested
    if use_custom_stylesheet:
        # Get the path to the stylesheet
        if getattr(sys, 'frozen', False):
            # Running as bundled app
            base_path = sys._MEIPASS
            stylesheet_path = os.path.join(base_path, "assets", "style.qss")
        else:
            # Running in development
            stylesheet_path = os.path.join(
                os.path.dirname(__file__), "style.qss")

        # Load custom stylesheet
        with open(stylesheet_path, "r") as f:
            custom_stylesheet = f.read()

        # Get current stylesheet and combine with custom
        current_stylesheet = app.styleSheet()

        # Add font styling to ensure consistency across the application
        font_stylesheet = """
        /* Global font styling */
        * {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            color: #e0e0e0;
        }
        
        QLabel[class="subheading"] {
            font-size: 15px;
            font-weight: 600;
            color: #ffffff;
        }
        
        QLabel[class="description"] {
            font-size: 12px;
            color: #aaaaaa;
        }
        
        QLabel[class="header-title"] {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-weight: 600;
            font-size: 19px;
            color: #ffffff;
            letter-spacing: 0.5px;
        }
        
        QLabel[class="header-subtitle"] {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-weight: 400;
            font-size: 10px;
            color: #f8c291;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        """

        combined_stylesheet = current_stylesheet + "\n" + \
            custom_stylesheet + "\n" + font_stylesheet

        # Apply the combined stylesheet
        app.setStyleSheet(combined_stylesheet)

        # Apply scrollbar styles
        apply_scrollbar_styles(app)

        # Force stylesheet refresh
        for widget in app.allWidgets():
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
