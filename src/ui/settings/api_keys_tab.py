from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QStyledItemDelegate,
    QSizePolicy,
    QListWidget,
    QListWidgetItem,
    QProxyStyle,
    QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QDir, QEvent, QPoint, QRect, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QIcon, QColor, QPen, QPainterPath, QPainter
from .settings_manager import Settings
import logging
import os
import sys

# Import our modular components
from .api_keys.common import APICategory
from .api_keys.llm_providers import LLMProvidersSection
from .api_keys.search_providers import SearchProvidersSection
from .api_keys.custom_openai import CustomOpenAISection


# ComboBoxStyle for proper arrow display
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


# Custom ComboBox with animated popup
class CustomComboBox(QComboBox):
    """ComboBox with custom popup and animation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Apply custom arrow
        self.setStyle(ComboBoxStyle())
        
        # Create popup frame
        self.popup_frame = QFrame(self.window())
        self.popup_frame.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.popup_frame.setProperty("class", "popup-frame")
        
        # Create shadow effect
        self.popup_frame.setStyleSheet("""
            QFrame.popup-frame {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        
        # Create scroll area for better handling of many items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: transparent;")
        
        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setProperty("class", "popup-list")
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                color: #e0e0e0;
                margin: 2px;
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
        
        # Set up the popup layout
        self.scroll_area.setWidget(self.list_widget)
        self.popup_layout = QVBoxLayout(self.popup_frame)
        self.popup_layout.setContentsMargins(0, 0, 0, 0)
        self.popup_layout.addWidget(self.scroll_area)
        
        # Connect list widget signals
        self.list_widget.itemClicked.connect(self._handle_item_selected)
        
        # Add animation
        self.animation = QPropertyAnimation(self.popup_frame, b"geometry")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.animation.setDuration(180)  # Animation duration in milliseconds
        
        # Remember if popup is visible
        self.popup_visible = False
        
        # Set fixed item height to make calculations easier
        self.item_height = 32
        
        # Set max height in items
        self.max_visible_items = 10
        
    def showPopup(self):
        """Show custom popup instead of standard dropdown."""
        if self.count() == 0 or not self.isEnabled():
            return
            
        # Calculate popup position and size
        popup_width = max(self.width(), 260)  # Minimum width for better readability
        
        # Calculate height based on number of items (limited by max_visible_items)
        items_height = min(self.count(), self.max_visible_items) * self.item_height
        popup_height = items_height + 8  # Add padding
        
        # Get global position for the popup
        pos = self.mapToGlobal(QPoint(0, self.height()))
        
        # Clear and populate list widget
        self.list_widget.clear()
        for i in range(self.count()):
            item = QListWidgetItem(self.itemText(i))
            # Store item data for later retrieval
            if self.itemData(i) is not None:
                item.setData(Qt.ItemDataRole.UserRole, self.itemData(i))
            self.list_widget.addItem(item)
        
        # Set the current item
        if self.currentIndex() >= 0:
            self.list_widget.setCurrentRow(self.currentIndex())
        
        # Set initial and final geometry for animation
        start_rect = QRect(pos.x(), pos.y(), popup_width, 0)
        end_rect = QRect(pos.x(), pos.y(), popup_width, popup_height)
        
        # Set up animation
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        
        # Show popup
        self.popup_frame.setGeometry(start_rect)
        self.popup_frame.show()
        self.animation.start()
        
        # Set popup visible flag
        self.popup_visible = True
        
        # Install event filter to handle mouse events outside the popup
        self.window().installEventFilter(self)
    
    def hidePopup(self):
        """Hide the custom popup."""
        if not self.popup_visible:
            return
            
        # Set up closing animation
        current_rect = self.popup_frame.geometry()
        start_rect = current_rect
        end_rect = QRect(current_rect.x(), current_rect.y(), current_rect.width(), 0)
        
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        
        # Connect animation finished signal to hide the popup
        self.animation.finished.connect(self._finish_hiding)
        
        # Start the closing animation
        self.animation.start()
        
        # Remove event filter
        self.window().removeEventFilter(self)
        
        # Set popup visible flag
        self.popup_visible = False
    
    def _finish_hiding(self):
        """Hide the popup frame and disconnect signal after animation."""
        self.popup_frame.hide()
        try:
            self.animation.finished.disconnect(self._finish_hiding)
        except:
            # Signal might already be disconnected
            pass
    
    def _handle_item_selected(self, item):
        """Handle item selection from the list."""
        index = self.list_widget.row(item)
        self.setCurrentIndex(index)
        self.hidePopup()
        self.activated.emit(index)
        
    def eventFilter(self, obj, event):
        """Handle events for checking if clicked outside the popup."""
        if event.type() == QEvent.Type.MouseButtonPress and self.popup_visible:
            # Check if the click is outside both the combo box and the popup
            pos = event.globalPosition().toPoint()
            if not self.popup_frame.geometry().contains(pos) and not self.geometry().contains(self.mapFromGlobal(pos)):
                self.hidePopup()
                return True
        return super().eventFilter(obj, event)
    
    def wheelEvent(self, event):
        """Override wheel event to prevent scroll changing the selection when popup is not visible."""
        if not self.popup_visible:
            event.ignore()


class APIKeysTab(QWidget):
    # Signal emitted when an API key is cleared
    api_key_cleared = pyqtSignal(str)
    
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.api_sections = {}  # Store references to API sections
        self.checkmark_path = None  # Initialize the checkmark path
        self.init_ui()
        
    def init_ui(self):
        # Create main layout with proper spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 0, 16)  # Right padding is 0
        
        # Set transparent background for this widget
        self.setStyleSheet("background-color: transparent;")

        # Get checkmark path for styling checkboxes
        if getattr(sys, 'frozen', False):
            # Running as bundled app
            base_path = sys._MEIPASS
            self.checkmark_path = os.path.join(base_path, "assets", "icons", "checkmark.svg")
        else:
            # Running in development
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.checkmark_path = os.path.join(app_dir, "ui", "assets", "icons", "checkmark.svg")

        # Create scroll area with modern styling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        scroll.setProperty("class", "global-scrollbar")
        
        # Apply scrollbar styling directly
        scrollbar = scroll.verticalScrollBar()
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

        # Create content widget for scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content.setProperty("class", "global-scrollbar")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(16)
        self.content_layout.setContentsMargins(0, 0, 8, 0)  # Added 8px right padding for gap between content and scrollbar

        # Create filter section with modern card design
        filter_section = self.create_filter_section()
        self.content_layout.addWidget(filter_section)

        # Initialize API key sections
        self.initialize_api_sections()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Connect internal signals
        self.search_input.textChanged.connect(self.apply_filters)
        self.category_combo.currentTextChanged.connect(self.apply_filters)
        self.show_empty.stateChanged.connect(self.apply_filters)
        self.show_filled.stateChanged.connect(self.apply_filters)

    def create_filter_section(self):
        """Create the search and filter section."""
        filter_widget = QFrame()
        filter_widget.setProperty("class", "card")
        filter_widget.setStyleSheet("""
            QFrame.card {
                background-color: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333333;
            }
        """)
        filter_layout = QVBoxLayout(filter_widget)
        filter_layout.setSpacing(12)
        filter_layout.setContentsMargins(16, 16, 16, 16)

        # Section title
        title_label = QLabel("Filter API Keys")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #e0e0e0;
            margin-bottom: 8px;
        """)
        filter_layout.addWidget(title_label)

        # Create form layout for consistent alignment
        form_widget = QWidget()
        form_widget.setStyleSheet("background-color: transparent;")
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)
        
        # Search bar with icon styling
        search_container = QWidget()
        search_container.setStyleSheet("background-color: transparent;")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(12)
        
        search_label = QLabel("Search:")
        search_label.setFixedWidth(90)
        search_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        search_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search API keys...")
        self.search_input.setProperty("class", "search-input")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #e67e22;
                background-color: #2d2d2d;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        form_layout.addWidget(search_container)

        # Category filter with modern styling
        category_container = QWidget()
        category_container.setStyleSheet("background-color: transparent;")
        category_layout = QHBoxLayout(category_container)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(12)
        
        category_label = QLabel("Category:")
        category_label.setFixedWidth(90)
        category_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        category_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        
        self.category_combo = CustomComboBox()
        self.category_combo.setProperty("class", "category-combo")
        self.category_combo.addItem("All Categories")
        self.category_combo.addItem(APICategory.LLM_PROVIDERS)
        self.category_combo.addItem(APICategory.SEARCH_PROVIDERS)
        self.category_combo.setStyleSheet("""
            QComboBox {
                padding: 10px 12px;
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                color: #e0e0e0;
                min-height: 20px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #e67e22;
                background-color: #2d2d2d;
            }
            QComboBox:focus {
                border: 1px solid #e67e22;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border-left: 1px solid #3b3b3b;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #3b3b3b;
                border-radius: 6px;
                selection-background-color: #e67e22;
                selection-color: white;
                padding: 4px;
            }
        """)
        
        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_combo)
        form_layout.addWidget(category_container)

        # Status filter with modern checkbox styling
        status_container = QWidget()
        status_container.setStyleSheet("background-color: transparent;")
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(12)
        
        status_label = QLabel("Status:")
        status_label.setFixedWidth(90)
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        
        checkbox_container = QWidget()
        checkbox_container.setStyleSheet("background-color: transparent;")
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(16)
        
        self.show_empty = QCheckBox("Show Empty")
        self.show_empty.setChecked(True)
        self.show_filled = QCheckBox("Show Filled")
        self.show_filled.setChecked(True)
        
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
        
        self.show_empty.setStyleSheet(checkbox_style)
        self.show_filled.setStyleSheet(checkbox_style)
        
        checkbox_layout.addWidget(self.show_empty)
        checkbox_layout.addWidget(self.show_filled)
        checkbox_layout.addStretch()
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(checkbox_container)
        
        form_layout.addWidget(status_container)
        filter_layout.addWidget(form_widget)

        return filter_widget

    def initialize_api_sections(self):
        """Initialize all API key sections using our modular components."""
        # Create Custom OpenAI Section (will be used by LLM section)
        self.custom_openai_section = CustomOpenAISection(self.settings)
        self.custom_openai_section.api_key_cleared.connect(self.api_key_cleared)
        
        # Create LLM Providers Section
        self.llm_section = LLMProvidersSection(self.settings, self.custom_openai_section)
        self.llm_section.api_key_cleared.connect(self.api_key_cleared)
        self.content_layout.addWidget(self.llm_section)
        
        # Create Search Providers Section
        self.search_section = SearchProvidersSection(self.settings)
        self.search_section.api_key_cleared.connect(self.api_key_cleared)
        self.content_layout.addWidget(self.search_section)
        
        # Collect API sections from components
        self.api_sections.update(self.llm_section.get_api_sections())
        self.api_sections.update(self.custom_openai_section.get_api_sections())
        self.api_sections.update(self.search_section.get_api_sections())

    def apply_filters(self):
        """Apply search and filter criteria to API key sections."""
        search_text = self.search_input.text().lower()
        selected_category = self.category_combo.currentText()
        show_empty = self.show_empty.isChecked()
        show_filled = self.show_filled.isChecked()

        # Track visible items per category
        visible_items = {
            APICategory.LLM_PROVIDERS: 0,
            APICategory.SEARCH_PROVIDERS: 0
        }

        # Apply filters to all API sections
        for provider, section_info in self.api_sections.items():
            widget = section_info['widget']
            category = section_info['category']
            
            # Find the API key input field and searchable text
            api_input = None
            searchable_text = ""
            has_key = False
            
            if provider.startswith('custom_openai'):
                # For custom OpenAI, use the stored sections data in custom_openai_section
                for section in self.custom_openai_section.custom_openai_sections:
                    if section['provider_key'] == provider:
                        api_input = section['api_input']
                        model_id = section['model_id_input'].text().strip()
                        base_url = section['base_url_input'].text().strip()
                        title_label = widget.findChild(QLabel)
                        title_text = title_label.text() if title_label else "Custom OpenAI Model"
                        searchable_text = f"{title_text} {model_id} {base_url}".lower()
                        has_key = bool(api_input.text().strip())
                        break
                else:
                    # Skip if we can't find the section
                    continue
            else:
                # For regular API sections, search for title and input field within the widget
                # First, try to find a QLabel (title) within the widget
                labels = widget.findChildren(QLabel)
                for label in labels:
                    # Look for the main title label (usually first with styling)
                    if "font-weight: bold" in label.styleSheet() and "font-size: 15px" in label.styleSheet():
                        searchable_text = label.text().lower()
                        break
                    # Fallback to any label if we can't find one with specific styling
                    elif searchable_text == "":
                        searchable_text = label.text().lower()

                # Then find the QLineEdit (API input) - it should have EchoMode.Password
                inputs = widget.findChildren(QLineEdit)
                for input_field in inputs:
                    if input_field.echoMode() == QLineEdit.EchoMode.Password:
                        api_input = input_field
                        has_key = bool(api_input.text().strip())
                        break
                
                # Skip if we can't find an API input
                if not api_input:
                    continue
            
            # Apply filters
            should_show = True

            # Category filter
            if selected_category != "All Categories" and category != selected_category:
                should_show = False

            # Search filter
            if search_text and search_text not in searchable_text:
                should_show = False

            # Status filter
            if has_key and not show_filled:
                should_show = False
            if not has_key and not show_empty:
                should_show = False

            widget.setVisible(should_show)
            
            # Count visible items per category
            if should_show:
                visible_items[category] += 1

        # Determine section visibility based on visible items
        self.llm_section.set_visibility(
            visible_items[APICategory.LLM_PROVIDERS] > 0 or 
            selected_category == "All Categories" or 
            selected_category == APICategory.LLM_PROVIDERS
        )
        
        self.search_section.set_visibility(
            visible_items[APICategory.SEARCH_PROVIDERS] > 0 or 
            selected_category == "All Categories" or 
            selected_category == APICategory.SEARCH_PROVIDERS
        ) 