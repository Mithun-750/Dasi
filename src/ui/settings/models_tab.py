import logging
import requests  # Keep this import for now, might be needed elsewhere or during cleanup
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QFrame,
    QScrollArea,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal

from .settings_manager import Settings
from .general_tab import SectionFrame
from .models.ui_components import SearchableComboBox, RoundLabel, RoundButton
from .models.selected_models import SelectedModelsComponent
from .models.vision_models import VisionModelsComponent
from .models.filename_models import FilenameModelsComponent
from .models.model_fetcher import ModelFetchWorker, create_model_tooltip


class ModelsTab(QWidget):
    # Signal emitted when models are added or removed
    models_changed = pyqtSignal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.available_models = []
        self.fetch_worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        # Create a widget to hold all content
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Model Selection Section
        selection_section = SectionFrame(
            "Model Selection",
            "Select and manage AI models for use with Dasi. Changes take effect after restarting the service."
        )

        # Model selection container
        selection_widget = QWidget()
        selection_widget.setProperty("class", "transparent-container")
        selection_layout = QHBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(8)

        # Model dropdown (using custom searchable combo box)
        self.model_dropdown = SearchableComboBox()
        self.model_dropdown.setMinimumWidth(300)
        self.model_dropdown.addItem("Loading models...")
        self.model_dropdown.setEnabled(False)

        # Refresh button with modern styling
        refresh_button = QPushButton("⟳")
        refresh_button.setFixedSize(36, 36)
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 6px;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #333333;
                border: 1px solid #e67e22;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        refresh_button.clicked.connect(self.fetch_models)
        refresh_button.setToolTip("Refresh models list")
        self.refresh_button = refresh_button

        # Add button with modern styling
        add_button = QPushButton("Add Model")
        add_button.setProperty("class", "primary")
        add_button.setStyleSheet("""
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
        """)
        add_button.clicked.connect(self.add_model)

        selection_layout.addWidget(self.model_dropdown)
        selection_layout.addWidget(refresh_button)
        selection_layout.addWidget(add_button)
        selection_layout.addStretch()

        # Progress bar container
        progress_container = QWidget()
        progress_container.setProperty("class", "transparent-container")
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(0)

        # Loading progress bar with modern styling
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #333333;
            }
            QProgressBar::chunk {
                background-color: #e67e22;
            }
        """)
        self.progress_bar.hide()

        progress_layout.addWidget(self.progress_bar)

        selection_section.layout.addWidget(selection_widget)
        selection_section.layout.addWidget(progress_container)
        content_layout.addWidget(selection_section)

        # Selected Models Component
        self.selected_models_component = SelectedModelsComponent(self.settings)
        self.selected_models_component.model_changed.connect(
            self.on_model_changed)
        content_layout.addWidget(self.selected_models_component)

        # Vision Models Component
        self.vision_models_component = VisionModelsComponent(self.settings)
        self.vision_models_component.vision_model_changed.connect(
            self.on_model_changed)
        content_layout.addWidget(self.vision_models_component)

        # Filename Models Component
        self.filename_models_component = FilenameModelsComponent(self.settings)
        self.filename_models_component.filename_model_changed.connect(
            self.on_model_changed)
        content_layout.addWidget(self.filename_models_component)

        # Set scroll area widget
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def showEvent(self, event):
        """Called when the tab becomes visible."""
        super().showEvent(event)
        # Start fetching models if we haven't already
        if not self.available_models and not self.fetch_worker:
            self.fetch_models()

    def cleanup(self):
        """Clean up any running threads."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.quit()
            self.fetch_worker.wait(2000)  # Wait up to 2 seconds
            if self.fetch_worker.isRunning():
                logging.warning("Terminating model fetch worker forcefully.")
                self.fetch_worker.terminate()
                self.fetch_worker.wait()
        self.fetch_worker = None  # Ensure worker reference is cleared

    def hideEvent(self, event):
        """Called when the tab is hidden."""
        self.cleanup()
        super().hideEvent(event)

    def closeEvent(self, event):
        """Called when the window is closed."""
        self.cleanup()
        super().closeEvent(event)

    def fetch_models(self):
        """Fetch available models."""
        # Clean up any existing worker first
        self.cleanup()

        # No need to check API keys or Ollama here anymore.
        # The worker thread will handle these checks.

        # Show loading state immediately
        self.model_dropdown.clear()
        self.model_dropdown.addItem("Loading models...")
        self.model_dropdown.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.show()
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("⌛")

        # Start worker thread
        self.fetch_worker = ModelFetchWorker(self.settings)
        self.fetch_worker.finished.connect(self._on_fetch_success)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.no_providers.connect(
            self._on_no_providers)  # Connect new signal
        self.fetch_worker.start()

    def _on_fetch_success(self, models):
        """Handle successful model fetch."""
        self.available_models = models  # Store fetched models (excluding custom for now)
        self.model_dropdown.clear()

        # Add custom OpenAI models from settings AFTER fetching others
        # This ensures they are always included if configured, regardless of worker fetch status
        custom_models = []
        # First check the original custom_openai model
        custom_model_id = self.settings.get(
            'models', 'custom_openai', 'model_id')
        custom_base_url = self.settings.get(
            'models', 'custom_openai', 'base_url')
        if custom_model_id and custom_base_url:
            custom_model = {
                'id': custom_model_id,  # Store the exact model ID as provided
                'provider': 'custom_openai',
                'name': f"Custom: {custom_model_id}"
            }
            custom_models.append(custom_model)

        # Then check for additional custom OpenAI models
        index = 1
        while True:
            settings_key = f"custom_openai_{index}"
            custom_model_id = self.settings.get(
                'models', settings_key, 'model_id')
            custom_base_url = self.settings.get(
                'models', settings_key, 'base_url')
            if custom_model_id and custom_base_url:
                custom_model = {
                    'id': custom_model_id,  # Store the exact model ID as provided
                    'provider': settings_key,
                    'name': f"Custom {index+1}: {custom_model_id}"
                }
                custom_models.append(custom_model)
                index += 1
            else:
                if index > 20:  # Safety break
                    logging.warning(
                        "Stopped checking for additional custom models after index 20.")
                    break
                break  # Exit loop if no more models are found

        all_display_models = self.available_models + custom_models

        # Sort all models (fetched + custom) alphabetically by name
        all_display_models.sort(key=lambda x: x.get('name', '').lower())

        if not all_display_models:
            # Call the no_providers handler if list is empty after adding custom
            self._on_no_providers()
            return  # Stop processing here

        # Add models to dropdown with provider info
        for model in all_display_models:
            display_text = f"{model['name']} ({model['provider']})"
            # Store the full model info in the item data
            self.model_dropdown.addItem(display_text, model)

            # Create descriptive tooltip for the model
            tooltip = create_model_tooltip(model)
            # Set tooltip for the item
            self.model_dropdown.setItemData(
                self.model_dropdown.count()-1, tooltip, Qt.ItemDataRole.ToolTipRole)  # Use ToolTipRole

        self.model_dropdown.setEnabled(True)
        self.progress_bar.hide()
        # Ensure worker reference is cleared AFTER processing results
        # self.fetch_worker = None # Let cleanup handle this

        # Reset refresh button
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("⟳")

        # Update vision models dropdown with ALL models (fetched + custom)
        self.vision_models_component.populate_models(all_display_models)

        # Update filename models dropdown with ALL models (fetched + custom)
        self.filename_models_component.populate_models(all_display_models)

    def _on_fetch_error(self, error):
        """Handle model fetch error."""
        self.model_dropdown.clear()
        self.model_dropdown.addItem("Failed to fetch models")
        self.model_dropdown.setEnabled(False)
        self.progress_bar.hide()
        # Ensure worker reference is cleared
        # self.fetch_worker = None # Let cleanup handle this

        # Reset refresh button
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("⟳")

        QMessageBox.warning(self, "Error", f"Failed to fetch models: {error}")

    def _on_no_providers(self):
        """Handle the case where no providers are configured or found."""
        logging.info("No providers configured or found by the fetch worker.")
        self.model_dropdown.clear()
        self.model_dropdown.addItem(
            "Please configure at least one model provider")
        self.model_dropdown.setEnabled(False)
        self.progress_bar.hide()
        # self.fetch_worker = None # Let cleanup handle this
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("⟳")
        # Clear vision models as well if none are available
        self.vision_models_component.populate_models([])
        # Clear filename models as well if none are available
        self.filename_models_component.populate_models([])

    def add_model(self):
        """Add selected model to the list."""
        current_index = self.model_dropdown.currentIndex()
        if current_index >= 0:
            model_info = self.model_dropdown.itemData(
                current_index, Qt.ItemDataRole.UserRole)
            if model_info:
                self.selected_models_component.add_model(model_info)

    def on_model_changed(self):
        """Handle model changes from components."""
        self.models_changed.emit()

    def remove_models_by_provider(self, provider: str):
        """Remove all models from a specific provider when its API key is cleared."""
        # Vision model is handled separately in selected models component
        vision_model_info = self.settings.get_vision_model_info()
        if vision_model_info and vision_model_info.get('provider') == provider:
            self.settings.set_vision_model_info(None)
            self.vision_models_component.update_vision_model_display()

        # Filename model is handled separately
        filename_model_info = self.settings.get_filename_model_info()
        if filename_model_info and filename_model_info.get('provider') == provider:
            self.settings.set_filename_model_info(None)
            self.filename_models_component.update_filename_model_display()

        # Handle selected models
        self.selected_models_component.remove_models_by_provider(provider)
