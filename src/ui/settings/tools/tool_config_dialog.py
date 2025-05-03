import os
import logging
from typing import Dict, Any, Optional, Callable

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QLabel
from PyQt6.QtCore import Qt

from .json_schema_form import JSONSchemaForm


class ToolConfigDialog(QDialog):
    """Dialog for editing tool configuration."""

    def __init__(
        self,
        tool_name: str,
        schema_path: str,
        config_path: Optional[str] = None,
        apply_callback: Optional[Callable[[], bool]] = None,
        parent=None
    ):
        """
        Initialize the tool configuration dialog.

        Args:
            tool_name: The name of the tool
            schema_path: Path to the JSON schema file
            config_path: Path to the configuration file (optional)
            apply_callback: Callback to notify when configuration is applied
            parent: Parent widget
        """
        super().__init__(parent)
        self.tool_name = tool_name
        self.schema_path = schema_path
        self.config_path = config_path
        self.apply_callback = apply_callback
        self.config_data = {}

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(f"{self.tool_name} Configuration")
        self.resize(600, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)  # Add overall dialog padding
        layout.setSpacing(12)  # Add spacing between elements

        # Title
        title = QLabel(f"Configure {self.tool_name}")
        # Enhanced title styling with bottom margin
        title.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #eeeeee; 
            margin-bottom: 10px; /* Added bottom margin */
        """)
        layout.addWidget(title)

        # Create JSON schema form
        try:
            self.form = JSONSchemaForm(
                schema_path=self.schema_path,
                config_path=self.config_path,
                save_callback=self._on_save,
                parent=self
            )
            layout.addWidget(self.form)
        except Exception as e:
            logging.error(f"Error creating form: {e}")
            error_label = QLabel(f"Error loading configuration: {str(e)}")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _on_save(self, config: Dict[str, Any]):
        """
        Handle save events from the form.

        Args:
            config: The new configuration data
        """
        self.config_data = config
        logging.info(f"Tool config saved for {self.tool_name}")

        # Apply the configuration if a callback was provided
        if self.apply_callback:
            try:
                success = self.apply_callback()
                if success:
                    logging.info(
                        f"Configuration applied successfully for {self.tool_name}")
                else:
                    logging.warning(
                        f"Failed to apply configuration for {self.tool_name}")
            except Exception as e:
                logging.error(f"Error applying configuration: {e}")

    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration.

        Returns:
            The current configuration data
        """
        return self.config_data
