import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QTextEdit,
    QDialog,
    QFormLayout,
    QFileDialog,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from .settings_manager import Settings


class ExampleDialog(QDialog):
    """Dialog for adding or editing jailbreak examples."""

    def __init__(self, parent=None, example=None):
        """Initialize the dialog.

        Args:
            parent: Parent widget
            example: Example to edit, or None for adding a new example
        """
        super().__init__(parent)
        self.example = example if example else {"input": "", "output": ""}
        self.setWindowTitle("Jailbreak Example")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.layout = QVBoxLayout()
        self.form_layout = QFormLayout()

        # Input field
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Enter the user's request here...")
        self.input_edit.setText(self.example["input"])
        self.form_layout.addRow("Input (request):", self.input_edit)

        # Output field
        self.output_edit = QTextEdit()
        self.output_edit.setPlaceholderText(
            "Enter the desired response here...")
        self.output_edit.setText(self.example["output"])
        self.form_layout.addRow("Output (response):", self.output_edit)

        self.layout.addLayout(self.form_layout)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)

        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.save_button)

        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

    def get_example(self):
        """Get the example data."""
        self.example["input"] = self.input_edit.toPlainText()
        self.example["output"] = self.output_edit.toPlainText()
        return self.example


class ExamplesTab(QWidget):
    """Tab for managing jailbreak examples."""

    examples_changed = pyqtSignal()

    def __init__(self, settings: Settings = None):
        """Initialize the examples tab."""
        super().__init__()
        self.settings = settings  # Store settings reference but don't use it for examples
        self.config_dir = Path(os.path.expanduser("~/.config/dasi"))
        self.examples_file = self.config_dir / "examples.json"

        self.examples = self._load_examples()

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout()

        # Create a scroll area for the content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        # Create content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # Section title
        title_label = QLabel("AI Behavior Examples")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;")
        content_layout.addWidget(title_label)

        # Description label
        description = QLabel(
            "Configure example behaviors for Dasi. These examples demonstrate to the AI "
            "how to respond to various requests, particularly those that might otherwise "
            "be restricted. Examples consist of an input (what the user asks) and the "
            "desired output (how Dasi should respond)."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "font-size: 13px; color: #cccccc; margin-bottom: 10px;")
        content_layout.addWidget(description)

        # Technical explanation
        tech_explanation = QLabel(
            "These examples are appended to the system prompt sent to the AI, providing "
            "concrete demonstrations of how to respond to user requests. Strong examples "
            "significantly improve the AI's ability to follow your desired behavior patterns."
        )
        tech_explanation.setWordWrap(True)
        tech_explanation.setStyleSheet(
            "font-size: 13px; color: #999999; font-style: italic; margin-bottom: 20px;")
        content_layout.addWidget(tech_explanation)

        # Table frame with styling
        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background-color: #222222;
                border-radius: 8px;
                border: 1px solid #333333;
            }
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # Table for examples
        self.examples_table = QTableWidget(0, 2)
        self.examples_table.setHorizontalHeaderLabels(
            ["Input (Request)", "Output (Response)"])

        # Style the table
        self.examples_table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: none;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #333333;
            }
            QTableWidget::item:selected {
                background-color: #e67e22;
                color: white;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                padding: 10px;
                font-weight: bold;
            }
        """)

        header = self.examples_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.examples_table.verticalHeader().setVisible(False)
        self.examples_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.examples_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.examples_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.examples_table.setAlternatingRowColors(True)

        table_layout.addWidget(self.examples_table)
        content_layout.addWidget(table_frame)

        # Buttons for managing examples
        button_layout = QHBoxLayout()

        # Style for buttons
        button_style = """
            QPushButton {
                background-color: #333333;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
            QPushButton[color="primary"] {
                background-color: #e67e22;
                color: white;
            }
            QPushButton[color="primary"]:hover {
                background-color: #f39c12;
            }
            QPushButton[color="danger"] {
                background-color: #e74c3c;
                color: white;
            }
            QPushButton[color="danger"]:hover {
                background-color: #c0392b;
            }
        """

        self.add_button = QPushButton("Add Example")
        self.add_button.setProperty("color", "primary")
        self.add_button.setStyleSheet(button_style)
        self.add_button.clicked.connect(self.add_example)

        self.edit_button = QPushButton("Edit Example")
        self.edit_button.setStyleSheet(button_style)
        self.edit_button.clicked.connect(self.edit_example)

        self.delete_button = QPushButton("Delete Example")
        self.delete_button.setProperty("color", "danger")
        self.delete_button.setStyleSheet(button_style)
        self.delete_button.clicked.connect(self.delete_example)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addStretch()  # Add space between edit and delete
        button_layout.addWidget(self.delete_button)

        content_layout.addLayout(button_layout)

        # Import/Export buttons
        io_layout = QHBoxLayout()

        self.import_button = QPushButton("Import Examples")
        self.import_button.setStyleSheet(button_style)
        self.import_button.clicked.connect(self.import_examples)

        self.export_button = QPushButton("Export Examples")
        self.export_button.setStyleSheet(button_style)
        self.export_button.clicked.connect(self.export_examples)

        io_layout.addWidget(self.import_button)
        io_layout.addWidget(self.export_button)
        io_layout.addStretch()  # Add space to align left

        content_layout.addLayout(io_layout)

        # Add some space at the bottom
        content_layout.addStretch()

        # Set up scroll area
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)

        # Populate the table
        self._populate_table()

    def _load_examples(self):
        """Load examples from file."""
        if not self.examples_file.exists():
            return []

        try:
            with open(self.examples_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_examples(self):
        """Save examples to file."""
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.examples_file, 'w') as f:
            json.dump(self.examples, f, indent=2)

        # Emit signal to notify of changes
        self.examples_changed.emit()

    def _populate_table(self):
        """Populate the examples table."""
        self.examples_table.setRowCount(0)

        for example in self.examples:
            row = self.examples_table.rowCount()
            self.examples_table.insertRow(row)

            # Truncate long text for display
            input_text = example["input"]
            if len(input_text) > 100:
                input_text = input_text[:97] + "..."

            output_text = example["output"]
            if len(output_text) > 100:
                output_text = output_text[:97] + "..."

            self.examples_table.setItem(row, 0, QTableWidgetItem(input_text))
            self.examples_table.setItem(row, 1, QTableWidgetItem(output_text))

    def add_example(self):
        """Add a new example."""
        dialog = ExampleDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.examples.append(dialog.get_example())
            self._save_examples()
            self._populate_table()

    def edit_example(self):
        """Edit the selected example."""
        selected_rows = self.examples_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection",
                                "Please select an example to edit.")
            return

        row = selected_rows[0].row()
        dialog = ExampleDialog(self, self.examples[row])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.examples[row] = dialog.get_example()
            self._save_examples()
            self._populate_table()

    def delete_example(self):
        """Delete the selected example."""
        selected_rows = self.examples_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection",
                                "Please select an example to delete.")
            return

        row = selected_rows[0].row()
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Confirm Deletion")
        msg_box.setText("Are you sure you want to delete this example?")
        msg_box.setInformativeText("This action cannot be undone.")
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            self.examples.pop(row)
            self._save_examples()
            self._populate_table()

    def import_examples(self):
        """Import examples from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Examples", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                imported = json.load(f)

            # Validate imported data
            if not isinstance(imported, list):
                raise ValueError("Invalid format: expected a list of examples")

            for item in imported:
                if not isinstance(item, dict) or "input" not in item or "output" not in item:
                    raise ValueError(
                        "Invalid format: each example must have 'input' and 'output' fields")

            # Confirm import
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Confirm Import")
            msg_box.setText(f"Import {len(imported)} examples?")
            msg_box.setInformativeText(
                "This will overwrite any existing examples with the same inputs.")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)

            if msg_box.exec() == QMessageBox.StandardButton.Yes:
                self.examples = imported
                self._save_examples()
                self._populate_table()

                QMessageBox.information(self, "Import Complete",
                                        f"Successfully imported {len(imported)} examples.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error",
                                 f"Failed to import examples: {str(e)}")

    def export_examples(self):
        """Export examples to a JSON file."""
        if not self.examples:
            QMessageBox.warning(self, "No Examples",
                                "There are no examples to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Examples", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, 'w') as f:
                json.dump(self.examples, f, indent=2)

            QMessageBox.information(self, "Export Complete",
                                    f"Successfully exported {len(self.examples)} examples.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error",
                                 f"Failed to export examples: {str(e)}")
