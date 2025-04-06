import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt

from ..general_tab import SectionFrame
from .ui_components import RoundLabel, RoundButton, SearchableComboBox


class VisionModelsComponent(QWidget):
    """Component for managing vision models."""

    vision_model_changed = pyqtSignal()  # Signal for when vision model is changed

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        """Initialize the UI for the vision models component."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Vision Models Section
        self.vision_section = SectionFrame(
            "Vision Models",
            "Select one model to handle image processing in multimodal conversations. Only select models that support image analysis."
        )

        # Vision model selection container
        vision_model_container = QWidget()
        vision_model_container.setProperty("class", "transparent-container")
        vision_model_layout = QVBoxLayout(vision_model_container)
        vision_model_layout.setContentsMargins(0, 0, 0, 0)
        vision_model_layout.setSpacing(8)

        # Create selection row container
        selection_row = QWidget()
        selection_row_layout = QHBoxLayout(selection_row)
        selection_row_layout.setContentsMargins(0, 0, 0, 0)
        selection_row_layout.setSpacing(8)

        # Create vision model dropdown
        self.vision_model_dropdown = SearchableComboBox()
        self.vision_model_dropdown.setMinimumWidth(300)

        # Set initial loading state
        self.set_loading_state()

        # Add Vision Model button with modern styling
        add_vision_button = QPushButton("Add Vision Model")
        add_vision_button.setProperty("class", "primary")
        add_vision_button.setStyleSheet("""
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
        add_vision_button.clicked.connect(self.add_vision_model)
        self.add_vision_button = add_vision_button

        # Add dropdown and button to selection row
        selection_row_layout.addWidget(self.vision_model_dropdown)
        selection_row_layout.addWidget(add_vision_button)
        selection_row_layout.addStretch()

        # Add selection row to container
        vision_model_layout.addWidget(selection_row)

        # Create container for displaying the selected vision model
        self.vision_model_display = QWidget()
        self.vision_model_display.setProperty("class", "transparent-container")
        self.vision_model_display.setVisible(False)  # Hide initially
        vision_model_display_layout = QVBoxLayout(self.vision_model_display)
        vision_model_display_layout.setContentsMargins(0, 8, 0, 0)
        vision_model_display_layout.setSpacing(0)

        # Add the display container to the main layout
        vision_model_layout.addWidget(self.vision_model_display)

        # Description label
        vision_model_description = QLabel(
            "Only models with vision capabilities (like GPT-4o, Gemini, Claude 3) will properly process images."
        )
        vision_model_description.setStyleSheet("""
            color: #aaaaaa;
            font-size: 12px;
            margin-top: 4px;
        """)
        vision_model_description.setWordWrap(True)
        vision_model_layout.addWidget(vision_model_description)

        self.vision_section.layout.addWidget(vision_model_container)
        layout.addWidget(self.vision_section)

        # Load vision model display immediately, without waiting for models to be fetched
        self.update_vision_model_display()

    def set_loading_state(self):
        """Set the dropdown to loading state."""
        self.vision_model_dropdown.clear()
        self.vision_model_dropdown.addItem("Loading models...")
        self.vision_model_dropdown.setEnabled(False)
        if hasattr(self, 'add_vision_button'):
            self.add_vision_button.setEnabled(False)

    def populate_models(self, models):
        """Populate the vision models dropdown with models."""
        # Clear the dropdown entirely
        self.vision_model_dropdown.clear()

        # Add "None" option at index 0
        self.vision_model_dropdown.addItem("None (No Vision Support)")

        # Add all models to the vision dropdown
        for model in models:
            display_text = f"{model['name']} ({model['provider']})"
            # Add model to dropdown and store the full model info in user data
            self.vision_model_dropdown.addItem(display_text, model)

            # Create and set tooltip for the item
            from .model_fetcher import create_model_tooltip
            tooltip = create_model_tooltip(model)
            index = self.vision_model_dropdown.count() - 1
            self.vision_model_dropdown.setItemData(
                index, tooltip, 3)  # 3 is ToolTipRole

        # Enable the dropdown and button now that models are loaded
        self.vision_model_dropdown.setEnabled(True)
        if hasattr(self, 'add_vision_button'):
            self.add_vision_button.setEnabled(True)

        # Load current selected vision model
        self.load_vision_model()

    def load_vision_model(self):
        """Load the saved vision model from settings."""
        # Get the saved vision model info
        vision_model_info = self.settings.get_vision_model_info()

        # Update the display regardless of dropdown state
        self.update_vision_model_display()

        # Only try to set the dropdown if we have models loaded and vision model info exists
        if self.vision_model_dropdown.count() <= 1 or not vision_model_info:  # Only "None" option or no vision model
            self.vision_model_dropdown.setCurrentIndex(0)  # Set to "None"
            return

        # Try to find the model in the dropdown
        for i in range(1, self.vision_model_dropdown.count()):
            item_data = self.vision_model_dropdown.itemData(
                i, Qt.ItemDataRole.UserRole)
            if (isinstance(item_data, dict) and
                item_data.get('id') == vision_model_info.get('id') and
                    item_data.get('provider') == vision_model_info.get('provider')):
                self.vision_model_dropdown.setCurrentIndex(i)
                return

        # If we get here, the saved model isn't in the current dropdown
        self.vision_model_dropdown.setCurrentIndex(0)
        logging.info(
            f"Saved vision model {vision_model_info.get('id', 'N/A')} not found in current model list, but keeping configuration."
        )

    def add_vision_model(self):
        """Add the selected vision model to settings."""
        current_index = self.vision_model_dropdown.currentIndex()
        if current_index <= 0:  # 0 is "None"
            # Clear vision model
            self.settings.set_vision_model_info(None)
            self.settings.save_settings()
            self.update_vision_model_display()
            self.vision_model_changed.emit()

            QMessageBox.information(
                self,
                "Vision Model Updated",
                "Vision support has been disabled.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Get the full model info dictionary from the dropdown
        model_info = self.vision_model_dropdown.itemData(
            current_index, Qt.ItemDataRole.UserRole)
        if not model_info or not isinstance(model_info, dict):
            logging.error(f"Invalid vision model data: {model_info}")
            return

        # Save the model info
        self.settings.set_vision_model_info(model_info)
        self.settings.save_settings()

        # Update the display
        self.update_vision_model_display()

        # Emit signal
        self.vision_model_changed.emit()

        # Show confirmation
        QMessageBox.information(
            self,
            "Vision Model Updated",
            f"Vision model set to: {model_info['name']}.\nThis model will be used for image processing.",
            QMessageBox.StandardButton.Ok
        )

    def update_vision_model_display(self):
        """Update the vision model display area."""
        # Clear existing widgets from display
        for i in reversed(range(self.vision_model_display.layout().count())):
            widget = self.vision_model_display.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Get current vision model info
        vision_model_info = self.settings.get_vision_model_info()

        if not vision_model_info:
            self.vision_model_display.setVisible(False)
            return

        # Create a widget similar to the model list items but for a single model
        model_widget = QWidget()
        model_widget.setObjectName("visionModelItem")
        model_widget.setStyleSheet("""
            #visionModelItem {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        # Create tooltip for the vision model
        from .model_fetcher import create_model_tooltip
        tooltip = create_model_tooltip(vision_model_info)
        model_widget.setToolTip(tooltip)

        layout = QHBoxLayout(model_widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Content layout for text
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # Create name and provider labels
        name_label = QLabel(vision_model_info['name'])
        name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
        """)

        provider_label = QLabel(f"Provider: {vision_model_info['provider']}")
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

        # Add "Vision Model" indicator label
        vision_label = RoundLabel("Vision Model")
        actions_layout.addWidget(vision_label)

        # Remove button
        remove_btn = RoundButton("×")
        remove_btn.setFixedSize(28, 28)
        remove_btn.clicked.connect(self.remove_vision_model)
        actions_layout.addWidget(remove_btn)

        # Add actions layout to main layout
        layout.addLayout(actions_layout)

        # Add the model widget to the display layout
        self.vision_model_display.layout().addWidget(model_widget)
        self.vision_model_display.setVisible(True)

    def remove_vision_model(self):
        """Remove the current vision model."""
        self.settings.set_vision_model_info(None)
        self.settings.save_settings()
        self.update_vision_model_display()
        # Reset dropdown to "None"
        self.vision_model_dropdown.setCurrentIndex(0)
        # Emit signal
        self.vision_model_changed.emit()

        QMessageBox.information(
            self,
            "Vision Model Removed",
            "Vision support has been disabled.",
            QMessageBox.StandardButton.Ok
        )

    def check_model_in_use(self, model_id):
        """Check if a model is being used as the vision model."""
        vision_model_info = self.settings.get_vision_model_info()
        if vision_model_info and vision_model_info.get('id') == model_id:
            return True
        return False
