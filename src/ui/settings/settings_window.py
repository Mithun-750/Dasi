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
from PyQt6.QtCore import Qt
import qdarktheme

from .settings_manager import Settings
from .api_keys_tab import APIKeysTab
from .models_tab import ModelsTab
from .general_tab import GeneralTab
from .prompt_chunks_tab import PromptChunksTab


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
                font-weight: bold;
            }
            QPushButton:hover:!checked {
                background-color: #353535;
                color: white;
            }
        """)


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.init_ui()

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

        # Add widgets to main layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.content)

        # Set initial tab
        self.switch_tab(0)

    def switch_tab(self, index: int):
        """Switch to the specified tab."""
        self.content.setCurrentIndex(index)

        # Update button states
        buttons = [self.general_btn, self.api_keys_btn, self.models_btn, self.prompt_chunks_btn]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)

    def launch_main_app(self):
        """Launch the main Dasi application."""
        try:
            from main import Dasi
            self.hide()  # Hide settings window
            app = Dasi()
            app.run()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to launch Dasi: {str(e)}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarktheme.load_stylesheet("dark"))

    window = SettingsWindow()
    window.show()

    sys.exit(app.exec())
