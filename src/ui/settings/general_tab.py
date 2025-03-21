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
    QFileDialog,
    QSlider,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from .settings_manager import Settings
import sys
import os
from PyQt6.QtWidgets import QApplication
import logging
from PyQt6.QtCore import QDir


class SearchableComboBox(QComboBox):
    """Custom ComboBox with search functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create search line edit
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search keys...")
        self.search_edit.setProperty("class", "search-input")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #e67e22;
            }
        """)

        # Create and setup the popup frame
        self.popup = QFrame(self)
        self.popup.setWindowFlags(Qt.WindowType.Popup)
        self.popup.setFrameStyle(QFrame.Shape.NoFrame)
        self.popup.setProperty("class", "card")
        self.popup.setStyleSheet("""
            QFrame {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)

        # Create scroll area for list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
                color: #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #e67e22;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #2e2e2e;
                border-left: 2px solid #e67e22;
            }
        """)
        self.scroll.setWidget(self.list_widget)

        # Setup popup layout
        self.popup_layout = QVBoxLayout(self.popup)
        self.popup_layout.setContentsMargins(8, 8, 8, 8)
        self.popup_layout.setSpacing(8)
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


class SectionFrame(QFrame):
    """A styled frame for each section in the settings."""
    
    def __init__(self, title, description=None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        
        self.setStyleSheet("""
            QFrame.card {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "subheading")
        self.layout.addWidget(self.title_label)
        
        # Description
        if description:
            self.description_label = QLabel(description)
            self.description_label.setWordWrap(True)
            self.description_label.setProperty("class", "description")
            self.layout.addWidget(self.description_label)


class GeneralTab(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.original_values = {}
        self.has_unsaved_changes = False
        self.init_ui()
        self.save_original_values()

    def save_original_values(self):
        """Save the original values of all settings for comparison."""
        self.original_values = {
            'custom_instructions': self.settings.get('general', 'custom_instructions', default=""),
            'temperature': self.settings.get('general', 'temperature', default=0.7),
            'hotkey': self.settings.get('general', 'hotkey', default={
                'ctrl': True,
                'alt': True,
                'shift': True,
                'super': False,
                'fn': False,
                'key': 'I'
            }),
            'start_on_boot': self.settings.get('general', 'start_on_boot', default=False),
            'export_path': self.settings.get('general', 'export_path', default=os.path.expanduser("~/Documents"))
        }
        self.has_unsaved_changes = False
        self.update_button_visibility()

    def get_current_values(self):
        """Get the current values of all settings."""
        return {
            'custom_instructions': self.custom_instructions.toPlainText(),
            'temperature': self.temperature.value(),
            'hotkey': {
                'ctrl': self.ctrl_checkbox.isChecked(),
                'alt': self.alt_checkbox.isChecked(),
                'shift': self.shift_checkbox.isChecked(),
                'super': self.super_checkbox.isChecked(),
                'fn': self.fn_checkbox.isChecked(),
                'key': self.key_selector.currentText()
            },
            'start_on_boot': self.startup_checkbox.isChecked(),
            'export_path': self.export_path.text()
        }

    def check_for_changes(self):
        """Check if there are any unsaved changes."""
        current = self.get_current_values()
        self.has_unsaved_changes = any([
            current['custom_instructions'] != self.original_values['custom_instructions'],
            abs(current['temperature'] - self.original_values['temperature']) > 0.001,
            current['hotkey'] != self.original_values['hotkey'],
            current['start_on_boot'] != self.original_values['start_on_boot'],
            current['export_path'] != self.original_values['export_path']
        ])
        self.update_button_visibility()

    def update_button_visibility(self):
        """Update the visibility of action buttons based on changes."""
        self.button_container.setVisible(self.has_unsaved_changes)

    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)  # Adjusted right padding

        # Get the checkmark path based on running mode
        if getattr(sys, 'frozen', False):
            # Running as bundled PyInstaller app
            base_path = sys._MEIPASS
            checkmark_path = os.path.join(base_path, "assets", "icons", "checkmark.svg")
            logging.info(f"Using frozen app checkmark at: {checkmark_path}")
        else:
            # Running in development
            app_dir = QDir.currentPath()
            checkmark_path = f"{app_dir}/src/ui/assets/icons/checkmark.svg"
            logging.info(f"Using development checkmark at: {checkmark_path}")

        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        # Create a widget to hold all settings
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)  # Adjusted right padding

        # Custom Instructions Section
        instructions_section = SectionFrame(
            "Custom Instructions",
            "Add custom instructions that will be included in every prompt. "
            "These instructions will influence how Dasi responds to your queries. "
            "Note: Changes require restarting the Dasi service or using the 'Save & Apply' button to take full effect."
        )
        
        self.custom_instructions = QTextEdit()
        self.custom_instructions.setMinimumHeight(120)
        self.custom_instructions.setPlaceholderText(
            "Example:\n- Use British English spelling\n- Include code examples in Python\n- Prefer shorter responses")

        # Load existing custom instructions
        custom_instructions = self.settings.get(
            'general', 'custom_instructions', default="")
        self.custom_instructions.setText(custom_instructions)
        
        # Connect textChanged signal for auto-save
        self.custom_instructions.textChanged.connect(self._on_any_change)
        
        instructions_section.layout.addWidget(self.custom_instructions)
        layout.addWidget(instructions_section)

        # LLM Settings Section
        llm_section = SectionFrame(
            "LLM Settings",
            "Temperature controls the randomness of responses. Lower values (0.0) make responses more deterministic, "
            "while higher values (1.0) make them more creative. "
            "Note: Changes require restarting the Dasi service or using the 'Save & Apply' button to take full effect."
        )
        
        # Temperature setting
        temp_container = QWidget()
        temp_container.setProperty("class", "transparent-container")
        temp_container.setStyleSheet("background-color: transparent;")
        temp_layout = QHBoxLayout(temp_container)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_layout.setSpacing(12)

        temp_label = QLabel("Temperature:")
        
        # Create a slider for temperature
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)  # 0.0 to 1.0 with 100 steps
        self.temp_slider.setValue(int(self.settings.get('general', 'temperature', default=0.7) * 100))
        self.temp_slider.setMinimumWidth(150)
        self.temp_slider.setStyleSheet("""
            QSlider {
                background-color: transparent;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background-color: #333333;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background-color: #e67e22;
                border: none;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background-color: #e67e22;
                border-radius: 2px;
            }
        """)
        
        # Keep the spin box for precise control but make it smaller
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 1.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(self.settings.get('general', 'temperature', default=0.7))
        self.temperature.setFixedWidth(70)
        self.temperature.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 3px;
                color: white;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #e67e22;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #333333;
                width: 16px;
                border: none;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #e67e22;
            }
        """)
        
        # Connect signals for syncing slider and spin box
        self.temp_slider.valueChanged.connect(self._sync_temp_from_slider)
        self.temperature.valueChanged.connect(self._sync_temp_from_spinbox)
        
        # Connect change signal
        self.temperature.valueChanged.connect(self._on_any_change)

        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_slider, 1)  # Give slider more space
        temp_layout.addWidget(self.temperature)

        llm_section.layout.addWidget(temp_container)
        layout.addWidget(llm_section)

        # Hotkey Settings Section
        hotkey_section = SectionFrame(
            "Global Hotkey",
            "Customize the global hotkey that activates Dasi. "
            "Changes require restarting the Dasi service to take effect."
        )

        # Hotkey input container
        hotkey_container = QWidget()
        hotkey_container.setProperty("class", "transparent-container")
        hotkey_container.setStyleSheet("background-color: transparent;")
        hotkey_layout = QHBoxLayout(hotkey_container)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        hotkey_layout.setSpacing(8)

        # Checkboxes for modifiers
        self.ctrl_checkbox = QCheckBox("Ctrl")
        self.alt_checkbox = QCheckBox("Alt")
        self.shift_checkbox = QCheckBox("Shift")
        self.super_checkbox = QCheckBox("Super")
        self.fn_checkbox = QCheckBox("Fn")
        
        # Apply consistent checkbox styling
        checkbox_style = f"""
            QCheckBox {{
                color: #e0e0e0;
                font-size: 12px;
                spacing: 5px;
                outline: none;
                border: none;
            }}
            QCheckBox:focus, QCheckBox:hover {{
                outline: none;
                border: none;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid #444444;
                border-radius: 3px;
                background-color: #2a2a2a;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2d2d2d;
                border: 1px solid #e67e22;
                image: url("{checkmark_path}");
            }}
            QCheckBox::indicator:hover {{
                border-color: #e67e22;
                background-color: #333333;
            }}
            QCheckBox:hover {{
                color: #ffffff;
                outline: none;
                border: none;
            }}
        """
        
        self.ctrl_checkbox.setStyleSheet(checkbox_style)
        self.alt_checkbox.setStyleSheet(checkbox_style)
        self.shift_checkbox.setStyleSheet(checkbox_style)
        self.super_checkbox.setStyleSheet(checkbox_style)
        self.fn_checkbox.setStyleSheet(checkbox_style)

        # Key selector
        self.key_selector = SearchableComboBox()
        # Add A-Z keys
        self.key_selector.addItems([chr(i) for i in range(65, 91)])  # A to Z
        # Add special keys
        special_keys = ['Tab', 'Space', 'Enter', 'Esc', 'Insert', 'Delete',
                        'Home', 'End', 'PgUp', 'PgDn', 'F1', 'F2', 'F3', 'F4',
                        'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12']
        self.key_selector.addItems(special_keys)

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

        hotkey_layout.addWidget(self.ctrl_checkbox)
        hotkey_layout.addWidget(self.alt_checkbox)
        hotkey_layout.addWidget(self.shift_checkbox)
        hotkey_layout.addWidget(self.super_checkbox)
        hotkey_layout.addWidget(self.fn_checkbox)
        hotkey_layout.addWidget(self.key_selector)
        hotkey_layout.addStretch()

        hotkey_section.layout.addWidget(hotkey_container)
        layout.addWidget(hotkey_section)

        # Startup Settings Section
        startup_section = SectionFrame(
            "Startup Settings",
            "Configure whether Dasi should automatically start when you log in."
        )

        self.startup_checkbox = QCheckBox("Start Dasi on system startup")
        self.startup_checkbox.setStyleSheet(checkbox_style)
        
        # Load current startup setting
        self.startup_checkbox.setChecked(self.settings.get('general', 'start_on_boot', default=False))
        
        # Connect stateChanged signal for auto-save
        self.startup_checkbox.stateChanged.connect(self._on_any_change)

        startup_section.layout.addWidget(self.startup_checkbox)
        layout.addWidget(startup_section)

        # Export Location Settings Section
        export_section = SectionFrame(
            "Export Location",
            "Set the default location where exported files will be saved."
        )

        # Create container for path input and browse button
        path_container = QWidget()
        path_container.setProperty("class", "transparent-container")
        path_container.setStyleSheet("background-color: transparent;")
        path_layout = QHBoxLayout(path_container)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)

        self.export_path = QLineEdit()
        self.export_path.setPlaceholderText("Default: ~/Documents")
        self.export_path.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #e67e22;
            }
        """)
        
        # Load current export path setting
        current_path = self.settings.get('general', 'export_path', default=os.path.expanduser("~/Documents"))
        self.export_path.setText(current_path)
        
        # Connect textChanged signal for auto-save
        self.export_path.textChanged.connect(self._on_any_change)
        
        browse_button = QPushButton("Browse")
        browse_button.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #333333;
                border-left: 2px solid #e67e22;
                color: white;
            }
        """)
        browse_button.clicked.connect(self._browse_export_path)

        path_layout.addWidget(self.export_path)
        path_layout.addWidget(browse_button)

        export_section.layout.addWidget(path_container)
        layout.addWidget(export_section)

        # Add spacing at the bottom
        layout.addStretch()

        # Set scroll area widget
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Create button container at the bottom
        self.button_container = QWidget()
        self.button_container.setProperty("class", "transparent-container")
        self.button_container.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(self.button_container)
        button_layout.setContentsMargins(0, 16, 0, 0)
        button_layout.setSpacing(8)

        # Add Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #333333;
                color: white;
            }
        """)
        cancel_button.clicked.connect(self._cancel_changes)

        # Add Reset button
        reset_button = QPushButton("Reset")
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #333333;
                color: white;
            }
        """)
        reset_button.clicked.connect(self._reset_changes)

        # Add Save & Apply button
        save_all_button = QPushButton("Save & Apply")
        save_all_button.setProperty("class", "primary")
        save_all_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
        """)
        save_all_button.clicked.connect(self._apply_all_settings)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(save_all_button)

        main_layout.addWidget(self.button_container)
        self.button_container.hide()  # Initially hide the buttons

        # Connect change signals
        self.custom_instructions.textChanged.connect(self._on_any_change)
        self.temperature.valueChanged.connect(self._on_any_change)
        self.ctrl_checkbox.stateChanged.connect(self._on_any_change)
        self.alt_checkbox.stateChanged.connect(self._on_any_change)
        self.shift_checkbox.stateChanged.connect(self._on_any_change)
        self.super_checkbox.stateChanged.connect(self._on_any_change)
        self.fn_checkbox.stateChanged.connect(self._on_any_change)
        self.key_selector.currentTextChanged.connect(self._on_any_change)
        self.startup_checkbox.stateChanged.connect(self._on_any_change)
        self.export_path.textChanged.connect(self._on_any_change)

    def _on_any_change(self):
        """Handler for any change in the settings."""
        self.check_for_changes()

    def _cancel_changes(self):
        """Cancel all changes and restore original values."""
        # Restore original values
        self.custom_instructions.setText(self.original_values['custom_instructions'])
        self.temperature.setValue(self.original_values['temperature'])
        
        hotkey = self.original_values['hotkey']
        self.ctrl_checkbox.setChecked(hotkey['ctrl'])
        self.alt_checkbox.setChecked(hotkey['alt'])
        self.shift_checkbox.setChecked(hotkey['shift'])
        self.super_checkbox.setChecked(hotkey['super'])
        self.fn_checkbox.setChecked(hotkey['fn'])
        self.key_selector.setCurrentText(hotkey['key'])
        
        self.startup_checkbox.setChecked(self.original_values['start_on_boot'])
        self.export_path.setText(self.original_values['export_path'])
        
        self.has_unsaved_changes = False
        self.update_button_visibility()

    def _reset_changes(self):
        """Reset all settings to their default values."""
        self.custom_instructions.setText("")
        self.temperature.setValue(0.7)
        
        self.ctrl_checkbox.setChecked(True)
        self.alt_checkbox.setChecked(True)
        self.shift_checkbox.setChecked(True)
        self.super_checkbox.setChecked(False)
        self.fn_checkbox.setChecked(False)
        self.key_selector.setCurrentText('I')
        
        self.startup_checkbox.setChecked(False)
        self.export_path.setText(os.path.expanduser("~/Documents"))
        
        self.check_for_changes()

    def _save_custom_instructions(self):
        """Auto-save custom instructions when changed."""
        # Remove auto-save functionality
        pass

    def _save_temperature(self):
        """Auto-save temperature when changed."""
        # Remove auto-save functionality
        pass

    def _save_startup_settings(self):
        """Auto-save startup settings when changed."""
        # Remove auto-save functionality
        pass

    def _save_export_path(self):
        """Auto-save export path when changed."""
        # Remove auto-save functionality
        pass

    def _apply_all_settings(self):
        """Save and apply all settings at once."""
        try:
            # Save custom instructions
            self.settings.set(self.custom_instructions.toPlainText(),
                            'general', 'custom_instructions')
            self.settings.custom_instructions_changed.emit()
            
            # Save temperature
            self.settings.set(self.temperature.value(),
                            'general', 'temperature')
            self.settings.temperature_changed.emit()
            
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
            
            # Save startup settings
            start_on_boot = self.startup_checkbox.isChecked()
            self.settings.set(start_on_boot, 'general', 'start_on_boot')
            self._update_startup_file(start_on_boot)
            
            # Save export path
            path = self.export_path.text()
            if '~' in path:
                path = os.path.expanduser(path)
            self.settings.set(path, 'general', 'export_path')
            
            # Update original values and hide buttons
            self.save_original_values()
            
            # Create custom message box with restart button
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Settings Applied")
            msg_box.setText("All settings have been saved successfully.")
            msg_box.setInformativeText(
                "For the changes to take full effect, would you like to restart the Dasi service now?")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

            # Style the buttons
            for button in msg_box.buttons():
                if msg_box.buttonRole(button) == QMessageBox.ButtonRole.YesRole:
                    button.setStyleSheet("""
                        QPushButton {
                            background-color: #e67e22;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 6px 12px;
                            font-weight: bold;
                        }
                        QPushButton:hover {
                            background-color: #f39c12;
                        }
                    """)

            response = msg_box.exec()

            if response == QMessageBox.StandardButton.Yes:
                self._restart_dasi_service()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _restart_dasi_service(self):
        """Helper method to restart Dasi service with a single message."""
        main_window = self.window()
        if main_window and hasattr(main_window, 'stop_dasi') and hasattr(main_window, 'start_dasi'):
            # Stop Dasi without showing message
            main_window.stop_dasi(show_message=False)
            
            # Small delay to ensure proper shutdown
            QTimer.singleShot(500, lambda: self._start_dasi_after_stop(main_window))

    def _start_dasi_after_stop(self, main_window):
        """Helper method to start Dasi after stopping."""
        # Start Dasi without showing message
        main_window.start_dasi(show_message=False)
        
        # Show a single success message
        QMessageBox.information(
            self,
            "Success",
            "Dasi service has been restarted successfully.",
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

    def _browse_export_path(self):
        """Open a file dialog to select an export path."""
        try:
            # Open a file dialog to select a directory
            directory = QFileDialog.getExistingDirectory(self, "Select Export Location")
            if directory:
                self.export_path.setText(directory)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to browse export path: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _sync_temp_from_slider(self, value):
        """Sync temperature value from slider to spin box."""
        # Prevent infinite loop by blocking signals
        self.temperature.blockSignals(True)
        self.temperature.setValue(value / 100.0)
        self.temperature.blockSignals(False)
        self._on_any_change()
        
    def _sync_temp_from_spinbox(self, value):
        """Sync temperature value from spin box to slider."""
        # Prevent infinite loop by blocking signals
        self.temp_slider.blockSignals(True)
        self.temp_slider.setValue(int(value * 100))
        self.temp_slider.blockSignals(False)
        self._on_any_change()
