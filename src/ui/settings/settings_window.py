import sys
import os
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QFrame,
    QMessageBox,
    QLabel,
)
from PyQt6.QtCore import Qt, QObject, QSize
from PyQt6.QtGui import QIcon, QPixmap
import logging
import socket

from .settings_manager import Settings
from .api_keys_tab import APIKeysTab
from .models_tab import ModelsTab
from .general_tab import GeneralTab
from .prompt_chunks_tab import PromptChunksTab
# from .web_search_tab import WebSearchTab # Ensure this is removed/commented
from .tools_tab import ToolsTab
from .examples_tab import ExamplesTab
from core.instance_manager import DasiInstanceManager
from ui.assets import apply_theme


class SidebarButton(QPushButton):
    def __init__(self, text, icon_path=None, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("class", "sidebar-button")

        # Set icon if provided
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(20, 20))

        # Set minimum height for better touch targets
        self.setMinimumHeight(48)

        # Add custom styling with more subtle professional effects
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                margin: 2px 8px;
                color: #e0e0e0;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #2e2e2e;
                border-left: 2px solid #e67e22;
                color: white;
            }
            QPushButton:checked {
                background-color: #e67e22;
                color: white;
                font-weight: medium;
            }
        """)


class ActionButton(QPushButton):
    """Button for actions like Start Dasi."""

    def __init__(self, text, icon_path=None, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("class", "primary")
        self._original_text = text  # Store original text

        # Set fixed width for the button
        self.setFixedWidth(170)  # Slightly smaller width

        # Center the button in its layout
        self.setStyleSheet("""
            QPushButton { 
                text-align: center;
                background-color: #e67e22;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #999999;
            }
        """)

        # Set icon if provided
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(18, 18))  # Slightly smaller icon

            # Add spacing between icon and text, but keep centered
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            # Adjust text with spacing that maintains center alignment
            self.setText(" " + text)  # Less space needed with centered text

    def setText(self, text):
        """Override setText to maintain proper spacing with icon"""
        self._original_text = text
        # Add a small spacing for better appearance
        spaced_text = " " + text
        super().setText(spaced_text)


class SettingsWindow(QMainWindow):
    def __init__(self, dasi_instance=None):
        super().__init__()
        self.settings = Settings()
        self.hotkey_listener = None

        # If a Dasi instance was passed, use it
        self.dasi_instance = dasi_instance
        if self.dasi_instance:
            # Register the instance with the manager if it's not already registered
            if not DasiInstanceManager.get_instance():
                DasiInstanceManager.set_instance(self.dasi_instance)
            # Get the hotkey listener from the instance
            if hasattr(self.dasi_instance, 'hotkey_listener'):
                self.hotkey_listener = self.dasi_instance.hotkey_listener
                logging.info(
                    "Successfully connected to existing hotkey listener")
        else:
            # No instance provided, check if one is registered with the manager
            existing_instance = DasiInstanceManager.get_instance()
            if existing_instance:
                self.dasi_instance = existing_instance
                if hasattr(existing_instance, 'hotkey_listener'):
                    self.hotkey_listener = existing_instance.hotkey_listener
                    logging.info("Connected to registered hotkey listener")

        self.init_ui()

        # Connect directly to the settings models_changed signal
        # This ensures we get the signal only once when models change
        logging.info("Connecting to Settings.models_changed signal")
        self.settings.models_changed.connect(self.handle_models_changed)
        logging.info("Connected to Settings.models_changed signal")

        # Check if Dasi is already running
        self.check_dasi_running()

        # Force style refresh after initialization to ensure correct styling
        self.refresh_styles()

    def init_ui(self):
        self.setWindowTitle("Dasi Settings")
        self.setMinimumSize(900, 600)

        # Get assets directory paths based on whether we're running as a bundled app
        if getattr(sys, 'frozen', False):
            # If we're running as a bundled app
            base_path = sys._MEIPASS
            ui_assets_dir = os.path.join(base_path, "assets")
            root_assets_dir = os.path.join(base_path, "assets")
            logging.info(
                f"Running bundled app, using assets at: {ui_assets_dir}")
        else:
            # If we're running in development
            # UI assets dir (for icons)
            ui_assets_dir = os.path.join(os.path.dirname(
                os.path.dirname(__file__)), "assets")
            # Project root assets dir (for app logo)
            project_root = os.path.dirname(os.path.dirname(
                os.path.dirname(__file__)))  # src/ directory
            root_assets_dir = os.path.join(project_root, "assets")
            logging.info(
                f"Running in development, using assets at: {ui_assets_dir}")

        # Define icon paths for start/stop button
        self.play_icon_path = os.path.join(ui_assets_dir, "icons", "play.png")
        self.stop_icon_path = os.path.join(ui_assets_dir, "icons", "stop.png")

        # Set window icon for taskbar
        icon_path = os.path.join(root_assets_dir, "Dasi.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logging.info(f"Set window icon from: {icon_path}")
        else:
            logging.warning(f"Window icon not found at {icon_path}")

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create sidebar
        sidebar = QFrame()
        sidebar.setProperty("class", "sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(8)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)

        # Apply sidebar styling
        sidebar.setStyleSheet("""
            QFrame.sidebar {
                background-color: #1a1a1a;
                border-right: 1px solid #333333;
            }
        """)

        # Add modern logo and header at the top of sidebar
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(12, 15, 12, 5)  # Adjusted padding
        header_layout.setSpacing(0)

        # Create horizontal layout for logo and title
        logo_title_container = QWidget()
        logo_title_layout = QHBoxLayout(logo_title_container)
        logo_title_layout.setContentsMargins(0, 0, 0, 0)
        # Slightly more space between logo and text
        logo_title_layout.setSpacing(14)
        logo_title_layout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter)  # Ensure vertical centering

        # Add logo image
        logo_image = QLabel()
        logo_image.setFixedSize(QSize(40, 40))  # Consistent size

        # Set logo from assets using the root_assets_dir path
        logo_path = os.path.join(root_assets_dir, "Dasi.png")

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            pixmap = pixmap.scaled(QSize(
                40, 40), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_image.setPixmap(pixmap)
            logo_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            # Fallback text if logo can't be found
            logo_image.setText("D")
            logo_image.setStyleSheet(
                "font-size: 22px; font-weight: bold; color: #e67e22;")
            logo_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logging.warning(f"Logo file not found at {logo_path}")

        # Text content for better vertical alignment
        text_content = QWidget()
        text_content_layout = QVBoxLayout(text_content)
        text_content_layout.setContentsMargins(0, 0, 0, 0)
        text_content_layout.setSpacing(0)  # No spacing between elements

        # Add stylish app name text
        title_label = QLabel("Dasi")
        title_label.setProperty("class", "header-title")
        subtitle_label = QLabel("SETTINGS")
        subtitle_label.setProperty("class", "header-subtitle")

        # Add text elements to layout
        text_content_layout.addWidget(title_label)
        text_content_layout.addWidget(subtitle_label)

        # Add elements to horizontal layout with proper alignment
        logo_title_layout.addWidget(logo_image)
        logo_title_layout.addWidget(text_content, 1)

        # Add the horizontal container to the main header layout
        header_layout.addWidget(logo_title_container)

        # Add styling for text elements
        header_container.setStyleSheet("""
            QLabel.header-title {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 600;
                font-size: 19px;
                color: #ffffff;
                letter-spacing: 0.5px;
                padding: 0px;
            }
            QLabel.header-subtitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 400;
                font-size: 10px;
                color: #f8c291;
                letter-spacing: 2px;
                text-transform: uppercase;
                padding: 0px;
            }
        """)

        # Add spacing and the header container to the sidebar
        # More bottom spacing to separate from buttons
        header_container.setContentsMargins(0, 0, 0, 25)
        sidebar_layout.addWidget(header_container)

        # Create sidebar buttons for each tab
        self.general_button = SidebarButton(
            "General", os.path.join(ui_assets_dir, "icons", "settings.svg"))
        self.models_button = SidebarButton(
            "Models", os.path.join(ui_assets_dir, "icons", "model.svg"))
        self.api_keys_button = SidebarButton(
            "API Keys", os.path.join(ui_assets_dir, "icons", "key.svg"))
        self.system_prompts_button = SidebarButton(
            "System Prompts", os.path.join(ui_assets_dir, "icons", "prompt.svg"))
        self.tools_button = SidebarButton(
            "Tools", os.path.join(ui_assets_dir, "icons", "tools.svg"))
        self.examples_button = SidebarButton(
            "Examples", os.path.join(ui_assets_dir, "icons", "examples.svg"))

        # Add buttons to sidebar
        sidebar_layout.addWidget(self.general_button)
        sidebar_layout.addWidget(self.models_button)
        sidebar_layout.addWidget(self.api_keys_button)
        sidebar_layout.addWidget(self.system_prompts_button)
        sidebar_layout.addWidget(self.tools_button)
        sidebar_layout.addWidget(self.examples_button)
        sidebar_layout.addStretch()

        # Add user tools section to sidebar
        button_container = QHBoxLayout()
        button_container.setContentsMargins(10, 10, 10, 20)
        button_container.setSpacing(10)

        # Create start/stop Dasi button with icon (using PNG path)
        self.start_dasi_btn = ActionButton("Start Dasi", self.play_icon_path)
        self.start_dasi_btn.clicked.connect(self.start_dasi)

        # Add to sidebar bottom
        button_container.addWidget(self.start_dasi_btn)
        sidebar_layout.addLayout(button_container)

        # Create content area with card-like appearance
        content_container = QFrame()
        content_container.setFrameShape(QFrame.Shape.NoFrame)
        content_container.setContentsMargins(0, 0, 5, 0)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Set darker background color with proper font styling
        content_container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: none;
                border-radius: 0;
            }
        """)

        # Create stacked widget for content
        self.content = QStackedWidget()
        self.content.setStyleSheet("""
            QStackedWidget {
                background-color: #1a1a1a;
                border: none;
                border-radius: 0;
            }
        """)

        # Add content directly to layout without the card frame
        content_layout.addWidget(self.content)

        # Create and add tabs
        self.general_tab = GeneralTab(self.settings)
        self.models_tab = ModelsTab(self.settings)
        self.api_keys_tab = APIKeysTab(self.settings)
        self.prompt_chunks_tab = PromptChunksTab(self.settings)
        # self.web_search_tab = WebSearchTab(self.settings) # Ensure this is removed/commented
        self.tools_tab = ToolsTab(self.settings)
        self.examples_tab = ExamplesTab(self.settings)

        # Connect examples_changed signal to refresh Dasi's prompts
        self.examples_tab.examples_changed.connect(
            self._handle_examples_changed)

        # Add tabs to stacked widget
        self.content.addWidget(self.general_tab)
        self.content.addWidget(self.models_tab)
        self.content.addWidget(self.api_keys_tab)
        self.content.addWidget(self.prompt_chunks_tab)
        # self.content.addWidget(self.web_search_tab) # Ensure this is removed/commented
        self.content.addWidget(self.tools_tab)
        self.content.addWidget(self.examples_tab)

        # Add widgets to main layout
        main_layout.addWidget(sidebar)
        # Give content area more space
        main_layout.addWidget(content_container, 1)

        # Connect button signals
        self.general_button.clicked.connect(lambda: self.switch_tab(0))
        self.models_button.clicked.connect(lambda: self.switch_tab(1))
        self.api_keys_button.clicked.connect(lambda: self.switch_tab(2))
        self.system_prompts_button.clicked.connect(lambda: self.switch_tab(3))
        self.tools_button.clicked.connect(lambda: self.switch_tab(4))
        self.examples_button.clicked.connect(lambda: self.switch_tab(5))

        # Connect API key cleared signal to remove models by provider
        self.api_keys_tab.api_key_cleared.connect(
            self.models_tab.remove_models_by_provider)

        # Set initial tab
        self.switch_tab(0)

        # Update Start Dasi button state
        self.update_start_button()

    def switch_tab(self, index: int):
        """Switch to the specified tab."""
        self.content.setCurrentIndex(index)

        # Update button states
        buttons = [self.general_button, self.models_button,
                   self.api_keys_button, self.system_prompts_button,
                   self.tools_button, self.examples_button]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)

    def check_dasi_running(self):
        """Check if Dasi is already running and update UI accordingly."""
        # If we already have a Dasi instance, it's running
        if self.dasi_instance and self.hotkey_listener and self.hotkey_listener.is_running():
            # Update button to show Stop Dasi
            self.start_dasi_btn.setText("Stop Dasi")
            self.start_dasi_btn.setEnabled(True)
            # Use the same theme for consistency, with slightly darker shade
            self.start_dasi_btn.setStyleSheet("""
                QPushButton { 
                    text-align: center;
                    background-color: #d35400;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
            """)
            self.start_dasi_btn.setIcon(QIcon(self.stop_icon_path))

            # Connect to stop_dasi
            try:
                self.start_dasi_btn.clicked.disconnect()
            except:
                pass
            self.start_dasi_btn.clicked.connect(self.stop_dasi)
            return

        # Otherwise check using the socket method
        if DasiInstanceManager.is_running():
            # Dasi is already running
            # Try to get the existing Dasi instance if available
            existing_instance = DasiInstanceManager.get_instance()
            if existing_instance:
                self.dasi_instance = existing_instance
                if hasattr(existing_instance, 'hotkey_listener'):
                    self.hotkey_listener = existing_instance.hotkey_listener

            # Update button to show Stop Dasi
            self.start_dasi_btn.setText("Stop Dasi")
            self.start_dasi_btn.setEnabled(True)
            # Use the same theme for consistency, with slightly darker shade
            self.start_dasi_btn.setStyleSheet("""
                QPushButton { 
                    text-align: center;
                    background-color: #d35400;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
            """)
            self.start_dasi_btn.setIcon(QIcon(self.stop_icon_path))

            # Connect to stop_dasi
            try:
                self.start_dasi_btn.clicked.disconnect()
            except:
                pass
            self.start_dasi_btn.clicked.connect(self.stop_dasi)
        else:
            # Dasi is not running
            # Update button to show Start Dasi
            self.update_start_button()

    def update_start_button(self):
        """Update the Start Dasi button state."""
        # IMPORTANT: Don't change the running state when models change
        # If we already have Dasi running, preserve that state

        # Get the current button text to check if we're showing "Stop Dasi" or "Start Dasi"
        current_button_text = self.start_dasi_btn.text()
        # Remove leading space added by ActionButton setText override
        if current_button_text.startswith(" "):
            current_button_text = current_button_text[1:]
        already_showing_stop = current_button_text == "Stop Dasi"

        # Only perform the full state check if we're not already showing "Stop Dasi"
        # This prevents model changes from affecting the button state
        if already_showing_stop:
            # If we're already showing Stop Dasi, keep it that way
            # This prevents model changes from toggling the button
            return

        # Check if Dasi is running - use consistent check method
        has_instance = DasiInstanceManager.is_running()
        has_listener = self.hotkey_listener is not None
        is_active = has_listener and self.hotkey_listener.is_running()
        is_running = has_instance and is_active

        # Log the state for debugging
        logging.info(
            f"Dasi state: has_instance={has_instance}, has_listener={has_listener}, is_active={is_active}, is_running={is_running}")

        # Update button text and icon
        if is_running:
            self.start_dasi_btn.setText("Stop Dasi")
            if os.path.exists(self.stop_icon_path):
                self.start_dasi_btn.setIcon(QIcon(self.stop_icon_path))
            self.start_dasi_btn.setToolTip("Stop the Dasi hotkey listener")

            # Update styling for stop button
            self.start_dasi_btn.setStyleSheet("""
                QPushButton { 
                    text-align: center;
                    background-color: #d35400;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
            """)

            # Connect to stop_dasi
            try:
                self.start_dasi_btn.clicked.disconnect()
            except:
                pass
            self.start_dasi_btn.clicked.connect(self.stop_dasi)
        else:
            has_models = bool(self.settings.get_selected_models())
            self.start_dasi_btn.setText(
                "Start Dasi" if has_models else "Select Models First")
            self.start_dasi_btn.setEnabled(has_models)
            if os.path.exists(self.play_icon_path):
                self.start_dasi_btn.setIcon(QIcon(self.play_icon_path))
            self.start_dasi_btn.setToolTip("Start the Dasi hotkey listener")

            # Update styling for start button
            self.start_dasi_btn.setStyleSheet("""
                QPushButton { 
                    text-align: center;
                    background-color: #e67e22;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #f39c12;
                }
                QPushButton:disabled {
                    background-color: #555555;
                    color: #999999;
                }
            """)

            # Connect to start_dasi
            try:
                self.start_dasi_btn.clicked.disconnect()
            except:
                pass
            self.start_dasi_btn.clicked.connect(self.start_dasi)

    def showEvent(self, event):
        """Called when the window becomes visible."""
        super().showEvent(event)
        # Refresh styles to ensure correct appearance
        self.refresh_styles()

    def start_dasi(self, show_message=True):
        """Start the Dasi hotkey listener."""
        try:
            if not self.settings.get_selected_models():
                QMessageBox.warning(
                    self,
                    "No Models Selected",
                    "Please select at least one model in the Models tab before starting Dasi."
                )
                self.switch_tab(2)  # Switch to Models tab
                return

            # Check if Dasi is already running
            if DasiInstanceManager.is_running():
                # Dasi is already running
                if show_message:
                    QMessageBox.information(
                        self,
                        "Dasi Already Running",
                        "Dasi is already running. No need to start it again.",
                        QMessageBox.StandardButton.Ok
                    )
                self.update_start_button()
                return

            # Always create a new Dasi instance for a complete restart
            logging.info(
                "Creating a completely new Dasi instance for full restart")
            from main import Dasi

            # Create a new instance which initializes everything fresh
            self.dasi_instance = Dasi()

            # Set references to the new components
            self.hotkey_listener = self.dasi_instance.hotkey_listener

            # Start the hotkey listener
            if self.hotkey_listener:
                self.hotkey_listener.start()
                logging.info("Started new hotkey listener")

                if show_message:
                    QMessageBox.information(
                        self,
                        "Dasi Started",
                        "Dasi is now running. Press Ctrl+Alt+Shift+I to activate.",
                        QMessageBox.StandardButton.Ok
                    )

                # Update button to show Stop Dasi
                self.start_dasi_btn.setText("Stop Dasi")
                # Use the same theme for consistency, with slightly darker shade
                self.start_dasi_btn.setStyleSheet("""
                    QPushButton { 
                        text-align: center;
                        background-color: #d35400;
                        color: white;
                        font-weight: bold;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                    }
                    QPushButton:hover {
                        background-color: #e67e22;
                    }
                """)
                self.start_dasi_btn.setIcon(QIcon(self.stop_icon_path))
                try:
                    self.start_dasi_btn.clicked.disconnect()
                except:
                    pass
                self.start_dasi_btn.clicked.connect(self.stop_dasi)
            else:
                logging.error("Failed to create hotkey listener")
                if show_message:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Failed to create hotkey listener"
                    )

        except Exception as e:
            logging.error(f"Failed to start Dasi: {str(e)}", exc_info=True)
            if show_message:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to start Dasi: {str(e)}"
                )

    def stop_dasi(self, show_message=True):
        """Stop the Dasi hotkey listener and hide the system tray icon."""
        try:
            logging.info("Stopping Dasi completely")

            # Stop hotkey listener if it exists and is running
            if self.hotkey_listener and self.hotkey_listener.is_running():
                self.hotkey_listener.stop()
                logging.info("Hotkey listener stopped")

            # Hide the system tray icon if it exists
            if self.dasi_instance and hasattr(self.dasi_instance, 'tray') and self.dasi_instance.tray:
                self.dasi_instance.tray.hide()
                logging.info("System tray hidden")

            # Clear all references to ensure a clean restart
            self.hotkey_listener = None

            # Clear the instance from manager
            DasiInstanceManager.clear_instance()
            self.dasi_instance = None

            if show_message:
                QMessageBox.information(
                    self,
                    "Dasi Stopped",
                    "Dasi has been stopped.",
                    QMessageBox.StandardButton.Ok
                )

            # Update button to show Start Dasi
            has_models = bool(self.settings.get_selected_models())
            self.start_dasi_btn.setText(
                "Start Dasi" if has_models else "Select Models First")
            self.start_dasi_btn.setEnabled(has_models)

            # Set back to orange theme style
            self.start_dasi_btn.setStyleSheet("""
                QPushButton { 
                    text-align: center;
                    background-color: #e67e22;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #f39c12;
                }
                QPushButton:disabled {
                    background-color: #555555;
                    color: #999999;
                }
            """)
            self.start_dasi_btn.setIcon(QIcon(self.play_icon_path))
            try:
                self.start_dasi_btn.clicked.disconnect()
            except:
                pass
            self.start_dasi_btn.clicked.connect(self.start_dasi)

        except Exception as e:
            logging.error(f"Failed to stop Dasi: {str(e)}", exc_info=True)
            if show_message:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to stop Dasi: {str(e)}"
                )

    def closeEvent(self, event):
        """Handle window close event."""
        # If hotkey listener is running, minimize to tray instead of closing
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener and self.hotkey_listener.is_running():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def refresh_styles(self):
        """Force refresh of all styles in the window and child widgets."""
        # Apply to main window
        self.style().unpolish(self)
        self.style().polish(self)

        # Apply to all child widgets recursively
        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        # Update the window
        self.update()

    def handle_models_changed(self):
        """Handler for the models_changed signal from the Settings class."""
        try:
            logging.info("Models changed")

            # Update UI elements based on the new model settings
            self.update_start_button()

            # If we have a Dasi instance...
            if self.dasi_instance:
                logging.info("Notifying Dasi instance of model changes")

                # Notify all components that need to know about model changes
                if hasattr(self.dasi_instance, 'langgraph_handler'):
                    self.dasi_instance.langgraph_handler.on_models_changed()

                if hasattr(self.dasi_instance, 'ai_manager'):
                    self.dasi_instance.ai_manager.on_models_changed()

                # Other handlers that may need to know about model changes
                # These might not all exist, depending on configuration
                handlers = [
                    'vision_handler',
                    'audio_handler',
                    # 'web_search_handler', # Ensure this is removed/commented if necessary
                ]

                for handler_name in handlers:
                    if hasattr(self.dasi_instance, handler_name):
                        handler = getattr(self.dasi_instance, handler_name)
                        if hasattr(handler, 'on_models_changed'):
                            handler.on_models_changed()
            else:
                logging.info("No Dasi instance to notify about model changes")
        except Exception as e:
            logging.error(f"Error handling models changed: {e}")
            import traceback
            logging.error(traceback.format_exc())

    def _handle_examples_changed(self):
        """Handle examples changed signal from examples tab."""
        try:
            if self.dasi_instance and hasattr(self.dasi_instance, "langgraph_handler"):
                # Refresh the system prompt with the new examples
                logging.info(
                    "Examples changed, refreshing LangGraph system prompt")
                self.dasi_instance.langgraph_handler._initialize_system_prompt()
            else:
                logging.info(
                    "Examples changed, but no active Dasi instance to refresh")
        except Exception as e:
            logging.error(f"Error handling examples changed: {e}")
            import traceback
            logging.error(traceback.format_exc())


def main():
    """Run the settings window as a standalone application."""
    import sys
    from PyQt6.QtWidgets import QApplication
    from ui.assets import apply_theme

    # Create application
    app = QApplication(sys.argv)

    # Apply our custom theme
    apply_theme(app, "dark")

    # Check if Dasi is already running
    existing_instance = DasiInstanceManager.get_instance()

    # Create and show settings window
    window = SettingsWindow(dasi_instance=existing_instance)

    # Apply the theme again and do additional style processing
    # This is critical to ensure widgets are properly styled
    apply_theme(app, "dark")

    # Show the window and force style refresh
    window.show()

    # Force a style refresh one more time after the window is visible
    for widget in app.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    # Run application
    sys.exit(app.exec())
