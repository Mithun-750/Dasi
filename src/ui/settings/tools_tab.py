import logging
import sys
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, QLabel, QHBoxLayout, QSpacerItem, QSizePolicy, QFrame,
    QPushButton, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from .settings_manager import Settings
from .general_tab import SectionFrame


class HorizontalLine(QFrame):
    """A simple horizontal line separator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setStyleSheet("background-color: #333333; max-height: 1px;")


class ToolsTab(QWidget):
    """Settings tab for enabling/disabling available LLM tools."""
    settings_changed = pyqtSignal()

    def __init__(self, settings: Settings, parent: QWidget = None):
        super().__init__(parent)
        self.settings = settings
        self.original_values = {}
        self.unsaved_changes = {}
        self.has_unsaved_changes = False

        # Store references to checkboxes
        self.checkboxes = {}

        # Get checkmark path for styling checkboxes
        if getattr(sys, 'frozen', False):
            # Running as bundled PyInstaller app
            base_path = sys._MEIPASS
            self.checkmark_path = os.path.join(
                base_path, "assets", "icons", "checkmark.svg")
            logging.info(
                f"Using frozen app checkmark at: {self.checkmark_path}")
        else:
            # Running in development
            app_dir = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
            self.checkmark_path = os.path.join(
                app_dir, "ui", "assets", "icons", "checkmark.svg")
            logging.info(
                f"Using development checkmark at: {self.checkmark_path}")

        self._setup_ui()
        self.load_settings()
        self.save_original_values()

    def save_original_values(self):
        """Save the original values based on the current checkbox states after loading."""
        try:
            self.original_values = self._get_current_values()  # Get state *after* loading
            logging.debug(
                f"Saved original ToolsTab values: {self.original_values}")
            self.has_unsaved_changes = False
            self._update_button_visibility()  # Ensure buttons are hidden initially
        except Exception as e:
            logging.error(f"Error saving original values: {e}", exc_info=True)

    def _get_current_values(self) -> dict:
        """Get the current values from UI elements (checkboxes)."""
        try:
            return {key: checkbox.isChecked() for key, checkbox in self.checkboxes.items()}
        except Exception as e:
            logging.error(f"Error getting current values: {e}", exc_info=True)
            return {}

    def _setup_ui(self):
        """Set up the UI layout and widgets."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Define tool info (Title, Description, Setting Key)
        tool_info = [
            ("Web Search Tool", "Allow the AI to search the web for current information or scrape content from links.", "web_search_enabled"),
            ("System Info Tool", "Allow the AI to access basic system information (CPU, memory).",
             "system_info_enabled"),
            ("Terminal Command Tool", "Allow the AI to execute terminal commands (requires user confirmation).",
             "terminal_command_enabled")
        ]

        for title, description, setting_key in tool_info:
            section_frame = SectionFrame(title, description, self)
            # Use the correct setting_key when creating the checkbox
            self._create_tool_checkbox(title.replace(
                " Tool", ""), description, section_frame.layout, setting_key)
            main_layout.addWidget(section_frame)

        # Spacer to push content up
        main_layout.addStretch()

        # --- Action Buttons ---
        self.button_container = QWidget()
        self.button_container.setProperty("class", "transparent-container")
        self.button_container.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(self.button_container)
        button_layout.setContentsMargins(0, 16, 0, 0)
        button_layout.setSpacing(8)

        # Add Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self._cancel_changes)

        # Add Reset button
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._reset_changes)

        # Add Save button
        save_button = QPushButton("Save")
        save_button.setProperty("class", "primary")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #a04000;
            }
        """)
        save_button.clicked.connect(self._apply_all_settings)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(save_button)

        main_layout.addWidget(self.button_container)
        self.button_container.hide()  # Initially hide the buttons

        self.setLayout(main_layout)

    def _create_tool_checkbox(self, title: str, description: str, layout: QVBoxLayout, setting_key: str):
        """Helper to create a checkbox, storing it with its setting_key."""
        try:
            checkbox = QCheckBox(f"Enable {title}")
            # Use setting_key as object name for identification
            checkbox.setObjectName(setting_key)
            checkbox.toggled.connect(self._check_for_changes)

            # Apply consistent checkbox styling
            checkbox_style = f"""
                QCheckBox {{
                    color: #e0e0e0;
                    font-size: 13px;
                    spacing: 5px;
                    outline: none;
                    border: none;
                    padding: 4px;
                }}
                QCheckBox:focus, QCheckBox:hover {{
                    outline: none;
                    border: none;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 1px solid #444444;
                    border-radius: 3px;
                    background-color: #2a2a2a;
                }}
                QCheckBox::indicator:checked {{
                    background-color: #2d2d2d;
                    border: 1px solid #e67e22;
                    image: url("{self.checkmark_path}");
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
            checkbox.setStyleSheet(checkbox_style)

            desc_label = QLabel(description)
            desc_label.setProperty("class", "secondary-text")
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                "color: #aaaaaa; font-size: 12px; padding-left: 4px;")

            checkbox_layout = QHBoxLayout()
            checkbox_layout.setContentsMargins(0, 0, 0, 8)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.addSpacerItem(QSpacerItem(
                10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
            checkbox_layout.addWidget(desc_label, 1)

            layout.addLayout(checkbox_layout)
            layout.addWidget(HorizontalLine())

            # Store the checkbox using the setting_key
            self.checkboxes[setting_key] = checkbox
            # No return needed as we store it directly
        except Exception as e:
            logging.error(f"Error creating tool checkbox: {e}", exc_info=True)

    def load_settings(self):
        """Load settings from the SettingsManager into checkboxes."""
        logging.debug("Loading Tools tab settings")
        if not self.checkboxes:
            logging.warning(
                "Checkboxes not yet initialized during load_settings call.")
            # Need to ensure _setup_ui runs first, which it should in __init__
            return
        try:
            for key, checkbox in self.checkboxes.items():
                value = self.settings.get('tools', key, default=True)
                # Block signals temporarily to prevent _check_for_changes during load
                checkbox.blockSignals(True)
                checkbox.setChecked(value)
                checkbox.blockSignals(False)
            # Call save_original_values *after* loading initial state
            self.save_original_values()
            self.unsaved_changes.clear()
            self.has_unsaved_changes = False
            self._update_button_visibility()
        except Exception as e:
            logging.error(f"Error loading tools settings: {e}", exc_info=True)

    def save_settings(self):
        """Save the current settings based on unsaved_changes."""
        # This method is primarily called by _apply_all_settings now
        logging.debug(
            f"Saving Tools tab unsaved changes: {self.unsaved_changes}")
        if not self.unsaved_changes:
            logging.debug("No unsaved changes in Tools tab to save.")
            return False  # Indicate nothing was saved

        try:
            for key, value in self.unsaved_changes.items():
                success = self.settings.set(
                    'tools', key, value)  # set() handles saving
                if not success:
                    logging.error(f"Failed to save setting: tools.{key}")
                    # Optionally raise an error or show a message
                    # raise IOError(f"Failed to save setting: tools.{key}")
            self.unsaved_changes.clear()
            self.save_original_values()  # Update original values after successful save
            logging.info("Tools settings saved successfully.")
            self.settings_changed.emit()
            return True  # Indicate save was successful
        except Exception as e:
            logging.error(f"Error saving tools settings: {e}", exc_info=True)
            return False  # Indicate save failed

    def reset_settings(self):
        """Reset settings to default for this tab in the Settings object."""
        logging.debug("Resetting Tools tab settings in Settings object")
        try:
            keys_to_reset = list(self.checkboxes.keys())
            for key in keys_to_reset:
                self.settings.set('tools', key, True)  # Set to default True
            self.settings_changed.emit()  # Emit signal after resetting
            return True
        except Exception as e:
            logging.error(
                f"Error resetting tools settings: {e}", exc_info=True)
            return False

    def _check_for_changes(self, checked):
        """Handle checkbox toggles and track unsaved changes."""
        try:
            sender_checkbox = self.sender()
            if not isinstance(sender_checkbox, QCheckBox):
                return

            # Find the setting key associated with this checkbox
            setting_key = sender_checkbox.objectName()
            if not setting_key:
                logging.warning(
                    "Checkbox signal received, but sender has no objectName (setting_key).")
                return

            logging.debug(f"Tool setting changed: {setting_key} = {checked}")

            original_value = self.original_values.get(
                setting_key, True)  # Default to True if not found

            if checked != original_value:
                self.unsaved_changes[setting_key] = checked
                logging.debug(
                    f"Added to unsaved changes: {setting_key}={checked}")
            elif setting_key in self.unsaved_changes:
                # Value changed back to the original saved value, remove from unsaved
                del self.unsaved_changes[setting_key]
                logging.debug(f"Removed from unsaved changes: {setting_key}")

            # Update overall flag
            self.has_unsaved_changes = bool(self.unsaved_changes)
            self._update_button_visibility()
        except Exception as e:
            logging.error(f"Error checking for changes: {e}", exc_info=True)
            # Don't show error dialog here to avoid spamming the user

    def _update_button_visibility(self):
        """Update the visibility of save, cancel, and reset buttons."""
        try:
            self.button_container.setVisible(self.has_unsaved_changes)
        except Exception as e:
            logging.error(
                f"Error updating button visibility: {e}", exc_info=True)

    def _cancel_changes(self):
        """Cancel changes and revert checkboxes to original values."""
        logging.debug("Canceling changes in Tools tab")
        try:
            for key, original_value in self.original_values.items():
                if key in self.checkboxes:
                    # Block signals to prevent _check_for_changes during cancel
                    self.checkboxes[key].blockSignals(True)
                    self.checkboxes[key].setChecked(original_value)
                    self.checkboxes[key].blockSignals(False)
            self.unsaved_changes.clear()
            self.has_unsaved_changes = False
            self._update_button_visibility()
            logging.info("Changes canceled and reverted to original values.")
            # No need to emit settings_changed as nothing was saved
        except Exception as e:
            logging.error(
                f"Error canceling changes in Tools tab: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to cancel changes: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _reset_changes(self):
        """Reset checkboxes to default (True) and show buttons."""
        logging.debug("Resetting checkboxes in Tools tab to default")
        try:
            self.unsaved_changes.clear()  # Clear previous unsaved changes
            for key, checkbox in self.checkboxes.items():
                # Block signals to prevent _check_for_changes during reset
                checkbox.blockSignals(True)
                checkbox.setChecked(True)  # Set UI to default
                checkbox.blockSignals(False)
                # Check if this default state differs from the original saved state
                original_value = self.original_values.get(key, True)
                if True != original_value:
                    # Mark as unsaved if default differs
                    self.unsaved_changes[key] = True

            self.has_unsaved_changes = bool(self.unsaved_changes)
            self._update_button_visibility()  # Show buttons if reset caused changes
            logging.info(
                "Checkboxes reset to default (True). Click Save to apply.")
            # No need to emit settings_changed yet, only after save
        except Exception as e:
            logging.error(
                f"Error resetting checkboxes in Tools tab: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to reset to defaults: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _apply_all_settings(self):
        """Apply all changes and save settings."""
        logging.debug("Applying all changes in Tools tab")
        if not self.unsaved_changes:
            logging.info("No changes to apply in Tools tab.")
            return

        try:
            if self.save_settings():  # save_settings now returns True/False
                self.has_unsaved_changes = False
                self._update_button_visibility()  # Hide buttons on successful save
                logging.info("All changes applied and saved.")

                # Show restart dialog
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Settings Saved")
                msg_box.setText("Tool settings have been saved successfully.")
                msg_box.setInformativeText(
                    "Changes to Tool settings require restarting the Dasi service to take full effect.\\n\\nWould you like to restart now?"
                )
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

                # Style the Yes button
                for button in msg_box.buttons():
                    if msg_box.buttonRole(button) == QMessageBox.ButtonRole.YesRole:
                        button.setProperty("class", "primary")
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
                        # Ensure style is applied correctly
                        button.style().unpolish(button)
                        button.style().polish(button)

                response = msg_box.exec()

                if response == QMessageBox.StandardButton.Yes:
                    logging.info("User selected to restart Dasi service")
                    self._restart_dasi_service()
                else:
                    logging.info("User chose not to restart Dasi service")
            else:
                logging.error("Failed to save settings during apply.")
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to save settings.",
                    QMessageBox.StandardButton.Ok
                )
        except Exception as e:
            logging.error(
                f"Error applying all changes in Tools tab: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to apply settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _restart_dasi_service(self):
        """Helper method to restart Dasi service with a complete reset."""
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, 'stop_dasi') and hasattr(main_window, 'start_dasi'):
                logging.info(
                    "Performing full restart of Dasi service from Tools tab")

                # Stop Dasi without showing message
                main_window.stop_dasi(show_message=False)

                # Small delay to ensure proper shutdown before restarting
                QTimer.singleShot(
                    500, lambda: self._start_dasi_after_stop(main_window))
            else:
                logging.error(
                    "Could not restart Dasi: main window lacks required methods")
                QMessageBox.warning(
                    self,
                    "Restart Failed",
                    "Could not restart Dasi service. Please restart manually.",
                    QMessageBox.StandardButton.Ok
                )
        except Exception as e:
            logging.error(f"Error during restart: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Restart Error",
                f"Failed to restart Dasi: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _start_dasi_after_stop(self, main_window):
        """Helper method to start Dasi after stopping with complete reinitialization."""
        try:
            # Start Dasi without showing message - this will create a new instance
            main_window.start_dasi(show_message=False)

            # Show a single success message
            QMessageBox.information(
                self,
                "Success",
                "Dasi service has been restarted successfully with all new settings applied.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            logging.error(f"Error restarting Dasi: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Restart Error",
                f"Failed to restart Dasi: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
