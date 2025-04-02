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
    QStyleOption,
    QStyle,
    QProxyStyle,
)
from PyQt6.QtCore import Qt, QEvent, QThread, pyqtSignal, QObject, QRectF
from PyQt6.QtGui import QPalette, QPainter, QPainterPath, QColor, QFont, QFontMetrics, QPen
from .settings_manager import Settings
from .general_tab import SectionFrame


class RoundLabel(QLabel):
    """Custom label with rounded corners using QPainter."""

    def __init__(self, text, parent=None, radius=12):
        super().__init__(text, parent)
        self.radius = radius
        # Set colors for the label - using orange theme
        # Light orange background with ~10% opacity
        self.bg_color = QColor(230, 126, 34, 25)
        self.text_color = QColor(230, 126, 34)  # Orange text (#e67e22)
        # Set fixed height for consistent look
        self.setFixedHeight(24)
        # Set content margins to create padding
        self.setContentsMargins(12, 4, 12, 4)
        # Set font size
        font = self.font()
        font.setPointSize(9)  # Same as the original 12px
        self.setFont(font)
        # Calculate width based on text + padding
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        self.setMinimumWidth(text_width + 24)  # 12px padding on each side

    def sizeHint(self):
        size = super().sizeHint()
        size.setHeight(24)
        return size

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # Create the path for the rounded rectangle
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, self.width(), self.height()),
                                self.radius, self.radius)

            # Set the clipping path
            painter.setClipPath(path)

            # Fill background
            painter.fillRect(self.rect(), self.bg_color)

            # Draw text - use the font we set in the constructor
            painter.setPen(self.text_color)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        finally:
            painter.end()


class RoundButton(QPushButton):
    """Custom button with rounded corners using QPainter."""

    def __init__(self, text, parent=None, radius=14):
        super().__init__(text, parent)
        self.radius = radius
        self.hover = False
        # Store colors as QColor objects
        self.border_color = QColor(230, 126, 34, 76)  # ~30% opacity
        self.hover_border_color = QColor(230, 126, 34, 102)  # ~40% opacity
        self.hover_bg_color = QColor(230, 126, 34, 25)  # ~10% opacity
        self.text_color = QColor(230, 126, 34)  # #e67e22

    def enterEvent(self, event):
        self.hover = True
        self.update()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover = False
        self.update()
        return super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # Create the path for the perfect circle
            path = QPainterPath()
            path.addEllipse(QRectF(1, 1, self.width()-2, self.height()-2))

            # Set the clipping path
            painter.setClipPath(path)

            # Draw the background
            if self.hover:
                # Hover state
                painter.fillRect(self.rect(), self.hover_bg_color)
            else:
                # Normal state
                painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

            # Draw the border
            painter.setPen(
                self.hover_border_color if self.hover else self.border_color)
            painter.drawEllipse(1, 1, self.width()-2, self.height()-2)

            # Draw the text centered
            painter.setPen(self.text_color)
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        finally:
            # Make sure painter is ended properly
            painter.end()


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

    def fetch_openai_models(self):
        """Fetch models from OpenAI API."""
        api_key = self.settings.get_api_key('openai')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.openai.com/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Filter for chat models
            text_models = []
            for model in models:
                if 'gpt' in model['id'].lower():  # Filter for GPT models
                    model_info = {
                        'id': model['id'],
                        'provider': 'openai',
                        'name': model['id']
                    }
                    text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching OpenAI models: {str(e)}")
            return []

    def fetch_anthropic_models(self):
        """Fetch models from Anthropic API."""
        api_key = self.settings.get_api_key('anthropic')
        if not api_key:
            logging.error("Anthropic API key not found.")
            return []

        try:
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.anthropic.com/v1/models', headers=headers)

            if response.status_code == 200:
                models = response.json().get('data', [])
                text_models = [
                    {
                        'id': model['id'],
                        'provider': 'anthropic',
                        'name': model.get('display_name', model['id'])
                    }
                    for model in models
                ]
                return text_models
            else:
                logging.error(
                    f"Failed to fetch models. Status code: {response.status_code}, Response: {response.text}")
                return []
        except Exception as e:
            logging.error(f"Error fetching Anthropic models: {str(e)}")
            return []

    def fetch_deepseek_models(self):
        """Fetch models from Deepseek API."""
        api_key = self.settings.get_api_key('deepseek')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.deepseek.com/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json().get('data', [])

            # Format models
            text_models = []
            for model in models:
                model_info = {
                    'id': model['id'],
                    'provider': 'deepseek',
                    'name': model.get('name', model['id'])
                }
                text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Deepseek models: {str(e)}")
            return []

    def fetch_together_models(self):
        """Fetch models from Together AI API."""
        api_key = self.settings.get_api_key('together')
        if not api_key:
            return []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                'https://api.together.xyz/v1/models',
                headers=headers
            )
            response.raise_for_status()
            models = response.json()

            # Format models
            text_models = []
            for model in models:
                model_info = {
                    'id': model['id'],
                    'provider': 'together',
                    'name': model.get('name', model['id'])
                }
                text_models.append(model_info)
            return text_models
        except Exception as e:
            logging.error(f"Error fetching Together AI models: {str(e)}")
            return []

    def fetch_xai_models(self):
        """Fetch models from xAI (Grok) API."""
        api_key = self.settings.get_api_key('xai')
        if not api_key:
            return []

        try:
            # xAI currently offers limited models, so we'll hardcode them
            # This can be updated when xAI expands their model offerings
            models = [
                {
                    'id': 'grok-beta',
                    'provider': 'xai',
                    'name': 'Grok Beta'
                },
                {
                    'id': 'grok-1',
                    'provider': 'xai',
                    'name': 'Grok-1'
                }
            ]

            return models
        except Exception as e:
            logging.error(f"Error setting up xAI models: {str(e)}")
            return []

    def run(self):
        try:
            # Fetch models from all providers
            google_models = self.fetch_google_models()
            openrouter_models = self.fetch_openrouter_models()
            ollama_models = self.fetch_ollama_models()
            groq_models = self.fetch_groq_models()
            openai_models = self.fetch_openai_models()
            anthropic_models = self.fetch_anthropic_models()
            deepseek_models = self.fetch_deepseek_models()
            together_models = self.fetch_together_models()
            xai_models = self.fetch_xai_models()

            # Combine all models
            all_models = (google_models + openrouter_models +
                          ollama_models + groq_models + openai_models +
                          anthropic_models + deepseek_models + together_models +
                          xai_models)

            if not all_models:
                self.error.emit(
                    "No models found. Please check your API keys and model configurations.")
                return

            self.finished.emit(all_models)
        except Exception as e:
            self.error.emit(str(e))


class ComboBoxStyle(QProxyStyle):
    """Custom style to draw a text arrow for combo boxes."""

    def __init__(self, style=None):
        super().__init__(style)
        self.arrow_color = QColor("#e67e22")  # Orange color for arrow

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown and isinstance(widget, QComboBox):
            # Draw a custom arrow
            rect = option.rect
            painter.save()

            # Set up the arrow color
            painter.setPen(QPen(self.arrow_color, 1.5))

            # Draw a triangle instead of text arrow for more modern look
            # Calculate the triangle points
            width = 9
            height = 6
            x = rect.center().x() - width // 2
            y = rect.center().y() - height // 2

            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x + width, y)
            path.lineTo(x + width // 2, y + height)
            path.lineTo(x, y)

            # Fill the triangle
            painter.fillPath(path, self.arrow_color)

            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


class SearchableComboBox(QComboBox):
    """Custom ComboBox with search functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Apply custom arrow style
        self.setStyle(ComboBoxStyle())

        # Apply orange-themed style
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                background-color: #222222;
                padding: 4px 8px;
                min-height: 18px;
            }
            QComboBox:hover, QComboBox:focus {
                border: 1px solid #e67e22;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
        """)

        # Create search line edit
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search models...")
        self.search_edit.setProperty("class", "search-input")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #2a2a2a;
                color: #e0e0e0;
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
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")
        self.scroll.setProperty("class", "global-scrollbar")

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
                background-color: #333333;
                border-left: 2px solid #e67e22;
            }
        """)
        self.list_widget.setProperty("class", "global-scrollbar")
        self.scroll.setWidget(self.list_widget)

        # Force scrollbar styling directly
        scrollbar = self.list_widget.verticalScrollBar()
        if scrollbar:
            scrollbar.setStyleSheet("""
                QScrollBar:vertical {
                    background-color: #1a1a1a !important;
                    width: 10px !important;
                    margin: 0px 0px 0px 8px !important;
                    border-radius: 5px !important;
                    border: none !important;
                }
                
                QScrollBar::handle:vertical {
                    background-color: #333333 !important;
                    min-height: 30px !important;
                    border-radius: 5px !important;
                    border: none !important;
                }
                
                QScrollBar::handle:vertical:hover {
                    background-color: #e67e22 !important;
                }
                
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px !important;
                    border: none !important;
                    background: none !important;
                }
                
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none !important;
                    border: none !important;
                }
            """)

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
        # Adjusted right padding from 0 to 16
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
        content_layout.setContentsMargins(
            0, 0, 0, 0)  # Removed 8px right padding

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

        # Selected Models Section
        models_section = SectionFrame(
            "Selected Models",
            "Models that will be available for use in Dasi. Set a default model that will be used when no specific model is requested."
        )

        # Selected models list with modern styling
        self.models_list = QListWidget()
        self.models_list.setFrameShape(QFrame.Shape.NoFrame)
        self.models_list.setSpacing(8)  # Increased spacing between items
        self.models_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 4px 0;
            }
            QListWidget::item:selected {
                background-color: transparent;
                border: none;
            }
            QListWidget::item:hover {
                background-color: transparent;
                border: none;
            }
        """)

        models_section.layout.addWidget(self.models_list)
        content_layout.addWidget(models_section)

        # Vision Models Section
        vision_models_section = SectionFrame(
            "Vision Models",
            "Select one model to handle image processing in multimodal conversations. Only select models that support image analysis."
        )

        # Vision model selection container
        vision_model_container = QWidget()
        vision_model_container.setProperty("class", "transparent-container")
        vision_model_layout = QVBoxLayout(vision_model_container)
        vision_model_layout.setContentsMargins(0, 0, 0, 0)
        vision_model_layout.setSpacing(8)

        # Create label
        vision_model_label = QLabel("Selected Vision Model:")
        vision_model_label.setStyleSheet("""
            color: #e0e0e0;
            font-size: 14px;
            font-weight: 500;
        """)

        # Create vision model dropdown
        self.vision_model_dropdown = SearchableComboBox()
        self.vision_model_dropdown.setMinimumWidth(300)

        # Add "None" option
        self.vision_model_dropdown.addItem("None (No Vision Support)")

        # Add model selector and label to container
        vision_model_layout.addWidget(vision_model_label)
        vision_model_layout.addWidget(self.vision_model_dropdown)

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

        vision_models_section.layout.addWidget(vision_model_container)
        content_layout.addWidget(vision_models_section)

        # Set scroll area widget
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Load selected models
        self.load_selected_models()

        # Connect vision model dropdown signal
        self.vision_model_dropdown.currentIndexChanged.connect(
            self.on_vision_model_changed)

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
                self.fetch_worker.terminate()
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
        """Fetch available models."""
        # Clean up any existing worker first
        self.cleanup()

        # Check if we have any API keys or custom models configured
        google_key = self.settings.get_api_key('google')

        # Check for any custom OpenAI models
        has_custom_openai = False

        # Check the original custom_openai model
        custom_model_id = self.settings.get(
            'models', 'custom_openai', 'model_id')
        custom_base_url = self.settings.get(
            'models', 'custom_openai', 'base_url')
        custom_api_key = self.settings.get_api_key('custom_openai')
        if custom_model_id and custom_base_url and custom_api_key:
            has_custom_openai = True

        # Check for additional custom OpenAI models
        if not has_custom_openai:
            index = 1
            while True:
                settings_key = f"custom_openai_{index}"
                model_id = self.settings.get(
                    'models', settings_key, 'model_id')
                base_url = self.settings.get(
                    'models', settings_key, 'base_url')
                api_key = self.settings.get_api_key(settings_key)

                if model_id and base_url and api_key:
                    has_custom_openai = True
                    break

                if index > 10:  # Limit the search to avoid infinite loop
                    break

                index += 1

        # Always check for local Ollama models regardless of API keys
        try:
            # Quick check if Ollama is running
            ollama_available = False
            try:
                response = requests.get(
                    'http://localhost:11434/api/tags', timeout=0.5)
                if response.status_code == 200:
                    ollama_available = True
            except:
                pass

            if ollama_available:
                # Show loading state and start worker thread
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

                # Update UI to show fetching state
                if hasattr(self, 'refresh_button'):
                    self.refresh_button.setEnabled(False)
                    self.refresh_button.setText("⌛")
                return
        except Exception as e:
            logging.error(f"Error checking for Ollama: {str(e)}")

        # If no Ollama and no API keys, show message
        if not google_key and not has_custom_openai:
            self.model_dropdown.clear()
            self.model_dropdown.addItem(
                "Please configure at least one model provider")
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

        # Update UI to show fetching state
        if hasattr(self, 'refresh_button'):
            self.refresh_button.setEnabled(False)
            self.refresh_button.setText("⌛")

    def _on_fetch_success(self, models):
        """Handle successful model fetch."""
        self.available_models = models
        self.model_dropdown.clear()
        self.vision_model_dropdown.clear()

        # Add "None" option to vision model dropdown
        self.vision_model_dropdown.addItem("None (No Vision Support)")

        # Check for custom OpenAI models
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
            models.append(custom_model)

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
                models.append(custom_model)
                index += 1
            else:
                break

        # Add models to dropdown with provider info
        for model in models:
            display_text = f"{model['name']} ({model['provider']})"
            # Store the full model info in the item data
            self.model_dropdown.addItem(display_text, model)

            # Check if model supports vision capabilities
            if self._is_vision_capable(model):
                vision_display_text = f"{model['name']} ({model['provider']})"
                self.vision_model_dropdown.addItem(vision_display_text, model)

        self.model_dropdown.setEnabled(True)
        self.vision_model_dropdown.setEnabled(True)
        self.progress_bar.hide()
        self.fetch_worker = None

        # Reset refresh button
        if hasattr(self, 'refresh_button'):
            self.refresh_button.setEnabled(True)
            self.refresh_button.setText("⟳")

        # Load saved vision model selection
        self.load_vision_model()

    def _is_vision_capable(self, model):
        """Check if a model is likely to support vision capabilities."""
        provider = model['provider']
        model_id = model['id'].lower()
        model_name = model['name'].lower()

        # Models known to support vision
        if provider == 'openai' and ('gpt-4-vision' in model_id or 'gpt-4o' in model_id or 'gpt-4-turbo' in model_id):
            return True
        elif provider == 'google' and ('gemini' in model_id):
            return True
        elif provider == 'anthropic' and ('claude-3' in model_id):
            return True
        elif provider == 'custom_openai' and ('gpt-4-vision' in model_id or 'gpt-4o' in model_id):
            return True

        # Check for known model names
        vision_keywords = ['vision', 'multimodal', 'image',
                           'visual', 'gpt-4o', 'gemini', 'claude-3']
        for keyword in vision_keywords:
            if keyword in model_id or keyword in model_name:
                return True

        return False

    def load_vision_model(self):
        """Load the saved vision model from settings."""
        vision_model_id = self.settings.get('models', 'vision_model')

        if not vision_model_id:
            # No vision model set, default to None
            self.vision_model_dropdown.setCurrentIndex(0)
            return

        # Find the model in the dropdown
        for i in range(1, self.vision_model_dropdown.count()):
            model_info = self.vision_model_dropdown.itemData(i)
            if model_info and model_info['id'] == vision_model_id:
                self.vision_model_dropdown.setCurrentIndex(i)
                return

        # If we got here, the saved model wasn't found in the list
        # This could happen if the model was removed or is no longer available
        # Reset to None
        self.vision_model_dropdown.setCurrentIndex(0)
        self.settings.set('models', 'vision_model', '')

    def _on_fetch_error(self, error):
        """Handle model fetch error."""
        self.model_dropdown.clear()
        self.model_dropdown.addItem("Failed to fetch models")
        self.model_dropdown.setEnabled(False)
        self.progress_bar.hide()
        self.fetch_worker = None

        # Reset refresh button
        if hasattr(self, 'refresh_button'):
            self.refresh_button.setEnabled(True)
            self.refresh_button.setText("⟳")

        QMessageBox.warning(self, "Error", f"Failed to fetch models: {error}")

    def load_selected_models(self):
        """Load selected models into the list."""
        self.models_list.clear()
        for model in self.settings.get_selected_models():
            self.add_model_to_list(model)

    def add_model_to_list(self, model_info: dict):
        """Add a model to the list widget with a remove button."""
        item = QListWidgetItem()
        item.setBackground(Qt.GlobalColor.transparent)
        self.models_list.addItem(item)

        # Main container widget with single border
        widget = QWidget()
        # Give it a specific name for styling
        widget.setObjectName("modelItem")
        widget.setStyleSheet("""
            #modelItem {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        # Use a single horizontal layout
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Create content layout for text directly without any container
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # Create name and provider labels
        name_label = QLabel(model_info['name'])
        name_label.setAutoFillBackground(False)
        name_label.setFrameShape(QFrame.Shape.NoFrame)
        name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
        """)

        provider_label = QLabel(f"Provider: {model_info['provider']}")
        provider_label.setAutoFillBackground(False)
        provider_label.setFrameShape(QFrame.Shape.NoFrame)
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

        # Add the layout directly to main layout
        layout.addLayout(content_layout, 1)  # Give it a stretch factor of 1

        # Create actions layout directly (no container widget)
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)
        actions_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Default model indicator
        is_default = self.settings.get(
            'models', 'default_model') == model_info['id']
        default_label = RoundLabel("Default")
        default_label.setVisible(is_default)

        # Set Default button with modern styling
        default_btn = QPushButton("Set Default")
        default_btn.setStyleSheet("""
            padding: 4px 12px;
            font-size: 12px;
            border-radius: 12px;
            background-color: transparent;
            border: 1px solid rgba(230, 126, 34, 0.3);
            color: #e67e22;
        """)
        default_btn.setVisible(False)
        default_btn.clicked.connect(
            lambda: self.set_default_model(model_info['id']))

        # Add hover effects with event filter
        default_btn.enterEvent = lambda e: default_btn.setStyleSheet("""
            padding: 4px 12px;
            font-size: 12px;
            border-radius: 12px;
            background-color: rgba(230, 126, 34, 0.1);
            border: 1px solid rgba(230, 126, 34, 0.4);
            color: #e67e22;
        """)
        default_btn.leaveEvent = lambda e: default_btn.setStyleSheet("""
            padding: 4px 12px;
            font-size: 12px;
            border-radius: 12px;
            background-color: transparent;
            border: 1px solid rgba(230, 126, 34, 0.3);
            color: #e67e22;
        """)

        # Remove button with modern styling - now using RoundButton with custom painting
        remove_btn = RoundButton("×")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setVisible(False)
        remove_btn.clicked.connect(lambda: self.remove_model(model_info['id']))

        # Add content to actions layout
        actions_layout.addWidget(default_label)
        actions_layout.addWidget(default_btn)
        actions_layout.addWidget(remove_btn)

        # Add actions layout to main layout
        layout.addLayout(actions_layout)

        # Create event filter for hover effects
        class HoverEventFilter(QObject):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.default_btn = default_btn
                self.remove_btn = remove_btn
                self.is_default = is_default
                # Keep reference to original style to avoid affecting inner elements
                self.original_style = """
                    #modelItem {
                        background-color: #222222;
                        border: 1px solid #333333;
                        border-radius: 8px;
                    }
                """
                self.hover_style = """
                    #modelItem {
                        background-color: #2a2a2a;
                        border: 1px solid #444444;
                        border-radius: 8px;
                    }
                """

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Enter:
                    # Show buttons
                    if not self.is_default:
                        self.default_btn.setVisible(True)
                    self.remove_btn.setVisible(True)

                    # Apply hover style only to the main widget
                    obj.setStyleSheet(self.hover_style)

                elif event.type() == QEvent.Type.Leave:
                    # Hide buttons
                    self.default_btn.setVisible(False)
                    self.remove_btn.setVisible(False)

                    # Restore original style
                    obj.setStyleSheet(self.original_style)

                return False

        # Install event filter
        hover_filter = HoverEventFilter(widget)
        widget.installEventFilter(hover_filter)
        widget.hover_filter = hover_filter

        # Set appropriate size for the item
        size_hint = widget.sizeHint()
        size_hint.setHeight(max(64, size_hint.height()))
        item.setSizeHint(size_hint)

        self.models_list.setItemWidget(item, widget)

    def set_default_model(self, model_id: str):
        """Set a model as the default model."""
        # Save the default model in settings
        self.settings.set('models', 'default_model', model_id)

        # Refresh the list to update the UI
        self.load_selected_models()

        # Show confirmation message
        QMessageBox.information(
            self,
            "Success",
            f"Default model has been set successfully.",
            QMessageBox.StandardButton.Ok
        )

    def add_model(self):
        """Add selected model to the list."""
        current_index = self.model_dropdown.currentIndex()
        if (current_index >= 0):
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
                    # No need to emit signal here - Settings class already emits it

    def remove_model(self, model_id: str):
        """Remove a model from the list."""
        if self.settings.remove_selected_model(model_id):
            # Reload settings from disk
            self.settings.load_settings()
            # Refresh the list
            self.load_selected_models()
            # No need to emit signal here - Settings class already emits it

    def remove_models_by_provider(self, provider: str):
        """Remove all models from a specific provider when its API key is cleared."""
        if not provider:
            return

        # Get current selected models
        current_models = self.settings.get_selected_models()

        # Find models from the specified provider
        # For custom_openai providers, we need to match the exact provider key
        if provider == 'custom_openai' or provider.startswith('custom_openai_'):
            models_to_remove = [
                model['id'] for model in current_models if model['provider'] == provider]
        else:
            # For standard providers, remove all models from that provider
            models_to_remove = [
                model['id'] for model in current_models if model['provider'] == provider]

        if not models_to_remove:
            # No models to remove
            return

        # Remove each model
        removed_any = False
        for model_id in models_to_remove:
            if self.settings.remove_selected_model(model_id):
                removed_any = True

        if removed_any:
            # Reload settings from disk
            self.settings.load_settings()
            # Refresh the list
            self.load_selected_models()
            # No need to emit signal here - Settings class already emits it for each model removed

            # Log the removal
            logging.info(
                f"Removed {len(models_to_remove)} models from provider '{provider}' due to API key reset")

            # Check if the default model was removed
            default_model = self.settings.get('models', 'default_model')
            if default_model in models_to_remove:
                # Reset the default model
                self.settings.set("", 'models', 'default_model')
                logging.info(
                    f"Reset default model as it was from provider '{provider}'")

            # Show notification to the user
            # Format the provider name for display
            display_provider = provider
            if provider.startswith('custom_openai_'):
                index = provider.split('_')[-1]
                display_provider = f"Custom OpenAI Model #{int(index)+1}"
            elif provider == 'custom_openai':
                display_provider = "Custom OpenAI Model"
            else:
                display_provider = provider.title()

            QMessageBox.information(
                self,
                "Models Removed",
                f"Removed {len(models_to_remove)} models from {display_provider} because the API key was cleared.",
                QMessageBox.StandardButton.Ok
            )

    def on_vision_model_changed(self, index):
        """Handle vision model selection change."""
        if index == 0:
            # "None" selected
            self.settings.set('models', 'vision_model', '')
            logging.info("Vision model set to None")
            return

        # Get the selected model info
        model_info = self.vision_model_dropdown.itemData(index)
        if model_info:
            # Save the model ID to settings
            self.settings.set('models', 'vision_model', model_info['id'])
            logging.info(
                f"Vision model set to: {model_info['name']} ({model_info['id']})")
