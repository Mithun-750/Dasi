from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QScrollArea,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QComboBox,
    QAbstractItemView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
)
from PyQt6.QtCore import Qt
from .settings_manager import Settings
import sys
import os
from PyQt6.QtWidgets import QApplication
import logging


class SearchableComboBox(QComboBox):
    """Custom ComboBox with search functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create search line edit
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search keys...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: none;
                background-color: #2b2b2b;
                color: white;
                border-radius: 0px;
            }
        """)

        # Create and setup the popup frame
        self.popup = QFrame(self)
        self.popup.setWindowFlags(Qt.WindowType.Popup)
        self.popup.setFrameStyle(QFrame.Shape.Box)
        self.popup.setStyleSheet("""
            QFrame {
                border: 1px solid #3f3f3f;
                background-color: #2b2b2b;
            }
        """)

        # Create scroll area for list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                outline: none;
            }
            QListWidget::item {
                padding: 5px;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #404040;
            }
            QListWidget::item:hover {
                background-color: #353535;
            }
        """)
        self.scroll.setWidget(self.list_widget)

        # Setup popup layout
        self.popup_layout = QVBoxLayout(self.popup)
        self.popup_layout.setContentsMargins(0, 0, 0, 0)
        self.popup_layout.setSpacing(0)
        self.popup_layout.addWidget(self.search_edit)
        self.popup_layout.addWidget(self.scroll)

        # Connect signals
        self.search_edit.textChanged.connect(self.filter_items)
        self.list_widget.itemClicked.connect(self.on_item_clicked)

        # Set item delegate for custom item height
        self.list_widget.setItemDelegate(QStyledItemDelegate())

    def showPopup(self):
        """Show custom popup."""
        # Position popup below the combobox
        pos = self.mapToGlobal(self.rect().bottomLeft())
        # Fixed height of 300px
        self.popup.setGeometry(pos.x(), pos.y(), self.width(), 300)

        # Clear and repopulate list widget
        self.list_widget.clear()
        for i in range(self.count()):
            item = QListWidgetItem(self.itemText(i))
            self.list_widget.addItem(item)

        self.popup.show()
        self.search_edit.setFocus()
        self.search_edit.clear()

    def hidePopup(self):
        """Hide custom popup."""
        self.popup.hide()
        super().hidePopup()

    def filter_items(self, text):
        """Filter items based on search text."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_item_clicked(self, item):
        """Handle item selection."""
        self.setCurrentText(item.text())
        self.hidePopup()


class GeneralTab(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("General Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)

        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Create a widget to hold all settings
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 20, 0)  # Right margin for scrollbar

        # Custom Instructions Section
        instructions_section = QFrame()
        instructions_layout = QVBoxLayout(instructions_section)
        instructions_layout.setSpacing(10)

        instructions_label = QLabel("Custom Instructions")
        instructions_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        instructions_description = QLabel(
            "Add your custom instructions to personalize how Dasi responds to your queries. "
            "These will be added to Dasi's core behavior."
        )
        instructions_description.setWordWrap(True)
        instructions_description.setStyleSheet("color: #888888; font-size: 12px;")

        self.custom_instructions = QTextEdit()
        self.custom_instructions.setMinimumHeight(100)
        self.custom_instructions.setPlaceholderText(
            "Example:\n- Use British English spelling\n- Include code examples in Python\n- Prefer shorter responses")
        self.custom_instructions.setStyleSheet("""
            QTextEdit {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 12px;
            }
        """)

        # Load existing custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="")
        self.custom_instructions.setText(custom_instructions)
        
        # Connect textChanged signal for auto-save
        self.custom_instructions.textChanged.connect(self._save_custom_instructions)

        instructions_layout.addWidget(instructions_label)
        instructions_layout.addWidget(instructions_description)
        instructions_layout.addWidget(self.custom_instructions)

        # LLM Settings Section
        llm_section = QFrame()
        llm_layout = QVBoxLayout(llm_section)
        llm_layout.setSpacing(10)

        llm_label = QLabel("LLM Settings")
        llm_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # Temperature setting
        temp_container = QWidget()
        temp_layout = QHBoxLayout(temp_container)
        temp_layout.setContentsMargins(0, 0, 0, 0)

        temp_label = QLabel("Temperature:")
        temp_label.setStyleSheet("font-size: 12px;")
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 1.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(self.settings.get(
            'general', 'temperature', default=0.7))
        self.temperature.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 5px;
                min-width: 80px;
            }
        """)
        
        # Connect valueChanged signal for auto-save
        self.temperature.valueChanged.connect(self._save_temperature)

        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temperature)
        temp_layout.addStretch()

        llm_layout.addWidget(llm_label)
        llm_layout.addWidget(temp_container)

        # Hotkey Settings Section
        hotkey_section = QFrame()
        hotkey_layout = QVBoxLayout(hotkey_section)
        hotkey_layout.setSpacing(10)

        hotkey_label = QLabel("Global Hotkey")
        hotkey_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        hotkey_description = QLabel(
            "Customize the global hotkey that activates Dasi. Changes will take effect after restart."
        )
        hotkey_description.setWordWrap(True)
        hotkey_description.setStyleSheet("color: #888888; font-size: 12px;")

        # Hotkey input container
        hotkey_container = QWidget()
        hotkey_layout_inner = QHBoxLayout(hotkey_container)
        hotkey_layout_inner.setContentsMargins(0, 0, 0, 0)

        # Checkboxes for modifiers
        self.ctrl_checkbox = QCheckBox("Ctrl")
        self.alt_checkbox = QCheckBox("Alt")
        self.shift_checkbox = QCheckBox("Shift")
        self.super_checkbox = QCheckBox("Super")
        self.fn_checkbox = QCheckBox("Fn")

        # Key selector
        self.key_selector = SearchableComboBox()
        # Add A-Z keys
        self.key_selector.addItems([chr(i) for i in range(65, 91)])  # A to Z
        # Add special keys
        special_keys = ['Tab', 'Space', 'Enter', 'Esc', 'Insert', 'Delete',
                        'Home', 'End', 'PgUp', 'PgDn', 'F1', 'F2', 'F3', 'F4',
                        'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12']
        self.key_selector.addItems(special_keys)

        self.key_selector.setStyleSheet("""
            QComboBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 5px;
            }
        """)

        # Load current hotkey settings
        current_hotkey = self.settings.get('general', 'hotkey', default={
            'ctrl': True,
            'alt': True,
            'shift': True,
            'super': False,
            'fn': False,
            'key': 'I'
        })

        self.ctrl_checkbox.setChecked(current_hotkey.get('ctrl', True))
        self.alt_checkbox.setChecked(current_hotkey.get('alt', True))
        self.shift_checkbox.setChecked(current_hotkey.get('shift', True))
        self.super_checkbox.setChecked(current_hotkey.get('super', False))
        self.fn_checkbox.setChecked(current_hotkey.get('fn', False))
        self.key_selector.setCurrentText(current_hotkey.get('key', 'I'))

        # Style checkboxes
        checkbox_style = """
            QCheckBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 5px 8px;
                color: #cccccc;
            }
            QCheckBox:hover {
                background-color: #404040;
            }
        """
        self.ctrl_checkbox.setStyleSheet(checkbox_style)
        self.alt_checkbox.setStyleSheet(checkbox_style)
        self.shift_checkbox.setStyleSheet(checkbox_style)
        self.super_checkbox.setStyleSheet(checkbox_style)
        self.fn_checkbox.setStyleSheet(checkbox_style)

        hotkey_layout_inner.addWidget(self.ctrl_checkbox)
        hotkey_layout_inner.addWidget(self.alt_checkbox)
        hotkey_layout_inner.addWidget(self.shift_checkbox)
        hotkey_layout_inner.addWidget(self.super_checkbox)
        hotkey_layout_inner.addWidget(self.fn_checkbox)
        hotkey_layout_inner.addWidget(self.key_selector)
        hotkey_layout_inner.addStretch()

        # Add save button for hotkey settings
        save_hotkey_button = QPushButton("Apply Hotkey")
        save_hotkey_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                max-width: 200px;
                background-color: #2b5c99;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #366bb3;
            }
            QPushButton:pressed {
                background-color: #1f4573;
                padding: 9px 16px 7px 16px;
            }
        """)
        save_hotkey_button.clicked.connect(self._save_hotkey_settings)

        hotkey_layout.addWidget(hotkey_label)
        hotkey_layout.addWidget(hotkey_description)
        hotkey_layout.addWidget(hotkey_container)
        hotkey_layout.addWidget(save_hotkey_button)

        # Startup Settings Section
        startup_section = QFrame()
        startup_layout = QVBoxLayout(startup_section)
        startup_layout.setSpacing(10)

        startup_label = QLabel("Startup Settings")
        startup_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        startup_description = QLabel(
            "Configure whether Dasi should automatically start when you log in."
        )
        startup_description.setWordWrap(True)
        startup_description.setStyleSheet("color: #888888; font-size: 12px;")

        self.startup_checkbox = QCheckBox("Start Dasi on system startup")
        self.startup_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 12px;
                padding: 5px;
            }
            QCheckBox:hover {
                background-color: #404040;
                border-radius: 4px;
            }
        """)
        
        # Load current startup setting
        self.startup_checkbox.setChecked(self.settings.get('general', 'start_on_boot', default=False))
        
        # Connect stateChanged signal for auto-save
        self.startup_checkbox.stateChanged.connect(self._save_startup_settings)

        startup_layout.addWidget(startup_label)
        startup_layout.addWidget(startup_description)
        startup_layout.addWidget(self.startup_checkbox)

        # Add sections to main layout
        layout.addWidget(instructions_section)
        layout.addWidget(llm_section)
        layout.addWidget(hotkey_section)
        layout.addWidget(startup_section)
        layout.addStretch()

        # Set scroll area widget
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _save_custom_instructions(self):
        """Auto-save custom instructions when changed."""
        self.settings.set(self.custom_instructions.toPlainText(),
                          'general', 'custom_instructions')

    def _save_temperature(self):
        """Auto-save temperature when changed."""
        self.settings.set(self.temperature.value(),
                          'general', 'temperature')

    def _save_hotkey_settings(self):
        """Save hotkey settings and prompt for restart."""
        try:
            # Save hotkey settings
            hotkey_settings = {
                'ctrl': self.ctrl_checkbox.isChecked(),
                'alt': self.alt_checkbox.isChecked(),
                'shift': self.shift_checkbox.isChecked(),
                'super': self.super_checkbox.isChecked(),
                'fn': self.fn_checkbox.isChecked(),
                'key': self.key_selector.currentText()
            }
            self.settings.set(hotkey_settings, 'general', 'hotkey')

            # Create custom message box with restart button
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Success")
            msg_box.setText("Hotkey settings saved successfully.")
            msg_box.setInformativeText(
                "Would you like to restart Dasi now for the changes to take effect?")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

            # Style the buttons
            for button in msg_box.buttons():
                if msg_box.buttonRole(button) == QMessageBox.ButtonRole.YesRole:
                    button.setStyleSheet("""
                        QPushButton {
                            background-color: #2b5c99;
                            color: white;
                            border: none;
                            padding: 6px 12px;
                            border-radius: 4px;
                        }
                        QPushButton:hover {
                            background-color: #366bb3;
                        }
                        QPushButton:pressed {
                            background-color: #1f4573;
                        }
                    """)

            response = msg_box.exec()

            if response == QMessageBox.StandardButton.Yes:
                # Get the main window (SettingsWindow)
                main_window = self.window()
                if main_window:
                    # Restart the application
                    main_window.hide()
                    QApplication.quit()
                    program = sys.executable
                    os.execl(program, program, *sys.argv)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save hotkey settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _save_startup_settings(self):
        """Auto-save startup settings when changed."""
        try:
            start_on_boot = self.startup_checkbox.isChecked()
            self.settings.set(start_on_boot, 'general', 'start_on_boot')
            self._update_startup_file(start_on_boot)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save startup settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _update_startup_file(self, enable: bool):
        """Update the startup file in the autostart directory."""
        try:
            # Get user's autostart directory
            config_dir = os.path.expanduser('~/.config/autostart')
            os.makedirs(config_dir, exist_ok=True)
            desktop_file = os.path.join(config_dir, 'dasi.desktop')

            if enable:
                # Get the executable path
                if getattr(sys, 'frozen', False):
                    # If we're running as a bundled app
                    exec_path = sys.executable
                else:
                    # If we're running in development
                    exec_path = os.path.abspath(sys.argv[0])

                # Create desktop entry content
                content = f"""[Desktop Entry]
Type=Application
Name=Dasi
Comment=Desktop AI Assistant
Exec={exec_path}
Icon=dasi
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
                # Write the desktop entry file
                with open(desktop_file, 'w') as f:
                    f.write(content)
                os.chmod(desktop_file, 0o755)
            else:
                # Remove the desktop entry file if it exists
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)

        except Exception as e:
            logging.error(f"Failed to update startup file: {str(e)}")
            raise
