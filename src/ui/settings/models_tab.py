import requests
import logging
import json
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QLineEdit,
    QFrame,
    QScrollArea,
    QStyledItemDelegate,
    QProgressBar,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QEvent, QThread, pyqtSignal
from PyQt6.QtGui import QPalette
from .settings_manager import Settings


class ModelFetchWorker(QThread):
    """Worker thread for fetching models."""
    finished = pyqtSignal(list)  # Emits list of model names
    error = pyqtSignal(str)      # Emits error message

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def fetch_google_models(self):
        """Fetch models from Google AI API."""
        api_key = self.settings.get_api_key('google')
        if not api_key:
            return []

        try:
            response = requests.get(
                'https://generativelanguage.googleapis.com/v1beta/models',
                params={'key': api_key}
            )
            response.raise_for_status()
            models = response.json().get('models', [])

            # Filter for models that support text generation
            text_models = []
            for model in models:
                if any(method in model.get('supportedGenerationMethods', [])
                       for method in ['generateText', 'generateContent']):
                    model_info = {
                        'id': model['name'],
                        'provider': 'google',
                        'name': model.get('displayName', model['name'])
                    }
                    text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Google models: {str(e)}")
            return []

    def fetch_openrouter_models(self):
        """Fetch models from OpenRouter API."""
        api_key = self.settings.get_api_key('openrouter')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/mithuns/dasi',
                'X-Title': 'Dasi'
            }

            response = requests.get(
                'https://openrouter.ai/api/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Filter for text-to-text models
            text_models = []
            for model in models:
                if model.get('architecture', {}).get('modality') == 'text->text':
                    model_info = {
                        'id': model['id'],
                        'provider': 'openrouter',
                        'name': model.get('name', model['id'])
                    }
                    text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching OpenRouter models: {str(e)}")
            return []

    def fetch_ollama_models(self):
        """Fetch models from local Ollama instance."""
        try:
            response = requests.get('http://localhost:11434/api/tags')
            response.raise_for_status()
            models = response.json().get('models', [])

            text_models = []
            for model in models:
                model_info = {
                    'id': model['name'],
                    'provider': 'ollama',
                    'name': model['name']
                }
                text_models.append(model_info)
            return text_models
        except requests.exceptions.ConnectionError:
            logging.warning("Ollama server not running or not accessible")
            return []
        except Exception as e:
            logging.error(f"Error fetching Ollama models: {str(e)}")
            return []

    def fetch_groq_models(self):
        """Fetch models from Groq API."""
        api_key = self.settings.get_api_key('groq')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.groq.com/openai/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Format models
            text_models = []
            for model in models:
                model_info = {
                    'id': model['id'],
                    'provider': 'groq',
                    # Use ID as name since that's what Groq provides
                    'name': model.get('id')
                }
                text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Groq models: {str(e)}")
            return []

    def run(self):
        try:
            # Fetch models from all providers
            google_models = self.fetch_google_models()
            openrouter_models = self.fetch_openrouter_models()
            ollama_models = self.fetch_ollama_models()
            groq_models = self.fetch_groq_models()

            # Combine all models
            all_models = google_models + openrouter_models + ollama_models + groq_models

            if not all_models:
                self.error.emit(
                    "No models found. Please check your API keys and Ollama installation.")
                return

            self.finished.emit(all_models)
        except Exception as e:
            self.error.emit(str(e))


class SearchableComboBox(QComboBox):
    """Custom ComboBox with search functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create search line edit
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search models...")
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


class ModelsTab(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.available_models = []
        self.fetch_worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Models")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Model selection section
        selection_widget = QWidget()
        selection_layout = QHBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 0, 0, 0)

        # Model dropdown (using custom searchable combo box)
        self.model_dropdown = SearchableComboBox()
        self.model_dropdown.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
                min-width: 200px;
                background-color: #363636;
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
        self.model_dropdown.addItem("Loading models...")
        self.model_dropdown.setEnabled(False)

        # Loading progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #404040;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
            }
        """)
        self.progress_bar.hide()

        # Add button
        add_button = QPushButton("Add Model")
        add_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
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
            QPushButton:disabled {
                background-color: #404040;
                color: #666666;
            }
        """)
        add_button.clicked.connect(self.add_model)

        selection_layout.addWidget(self.model_dropdown)
        selection_layout.addWidget(add_button)
        selection_layout.addStretch()

        # Add selection widget and progress bar to a container
        dropdown_container = QWidget()
        dropdown_layout = QVBoxLayout(dropdown_container)
        dropdown_layout.setContentsMargins(0, 0, 0, 0)
        dropdown_layout.setSpacing(0)
        dropdown_layout.addWidget(selection_widget)
        dropdown_layout.addWidget(self.progress_bar)

        layout.addWidget(dropdown_container)

        # Selected models list
        list_label = QLabel("Selected Models")
        list_label.setStyleSheet("font-size: 14px; margin-top: 10px;")
        layout.addWidget(list_label)

        self.models_list = QListWidget()
        self.models_list.setStyleSheet("""
            QListWidget {
                border-radius: 4px;
                font-size: 13px;
                padding: 0px;
                background-color: #363636;
            }
            QListWidget::item {
                padding: 0px;
                border-radius: 3px;
                min-height: 40px;
            }
            QListWidget::item:hover {
                background-color: #404040;
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
        # Set size policy to expand
        self.models_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.models_list)

        # Load selected models
        self.load_selected_models()

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
            self.fetch_worker.wait()

    def hideEvent(self, event):
        """Called when the tab is hidden."""
        self.cleanup()
        super().hideEvent(event)

    def closeEvent(self, event):
        """Called when the window is closed."""
        self.cleanup()
        super().closeEvent(event)

    def fetch_models(self):
        """Fetch available models from Google API."""
        # Clean up any existing worker first
        self.cleanup()

        api_key = self.settings.get_api_key('google')
        if not api_key:
            self.model_dropdown.clear()
            self.model_dropdown.addItem("Please add Google API key first")
            self.model_dropdown.setEnabled(False)
            return

        # Show loading state
        self.model_dropdown.clear()
        self.model_dropdown.addItem("Loading models...")
        self.model_dropdown.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.show()

        # Start worker thread
        self.fetch_worker = ModelFetchWorker(self.settings)
        self.fetch_worker.finished.connect(self._on_fetch_success)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.start()

    def _on_fetch_success(self, models):
        """Handle successful model fetch."""
        self.available_models = models
        self.model_dropdown.clear()

        # Add models to dropdown with provider info
        for model in models:
            display_text = f"{model['name']} ({model['provider']})"
            # Store the full model info in the item data
            self.model_dropdown.addItem(display_text, model)

        self.model_dropdown.setEnabled(True)
        self.progress_bar.hide()
        self.fetch_worker = None

    def _on_fetch_error(self, error):
        """Handle model fetch error."""
        self.model_dropdown.clear()
        self.model_dropdown.addItem("Failed to fetch models")
        self.model_dropdown.setEnabled(False)
        self.progress_bar.hide()
        self.fetch_worker = None
        QMessageBox.warning(self, "Error", f"Failed to fetch models: {error}")

    def load_selected_models(self):
        """Load selected models into the list."""
        self.models_list.clear()
        for model in self.settings.get_selected_models():
            self.add_model_to_list(model)

    def add_model_to_list(self, model_info: dict):
        """Add a model to the list widget with a remove button."""
        item = QListWidgetItem()
        self.models_list.addItem(item)

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Create label with model name and provider
        label = QLabel(f"{model_info['name']} ({model_info['provider']})")
        label.setStyleSheet("""
            QLabel {
                font-size: 13px;
            }
        """)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                border-radius: 12px;
                font-weight: bold;
                font-size: 16px;
                margin: 0;
                padding: 0;
                line-height: 24px;
                min-width: 24px;
                max-width: 24px;
                border: none;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #cc3333;
                padding-top: 1px;
                padding-left: 1px;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_model(model_info['id']))

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(remove_btn)

        widget.setLayout(layout)

        item_height = max(40, remove_btn.height(
        ) + layout.contentsMargins().top() + layout.contentsMargins().bottom())
        item.setSizeHint(widget.sizeHint())

        self.models_list.setItemWidget(item, widget)

    def add_model(self):
        """Add selected model to the list."""
        current_index = self.model_dropdown.currentIndex()
        if current_index >= 0:
            model_info = self.model_dropdown.itemData(current_index)
            if model_info and model_info['id'] not in self.settings.get_selected_model_ids():
                # Add model to settings
                if self.settings.add_selected_model(
                    model_info['id'],
                    model_info['provider'],
                    model_info['name']
                ):
                    # Reload settings from disk to ensure we have latest data
                    self.settings.load_settings()
                    # Update UI
                    self.add_model_to_list(model_info)

    def remove_model(self, model_id: str):
        """Remove a model from the list."""
        if self.settings.remove_selected_model(model_id):
            # Reload settings from disk
            self.settings.load_settings()
            # Refresh the list
            self.load_selected_models()
