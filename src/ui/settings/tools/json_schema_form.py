import json
import logging
import os
import sys
from typing import Dict, Any, Callable, Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QCheckBox,
    QLabel, QPushButton, QHBoxLayout, QScrollArea, QTabWidget,
    QGroupBox, QSizePolicy, QListWidget, QListWidgetItem, QFrame,
    QTextEdit, QDoubleSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal


class JSONSchemaForm(QWidget):
    """A dynamic form generator based on JSON schema."""

    form_changed = pyqtSignal()

    def __init__(
        self,
        schema_path: str,
        config_path: Optional[str] = None,
        save_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the form.

        Args:
            schema_path: Path to the JSON schema file
            config_path: Path to the existing configuration file (optional)
            save_callback: Callback function to call when save is clicked
            parent: Parent widget
        """
        super().__init__(parent)
        self.schema_path = schema_path
        self.config_path = config_path
        self.save_callback = save_callback
        self.schema = {}
        self.config = {}
        self.form_widgets = {}
        self.has_changes = False
        self.checkmark_path = self._get_checkmark_path()

        self._load_schema()
        self._load_config()
        self._setup_ui()

    def _load_schema(self):
        """Load the JSON schema."""
        try:
            if not os.path.exists(self.schema_path):
                logging.error(f"Schema file not found: {self.schema_path}")
                return

            with open(self.schema_path, 'r') as f:
                self.schema = json.load(f)
                logging.debug(f"Loaded schema from {self.schema_path}")
        except Exception as e:
            logging.error(f"Error loading JSON schema: {e}")
            self.schema = {}

    def _load_config(self):
        """Load the configuration file if it exists."""
        try:
            if self.config_path and os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                    logging.debug(f"Loaded config from {self.config_path}")
            else:
                logging.info(
                    f"No config file found at {self.config_path}, using defaults")
                # Initialize with default values from schema
                self.config = self._get_default_values(self.schema)
        except Exception as e:
            logging.error(f"Error loading config file: {e}")
            self.config = {}

    def _get_default_values(self, schema_part, path=""):
        """Recursively extract default values from schema."""
        result = {}

        if not schema_part or "properties" not in schema_part:
            return result

        for prop_name, prop_schema in schema_part.get("properties", {}).items():
            current_path = f"{path}.{prop_name}" if path else prop_name

            if prop_schema.get("type") == "object":
                result[prop_name] = self._get_default_values(
                    prop_schema, current_path)
            elif "default" in prop_schema:
                result[prop_name] = prop_schema["default"]
            elif prop_schema.get("type") == "array":
                result[prop_name] = []
            elif prop_schema.get("type") == "string":
                result[prop_name] = ""
            elif prop_schema.get("type") == "integer" or prop_schema.get("type") == "number":
                result[prop_name] = 0
            elif prop_schema.get("type") == "boolean":
                result[prop_name] = False

        return result

    def _get_checkmark_path(self):
        """Get the path to the checkmark icon."""
        if getattr(sys, 'frozen', False):
            # Running as bundled PyInstaller app
            base_path = sys._MEIPASS
            return os.path.join(base_path, "assets", "icons", "checkmark.svg")
        else:
            # Running in development - Go up one more level due to file move
            app_dir = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # Added one more dirname
            return os.path.join(app_dir, "ui", "assets", "icons", "checkmark.svg")

    def _setup_ui(self):
        """Set up the form user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create a scroll area for the form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # Create the form container
        form_container = QWidget()
        self.form_layout = QVBoxLayout(form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(16)

        # Generate form from schema
        if self.schema:
            self._generate_form(self.schema, self.config, self.form_layout)
        else:
            self.form_layout.addWidget(QLabel("Error: Could not load schema"))

        # Add buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 16, 0, 0)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._reset_form)

        self.save_button = QPushButton("Save")
        self.save_button.setProperty("class", "primary")
        self.save_button.clicked.connect(self._save_form)

        button_layout.addWidget(self.reset_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)

        self.form_layout.addLayout(button_layout)

        # Set up scroll area
        scroll_area.setWidget(form_container)
        main_layout.addWidget(scroll_area)

        # Update button states
        self._update_buttons()

    def _generate_form(self, schema, config, layout, path=""):
        """
        Recursively generate form widgets based on schema.

        Args:
            schema: The schema or schema part to process
            config: The config values to use
            layout: The layout to add widgets to
            path: The current path in the object tree
        """
        if "properties" not in schema:
            return

        properties = schema.get("properties", {})

        for prop_name, prop_schema in properties.items():
            current_path = f"{path}.{prop_name}" if path else prop_name
            prop_type = prop_schema.get("type")

            # Skip unsupported types
            if not prop_type:
                continue

            # Handle objects (create sections)
            if prop_type == "object":
                group_box = QGroupBox(prop_schema.get(
                    "title", prop_name.replace("_", " ").title()))
                group_layout = QVBoxLayout(group_box)

                # Add description if available
                if prop_schema.get("description"):
                    desc_label = QLabel(prop_schema["description"])
                    desc_label.setWordWrap(True)
                    desc_label.setStyleSheet(
                        "color: #999999; font-size: 12px; margin-bottom: 8px;")
                    group_layout.addWidget(desc_label)

                # Generate form for this object's properties
                self._generate_form(
                    prop_schema,
                    config.get(prop_name, {}),
                    group_layout,
                    current_path
                )

                layout.addWidget(group_box)

            # Handle arrays of objects (create a list with add/remove)
            elif prop_type == "array" and prop_schema.get("items", {}).get("type") == "object":
                self._create_array_widget(
                    prop_name, prop_schema, config, layout, current_path)

            # Handle primitive types
            else:
                form_layout = QFormLayout()
                form_layout.setContentsMargins(0, 0, 0, 0)
                form_layout.setSpacing(8)

                # Create the appropriate widget based on type
                widget = self._create_widget_for_property(
                    prop_name,
                    prop_schema,
                    config.get(prop_name),
                    current_path
                )

                if widget:
                    # Store the widget reference
                    self.form_widgets[current_path] = widget

                    # Create label
                    label = QLabel(prop_schema.get(
                        "title", prop_name.replace("_", " ").title()))

                    # Add to form
                    form_layout.addRow(label, widget)

                    # Add description if available
                    if prop_schema.get("description"):
                        desc_label = QLabel(prop_schema["description"])
                        desc_label.setWordWrap(True)
                        desc_label.setStyleSheet(
                            "color: #999999; font-size: 12px; margin-top: -4px;")
                        form_layout.addRow("", desc_label)

                    layout.addLayout(form_layout)

    def _create_widget_for_property(self, prop_name, prop_schema, value, path):
        """
        Create an appropriate widget for a property based on its type.

        Args:
            prop_name: The name of the property
            prop_schema: The schema for the property
            value: The current value
            path: The path to this property

        Returns:
            The created widget or None if type is not supported
        """
        prop_type = prop_schema.get("type")

        if prop_type == "string":
            widget = QLineEdit()
            if value is not None:
                widget.setText(str(value))
            # Add padding to line edits
            widget.setStyleSheet("padding: 4px 6px;")
            widget.textChanged.connect(lambda: self._on_form_changed(path))
            return widget

        elif prop_type == "integer":
            widget = QSpinBox()
            if "minimum" in prop_schema:
                widget.setMinimum(prop_schema["minimum"])
            if "maximum" in prop_schema:
                widget.setMaximum(prop_schema["maximum"])
            if value is not None:
                widget.setValue(int(value))
            # Add padding to spin boxes
            widget.setStyleSheet("padding: 4px 6px;")
            widget.valueChanged.connect(lambda: self._on_form_changed(path))
            return widget

        elif prop_type == "number":
            widget = QDoubleSpinBox()
            if "minimum" in prop_schema:
                widget.setMinimum(prop_schema["minimum"])
            if "maximum" in prop_schema:
                widget.setMaximum(prop_schema["maximum"])
            if value is not None:
                widget.setValue(float(value))
            # Add padding to double spin boxes
            widget.setStyleSheet("padding: 4px 6px;")
            widget.valueChanged.connect(lambda: self._on_form_changed(path))
            return widget

        elif prop_type == "boolean":
            widget = QCheckBox()
            if value is not None:
                widget.setChecked(bool(value))
            widget.toggled.connect(lambda: self._on_form_changed(path))
            # Apply consistent checkbox styling (copied from web_search_tab)
            checkbox_style = f"""
                QCheckBox {{
                    color: #e0e0e0;
                    font-size: 13px;
                    spacing: 5px;
                    outline: none;
                    border: none;
                    padding: 4px; /* Added padding */
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
            widget.setStyleSheet(checkbox_style)
            return widget

        elif prop_type == "array" and "enum" in prop_schema.get("items", {}):
            # Create a combo box for enums
            widget = QComboBox()
            for item in prop_schema["items"]["enum"]:
                widget.addItem(str(item))
            if value is not None and value in prop_schema["items"]["enum"]:
                widget.setCurrentText(str(value))
            widget.currentIndexChanged.connect(
                lambda: self._on_form_changed(path))
            return widget

        return None

    def _create_array_widget(self, prop_name, prop_schema, config, layout, path):
        """
        Create a widget for an array of objects with add/remove functionality.

        Args:
            prop_name: The name of the property
            prop_schema: The schema for the property
            config: The config values
            layout: The layout to add to
            path: The current path
        """
        # Create a group for the array
        group_box = QGroupBox(prop_schema.get(
            "title", prop_name.replace("_", " ").title()))
        group_layout = QVBoxLayout(group_box)

        # Add description if available
        if prop_schema.get("description"):
            desc_label = QLabel(prop_schema["description"])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #999999; font-size: 12px;")
            group_layout.addWidget(desc_label)

        # Create a list widget to show the items
        list_widget = QListWidget()
        list_widget.setFrameShape(QFrame.Shape.NoFrame)
        # Remove hover effect and selection highlight
        list_widget.setStyleSheet("""
            QListWidget::item:hover { background-color: transparent; }
            QListWidget::item:selected { background-color: transparent; color: #e0e0e0; }
        """)
        list_widget.setFocusPolicy(
            Qt.FocusPolicy.NoFocus)  # Prevent focus rectangle

        # Store reference to the list widget
        self.form_widgets[path] = list_widget

        # Add items from config
        items = config.get(prop_name, [])
        for i, item in enumerate(items):
            item_widget = self._create_array_item_widget(
                prop_schema["items"], item, f"{path}[{i}]")
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            list_widget.addItem(list_item)
            list_widget.setItemWidget(list_item, item_widget)

        group_layout.addWidget(list_widget)

        # Add button to add new items
        add_button = QPushButton("Add Item")
        add_button.clicked.connect(lambda: self._add_array_item(
            list_widget, prop_schema["items"], path))

        group_layout.addWidget(add_button)
        layout.addWidget(group_box)

    def _create_array_item_widget(self, item_schema, item_data, path):
        """
        Create a widget for an array item.

        Args:
            item_schema: The schema for the array item
            item_data: The data for this item
            path: The path to this item

        Returns:
            A widget representing the array item
        """
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 8, 0, 8)

        # Item form
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(4)
        form_layout.setVerticalSpacing(8)

        # Process each property in the item
        for prop_name, prop_schema in item_schema.get("properties", {}).items():
            current_path = f"{path}.{prop_name}"

            # Create widget for this property
            widget = self._create_widget_for_property(
                prop_name,
                prop_schema,
                item_data.get(prop_name),
                current_path
            )

            if widget:
                # Store the widget
                self.form_widgets[current_path] = widget

                # Create label
                label = QLabel(prop_schema.get(
                    "title", prop_name.replace("_", " ").title()))

                # Add to form
                form_layout.addRow(label, widget)

        container_layout.addLayout(form_layout)

        # Buttons for item management
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 8, 0, 0)

        # Delete button
        delete_button = QPushButton("Remove")
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #6e3030;
                color: #f0d0d0;
                border: 1px solid #8e4040;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #8e4040;
                color: #ffffff;
                border: 1px solid #ae5050;
            }
            QPushButton:pressed {
                background-color: #5e2020;
            }
        """)
        delete_button.clicked.connect(
            lambda: self._remove_array_item(container, path))

        buttons_layout.addStretch(1)
        buttons_layout.addWidget(delete_button)

        container_layout.addLayout(buttons_layout)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #333333; max-height: 1px;")

        container_layout.addWidget(separator)

        return container

    def _add_array_item(self, list_widget, item_schema, path):
        """
        Add a new item to an array.

        Args:
            list_widget: The list widget to add to
            item_schema: The schema for items in this array
            path: The path to the array
        """
        # Generate default data
        item_data = self._get_default_values(item_schema)

        # Create index for the new item
        item_index = list_widget.count()
        item_path = f"{path}[{item_index}]"

        # Create widget for the new item
        item_widget = self._create_array_item_widget(
            item_schema, item_data, item_path)

        # Add to list
        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())
        list_widget.addItem(list_item)
        list_widget.setItemWidget(list_item, item_widget)

        # Mark form as changed
        self._on_form_changed(path)

    def _remove_array_item(self, item_widget, path):
        """
        Remove an item from an array.

        Args:
            item_widget: The widget to remove
            path: The path to the item
        """
        # Find the list widget that contains this item
        list_widget = None
        # Extract array path from the item path
        array_path = path.split('[')[0]

        if array_path in self.form_widgets:
            list_widget = self.form_widgets[array_path]

        if list_widget and isinstance(list_widget, QListWidget):
            # Find the item in the list
            for i in range(list_widget.count()):
                if list_widget.itemWidget(list_widget.item(i)) == item_widget:
                    # Remove the item
                    list_widget.takeItem(i)
                    break

        # Mark form as changed
        self._on_form_changed(array_path)

        # Clean up the removed widgets from form_widgets
        # This is important to avoid memory leaks and invalid references
        keys_to_remove = []
        for widget_path in self.form_widgets:
            if widget_path.startswith(path):
                keys_to_remove.append(widget_path)

        for key in keys_to_remove:
            del self.form_widgets[key]

    def _on_form_changed(self, path):
        """
        Handle changes in the form.

        Args:
            path: The path of the changed widget
        """
        self.has_changes = True
        self._update_buttons()
        self.form_changed.emit()

    def _update_buttons(self):
        """Update button states based on form state."""
        self.reset_button.setEnabled(self.has_changes)
        self.save_button.setEnabled(self.has_changes)

    def _reset_form(self):
        """Reset the form to the initial values."""
        # Reload config
        self._load_config()

        # Update all widgets with config values
        self._reset_widgets_from_config(self.schema, self.config)

        # Update state
        self.has_changes = False
        self._update_buttons()

    def _reset_widgets_from_config(self, schema, config, path=""):
        """
        Reset widgets to match the config values.

        Args:
            schema: The schema or schema part
            config: The config values
            path: The current path
        """
        if "properties" not in schema:
            return

        for prop_name, prop_schema in schema.get("properties", {}).items():
            current_path = f"{path}.{prop_name}" if path else prop_name
            prop_type = prop_schema.get("type")

            if prop_type == "object":
                # Recursively reset object properties
                self._reset_widgets_from_config(
                    prop_schema,
                    config.get(prop_name, {}),
                    current_path
                )
            elif prop_type == "array" and prop_schema.get("items", {}).get("type") == "object":
                # Handle array of objects - more complex reset required
                list_widget = self.form_widgets.get(current_path)
                if list_widget and isinstance(list_widget, QListWidget):
                    # Clear the list
                    list_widget.clear()

                    # Rebuild from config
                    items = config.get(prop_name, [])
                    for i, item in enumerate(items):
                        item_widget = self._create_array_item_widget(
                            prop_schema["items"],
                            item,
                            f"{current_path}[{i}]"
                        )
                        list_item = QListWidgetItem()
                        list_item.setSizeHint(item_widget.sizeHint())
                        list_widget.addItem(list_item)
                        list_widget.setItemWidget(list_item, item_widget)
            elif current_path in self.form_widgets:
                # Reset primitive type widgets
                widget = self.form_widgets[current_path]
                value = config.get(prop_name)

                # Temporarily block signals to prevent recursive change events
                widget.blockSignals(True)

                if isinstance(widget, QLineEdit):
                    widget.setText(str(value) if value is not None else "")
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value) if value is not None else 0)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value) if value is not None else 0.0)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(
                        bool(value) if value is not None else False)
                elif isinstance(widget, QComboBox):
                    if value is not None:
                        widget.setCurrentText(str(value))

                widget.blockSignals(False)

    def _save_form(self):
        """Save the form values to the configuration."""
        try:
            # Collect values from form
            config = self._collect_form_values(self.schema)

            # Call save callback if provided
            if self.save_callback:
                self.save_callback(config)

            # Save to file if path provided
            if self.config_path:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                logging.info(f"Saved config to {self.config_path}")

            # Update state
            self.config = config
            self.has_changes = False
            self._update_buttons()
        except Exception as e:
            logging.error(f"Error saving form: {e}")

    def _collect_form_values(self, schema, path=""):
        """
        Recursively collect values from form widgets based on schema.

        Args:
            schema: The schema or schema part
            path: The current path

        Returns:
            Dict with collected values
        """
        result = {}

        if "properties" not in schema:
            return result

        for prop_name, prop_schema in schema.get("properties", {}).items():
            current_path = f"{path}.{prop_name}" if path else prop_name
            prop_type = prop_schema.get("type")

            if prop_type == "object":
                # Recursively collect object properties
                result[prop_name] = self._collect_form_values(
                    prop_schema, current_path)
            elif prop_type == "array" and prop_schema.get("items", {}).get("type") == "object":
                # Collect array of objects
                result[prop_name] = self._collect_array_values(
                    current_path, prop_schema["items"])
            elif current_path in self.form_widgets:
                # Collect primitive type values
                widget = self.form_widgets[current_path]

                if isinstance(widget, QLineEdit):
                    result[prop_name] = widget.text()
                elif isinstance(widget, QSpinBox):
                    result[prop_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    result[prop_name] = widget.value()
                elif isinstance(widget, QCheckBox):
                    result[prop_name] = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    result[prop_name] = widget.currentText()

        return result

    def _collect_array_values(self, array_path, item_schema):
        """
        Collect values from an array of objects.

        Args:
            array_path: The path to the array
            item_schema: The schema for items in the array

        Returns:
            List of collected item values
        """
        result = []

        # Get the list widget
        list_widget = self.form_widgets.get(array_path)
        if not list_widget or not isinstance(list_widget, QListWidget):
            return result

        # Process each item in the list
        for i in range(list_widget.count()):
            item_path = f"{array_path}[{i}]"
            item_data = {}

            # Collect values for each property in the item
            for prop_name, prop_schema in item_schema.get("properties", {}).items():
                prop_path = f"{item_path}.{prop_name}"

                if prop_path in self.form_widgets:
                    widget = self.form_widgets[prop_path]

                    if isinstance(widget, QLineEdit):
                        item_data[prop_name] = widget.text()
                    elif isinstance(widget, QSpinBox):
                        item_data[prop_name] = widget.value()
                    elif isinstance(widget, QDoubleSpinBox):
                        item_data[prop_name] = widget.value()
                    elif isinstance(widget, QCheckBox):
                        item_data[prop_name] = widget.isChecked()
                    elif isinstance(widget, QComboBox):
                        item_data[prop_name] = widget.currentText()

            result.append(item_data)

        return result
