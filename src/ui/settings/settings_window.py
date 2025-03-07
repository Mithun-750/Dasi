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
)
from PyQt6.QtCore import Qt, QObject
import qdarktheme
import logging
import socket

from .settings_manager import Settings
from .api_keys_tab import APIKeysTab
from .models_tab import ModelsTab
from .general_tab import GeneralTab
from .prompt_chunks_tab import PromptChunksTab
from instance_manager import DasiInstanceManager


class SidebarButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px 20px;
                border: none;
                border-radius: 0;
                font-size: 14px;
                color: #cccccc;
            }
            QPushButton:checked {
                background-color: #404040;
                color: white;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)


class ActionButton(QPushButton):
    """Button for actions like Start Dasi."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                text-align: center;
                padding: 12px 20px;
                border: none;
                background-color: #2b5c99;
                color: white;
                font-weight: bold;
                font-size: 14px;
                margin: 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
            QPushButton:pressed {
                background-color: #1f4573;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #666666;
            }
        """)


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
            self.hotkey_listener = self.dasi_instance.hotkey_listener
            
        self.init_ui()
        
        # Connect models tab changes to update button
        self.models_tab.models_changed.connect(self.update_start_button)
        
        # Check if Dasi is already running
        self.check_dasi_running()

    def init_ui(self):
        self.setWindowTitle("Dasi Settings")
        self.setMinimumSize(800, 500)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create sidebar
        sidebar = QFrame()
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-right: 1px solid #3f3f3f;
            }
        """)
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(0)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        # Create sidebar buttons
        self.general_btn = SidebarButton("General")
        self.api_keys_btn = SidebarButton("API Keys")
        self.models_btn = SidebarButton("Models")
        self.prompt_chunks_btn = SidebarButton("Prompt Chunks")

        sidebar_layout.addWidget(self.general_btn)
        sidebar_layout.addWidget(self.api_keys_btn)
        sidebar_layout.addWidget(self.models_btn)
        sidebar_layout.addWidget(self.prompt_chunks_btn)
        sidebar_layout.addStretch()

        # Add Start Dasi button at the bottom
        self.start_dasi_btn = ActionButton("Start Dasi")
        self.start_dasi_btn.clicked.connect(self.start_dasi)
        sidebar_layout.addWidget(self.start_dasi_btn)

        # Create stacked widget for content
        self.content = QStackedWidget()
        self.content.setStyleSheet("""
            QStackedWidget {
                background-color: #323232;
            }
        """)

        # Create and add tabs
        self.general_tab = GeneralTab(self.settings)
        self.api_keys_tab = APIKeysTab(self.settings)
        self.models_tab = ModelsTab(self.settings)
        self.prompt_chunks_tab = PromptChunksTab(self.settings)

        self.content.addWidget(self.general_tab)
        self.content.addWidget(self.api_keys_tab)
        self.content.addWidget(self.models_tab)
        self.content.addWidget(self.prompt_chunks_tab)

        # Connect button signals
        self.general_btn.clicked.connect(lambda: self.switch_tab(0))
        self.api_keys_btn.clicked.connect(lambda: self.switch_tab(1))
        self.models_btn.clicked.connect(lambda: self.switch_tab(2))
        self.prompt_chunks_btn.clicked.connect(lambda: self.switch_tab(3))
        
        # Connect API key cleared signal to remove models by provider
        self.api_keys_tab.api_key_cleared.connect(self.models_tab.remove_models_by_provider)

        # Add widgets to main layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.content)

        # Set initial tab
        self.switch_tab(0)

        # Update Start Dasi button state
        self.update_start_button()

    def switch_tab(self, index: int):
        """Switch to the specified tab."""
        self.content.setCurrentIndex(index)

        # Update button states
        buttons = [self.general_btn, self.api_keys_btn, self.models_btn, self.prompt_chunks_btn]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)

    def check_dasi_running(self):
        """Check if Dasi is already running and update UI accordingly."""
        # If we already have a Dasi instance, it's running
        if self.dasi_instance and self.hotkey_listener and self.hotkey_listener.is_running():
            # Update button to show Stop Dasi
            self.start_dasi_btn.setText("Stop Dasi")
            self.start_dasi_btn.setEnabled(True)
            
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
                self.hotkey_listener = self.dasi_instance.hotkey_listener
            
            # Update button to show Stop Dasi
            self.start_dasi_btn.setText("Stop Dasi")
            self.start_dasi_btn.setEnabled(True)
            
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
        """Update the state of the Start Dasi button based on selected models and running state."""
        try:
            # First check if we already have a Dasi instance that's running
            if self.dasi_instance and self.hotkey_listener and self.hotkey_listener.is_running():
                self.start_dasi_btn.setText("Stop Dasi")
                self.start_dasi_btn.setEnabled(True)
                
                # Ensure the button is connected to stop_dasi
                try:
                    self.start_dasi_btn.clicked.disconnect()
                except:
                    pass
                self.start_dasi_btn.clicked.connect(self.stop_dasi)
                return
            
            # Otherwise check using the socket method
            if DasiInstanceManager.is_running():
                # If Dasi is running
                # Try to get the existing Dasi instance if available
                existing_instance = DasiInstanceManager.get_instance()
                if existing_instance:
                    self.dasi_instance = existing_instance
                    self.hotkey_listener = self.dasi_instance.hotkey_listener
                
                self.start_dasi_btn.setText("Stop Dasi")
                self.start_dasi_btn.setEnabled(True)
                
                # Ensure the button is connected to stop_dasi
                try:
                    self.start_dasi_btn.clicked.disconnect()
                except:
                    pass
                self.start_dasi_btn.clicked.connect(self.stop_dasi)
            else:
                # If Dasi is not running
                has_models = bool(self.settings.get_selected_models())
                self.start_dasi_btn.setEnabled(has_models)
                self.start_dasi_btn.setText("Start Dasi" if has_models else "Select Models First")
                
                # Ensure the button is connected to start_dasi
                try:
                    self.start_dasi_btn.clicked.disconnect()
                except:
                    pass
                self.start_dasi_btn.clicked.connect(self.start_dasi)
        except Exception as e:
            logging.error(f"Error updating start button: {str(e)}")
            self.start_dasi_btn.setEnabled(False)
            self.start_dasi_btn.setText("Error")

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

            # Initialize Dasi instance if not already initialized
            existing_instance = DasiInstanceManager.get_instance()
            if not existing_instance:
                from main import Dasi
                self.dasi_instance = Dasi()
                # Note: Dasi constructor now registers itself with DasiInstanceManager
                self.hotkey_listener = self.dasi_instance.hotkey_listener
            else:
                self.dasi_instance = existing_instance
                self.hotkey_listener = self.dasi_instance.hotkey_listener

            # Start the hotkey listener if it's not already running
            if not self.hotkey_listener or not self.hotkey_listener.is_running():
                self.hotkey_listener.start()
                if show_message:
                    QMessageBox.information(
                        self,
                        "Dasi Started",
                        "Dasi is now running. Press Ctrl+Alt+Shift+I to activate.",
                        QMessageBox.StandardButton.Ok
                    )
                
                # Update button to show Stop Dasi
                self.start_dasi_btn.setText("Stop Dasi")
                try:
                    self.start_dasi_btn.clicked.disconnect()
                except:
                    pass
                self.start_dasi_btn.clicked.connect(self.stop_dasi)

        except Exception as e:
            if show_message:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to start Dasi: {str(e)}"
                )
            
    def stop_dasi(self, show_message=True):
        """Stop the Dasi hotkey listener and hide the system tray icon."""
        try:
            if self.hotkey_listener and self.hotkey_listener.is_running():
                self.hotkey_listener.stop()
                
                # Hide the system tray icon if it exists
                if self.dasi_instance and hasattr(self.dasi_instance, 'tray') and self.dasi_instance.tray:
                    self.dasi_instance.tray.hide()
                
                if show_message:
                    QMessageBox.information(
                        self,
                        "Dasi Stopped",
                        "Dasi has been stopped.",
                        QMessageBox.StandardButton.Ok
                    )
            
            # Clear the instance from manager
            DasiInstanceManager.clear_instance()
            self.dasi_instance = None
            
            # Update button to show Start Dasi
            has_models = bool(self.settings.get_selected_models())
            self.start_dasi_btn.setText("Start Dasi" if has_models else "Select Models First")
            self.start_dasi_btn.setEnabled(has_models)
            try:
                self.start_dasi_btn.clicked.disconnect()
            except:
                pass
            self.start_dasi_btn.clicked.connect(self.start_dasi)
            
        except Exception as e:
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


def main():
    """Run the settings window as a standalone application."""
    import sys
    from PyQt6.QtWidgets import QApplication
    import qdarktheme
    
    # Create application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    qdarktheme.setup_theme("dark")
    
    # Check if Dasi is already running
    existing_instance = DasiInstanceManager.get_instance()
    
    # Create and show settings window
    window = SettingsWindow(dasi_instance=existing_instance)
    window.show()
    
    # Run application
    sys.exit(app.exec())
