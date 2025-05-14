import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt

from ..general_tab import SectionFrame
from .ui_components import RoundLabel, RoundButton, SearchableComboBox


class FilenameModelsComponent(QWidget):
    """Component for managing filename suggester models."""

    # Signal for when filename model is changed
    filename_model_changed = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        """Initialize the UI for the filename models component."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Filename Models Section
        self.filename_section = SectionFrame(
            "Filename Suggester Model",
            "Select one model to handle filename suggestions for generated content. Choose a model with good text understanding capabilities."
        )

        # Filename model selection container
        filename_model_container = QWidget()
        filename_model_container.setProperty("class", "transparent-container")
        filename_model_layout = QVBoxLayout(filename_model_container)
        filename_model_layout.setContentsMargins(0, 0, 0, 0)
        filename_model_layout.setSpacing(8)

        # Create selection row container
        selection_row = QWidget()
        selection_row_layout = QHBoxLayout(selection_row)
        selection_row_layout.setContentsMargins(0, 0, 0, 0)
        selection_row_layout.setSpacing(8)

        # Create filename model dropdown
        self.filename_model_dropdown = SearchableComboBox()
        self.filename_model_dropdown.setMinimumWidth(300)

        # Set initial loading state
        self.set_loading_state()

        # Add Filename Model button with modern styling
        add_filename_button = QPushButton("Add Filename Model")
        add_filename_button.setProperty("class", "primary")
        add_filename_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #a04000;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        add_filename_button.clicked.connect(self.add_filename_model)
        self.add_filename_button = add_filename_button

        # Add dropdown and button to selection row
        selection_row_layout.addWidget(self.filename_model_dropdown)
        selection_row_layout.addWidget(add_filename_button)
        selection_row_layout.addStretch()

        # Add selection row to container
        filename_model_layout.addWidget(selection_row)

        # Create container for displaying the selected filename model
        self.filename_model_display = QWidget()
        self.filename_model_display.setProperty(
            "class", "transparent-container")
        self.filename_model_display.setVisible(False)  # Hide initially
        filename_model_display_layout = QVBoxLayout(
            self.filename_model_display)
        filename_model_display_layout.setContentsMargins(0, 8, 0, 0)
        filename_model_display_layout.setSpacing(0)

        # Add the display container to the main layout
        filename_model_layout.addWidget(self.filename_model_display)

        # Description label
        filename_model_description = QLabel(
            "This model will be used specifically for generating filename suggestions. If none is selected, the default chat model will be used."
        )
        filename_model_description.setStyleSheet("""
            color: #aaaaaa;
            font-size: 12px;
            margin-top: 4px;
        """)
        filename_model_description.setWordWrap(True)
        filename_model_layout.addWidget(filename_model_description)

        self.filename_section.layout.addWidget(filename_model_container)
        layout.addWidget(self.filename_section)

        # Load filename model display immediately, without waiting for models to be fetched
        self.update_filename_model_display()

    def set_loading_state(self):
        """Set the dropdown to loading state."""
        self.filename_model_dropdown.clear()
        self.filename_model_dropdown.addItem("Loading models...")
        self.filename_model_dropdown.setEnabled(False)
        if hasattr(self, 'add_filename_button'):
            self.add_filename_button.setEnabled(False)

    def populate_models(self, models):
        """Populate the filename models dropdown with models."""
        # Clear the dropdown entirely
        self.filename_model_dropdown.clear()

        # Add "None" option at index 0
        self.filename_model_dropdown.addItem("None (Use Default Model)")

        # Add all models to the filename dropdown
        for model in models:
            display_text = f"{model['name']} ({model['provider']})"
            # Add model to dropdown and store the full model info in user data
            self.filename_model_dropdown.addItem(display_text, model)

            # Create and set tooltip for the item
            from .model_fetcher import create_model_tooltip
            tooltip = create_model_tooltip(model)
            index = self.filename_model_dropdown.count() - 1
            self.filename_model_dropdown.setItemData(
                index, tooltip, 3)  # 3 is ToolTipRole

        # Enable the dropdown and button now that models are loaded
        self.filename_model_dropdown.setEnabled(True)
        if hasattr(self, 'add_filename_button'):
            self.add_filename_button.setEnabled(True)

        # Load current selected filename model
        self.load_filename_model()

    def load_filename_model(self):
        """Load the saved filename model from settings."""
        # Get the saved filename model info
        filename_model_info = self.settings.get_filename_model_info()

        # Update the display regardless of dropdown state
        self.update_filename_model_display()

        # Only try to set the dropdown if we have models loaded and filename model info exists
        # Only "None" option or no filename model
        if self.filename_model_dropdown.count() <= 1 or not filename_model_info:
            self.filename_model_dropdown.setCurrentIndex(0)  # Set to "None"
            return

        # Try to find the model in the dropdown
        for i in range(1, self.filename_model_dropdown.count()):
            item_data = self.filename_model_dropdown.itemData(
                i, Qt.ItemDataRole.UserRole)
            if (isinstance(item_data, dict) and
                item_data.get('id') == filename_model_info.get('id') and
                    item_data.get('provider') == filename_model_info.get('provider')):
                self.filename_model_dropdown.setCurrentIndex(i)
                return

        # If we get here, the saved model isn't in the current dropdown
        self.filename_model_dropdown.setCurrentIndex(0)
        logging.info(
            f"Saved filename model {filename_model_info.get('id', 'N/A')} not found in current model list, but keeping configuration."
        )

    def add_filename_model(self):
        """Add the selected filename model to settings."""
        current_index = self.filename_model_dropdown.currentIndex()
        if current_index <= 0:  # 0 is "None"
            # Clear filename model
            self.settings.set_filename_model_info(None)
            self.settings.save_settings()
            self.update_filename_model_display()
            self.filename_model_changed.emit()

            QMessageBox.information(
                self,
                "Filename Model Updated",
                "Filename suggester will use the default chat model.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Get the full model info dictionary from the dropdown
        model_info = self.filename_model_dropdown.itemData(
            current_index, Qt.ItemDataRole.UserRole)
        if not model_info or not isinstance(model_info, dict):
            logging.error(f"Invalid filename model data: {model_info}")
            return

        # Save the model info
        self.settings.set_filename_model_info(model_info)
        self.settings.save_settings()

        # Update the display
        self.update_filename_model_display()

        # Emit signal
        self.filename_model_changed.emit()

        # Show confirmation
        QMessageBox.information(
            self,
            "Filename Model Updated",
            f"Filename suggester model set to: {model_info['name']}.\nThis model will be used for generating filename suggestions.",
            QMessageBox.StandardButton.Ok
        )

    def update_filename_model_display(self):
        """Update the filename model display area."""
        # Clear existing widgets from display
        for i in reversed(range(self.filename_model_display.layout().count())):
            widget = self.filename_model_display.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Get current filename model info
        filename_model_info = self.settings.get_filename_model_info()

        if not filename_model_info:
            self.filename_model_display.setVisible(False)
            return

        # Create a widget similar to the model list items but for a single model
        model_widget = QWidget()
        model_widget.setObjectName("filenameModelItem")
        model_widget.setStyleSheet("""
            #filenameModelItem {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        # Create tooltip for the filename model
        from .model_fetcher import create_model_tooltip
        tooltip = create_model_tooltip(filename_model_info)
        model_widget.setToolTip(tooltip)

        layout = QHBoxLayout(model_widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Content layout for text
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # Create name and provider labels
        name_label = QLabel(filename_model_info['name'])
        name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
        """)

        provider_label = QLabel(f"Provider: {filename_model_info['provider']}")
        provider_label.setStyleSheet("""
            font-size: 12px;
            color: #aaaaaa;
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
        """)

        # Add labels to content layout
        content_layout.addWidget(name_label)
        content_layout.addWidget(provider_label)

        # Add content layout to main layout
        layout.addLayout(content_layout, 1)

        # Create actions layout
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)
        actions_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Add "Filename Model" indicator label
        filename_label = RoundLabel("Filename Model")
        actions_layout.addWidget(filename_label)

        # Remove button
        remove_btn = RoundButton("×")
        remove_btn.setFixedSize(28, 28)
        remove_btn.clicked.connect(self.remove_filename_model)
        actions_layout.addWidget(remove_btn)

        # Add actions layout to main layout
        layout.addLayout(actions_layout)

        # Add the model widget to the display layout
        self.filename_model_display.layout().addWidget(model_widget)
        self.filename_model_display.setVisible(True)

    def remove_filename_model(self):
        """Remove the current filename model."""
        self.settings.set_filename_model_info(None)
        self.settings.save_settings()
        self.update_filename_model_display()
        # Reset dropdown to "None"
        self.filename_model_dropdown.setCurrentIndex(0)
        # Emit signal
        self.filename_model_changed.emit()

        QMessageBox.information(
            self,
            "Filename Model Removed",
            "Filename suggester will use the default chat model.",
            QMessageBox.StandardButton.Ok
        )

    def check_model_in_use(self, model_id):
        """Check if a model is being used as the filename model."""
        filename_model_info = self.settings.get_filename_model_info()
        if filename_model_info and filename_model_info.get('id') == model_id:
            return True
        return False
