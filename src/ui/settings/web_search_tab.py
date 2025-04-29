import os
import sys
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QCheckBox,
    QSpinBox,
    QGridLayout,
    QMessageBox,
    QStyledItemDelegate,
    QProxyStyle,
    QStyle,
    QListWidget,
    QListWidgetItem,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QDir, QPoint, QRect, QPropertyAnimation, QEasingCurve, QEvent
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QColor, QPen
from .settings_manager import Settings
from .general_tab import SectionFrame  # Import SectionFrame from general_tab
import logging


# Custom style to draw a text arrow for combo boxes
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
        self.popup_frame.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
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
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("background-color: transparent;")
        self.scroll_area.setProperty("class", "global-scrollbar")

        # Create list widget for items
        self.list_widget = QListWidget()
        self.list_widget.setProperty("class", "popup-list global-scrollbar")
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
        # Minimum width for better readability
        popup_width = max(self.width(), 260)

        # Calculate height based on number of items (limited by max_visible_items)
        items_height = min(
            self.count(), self.max_visible_items) * self.item_height
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
        end_rect = QRect(current_rect.x(), current_rect.y(),
                         current_rect.width(), 0)

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


class WebSearchTab(QWidget):
    """Tab for configuring web search settings."""

    # Signal emitted when search settings change
    search_settings_changed = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.original_values = {}
        self.has_unsaved_changes = False
        self.checkmark_path = None  # Initialize the checkmark path
        self.init_ui()
        self.save_original_values()

    def save_original_values(self):
        """Save the original values of all settings for comparison."""
        self.original_values = {
            'default_provider': self.settings.get('web_search', 'default_provider', default='ddg_search'),
            'max_results': self.settings.get('web_search', 'max_results', default=3),
        }
        self.has_unsaved_changes = False
        self.update_button_visibility()

    def get_current_values(self):
        """Get the current values of all settings."""
        # All providers are always enabled
        all_providers = [
            'ddg_search',  # Move DuckDuckGo first as default
            'google_serper',
            'brave_search',
            'exa_search',
            'tavily_search'
        ]

        return {
            'default_provider': self.default_provider.currentData(),
            'max_results': self.max_results.value(),
            'enabled_providers': all_providers,
        }

    def check_for_changes(self):
        """Check if there are any unsaved changes."""
        current = self.get_current_values()
        self.has_unsaved_changes = any([
            current['default_provider'] != self.original_values['default_provider'],
            current['max_results'] != self.original_values['max_results'],
        ])

        self.update_button_visibility()

    def update_button_visibility(self):
        """Update the visibility of action buttons based on changes."""
        self.button_container.setVisible(self.has_unsaved_changes)

    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        # Adjusted right margin from 0 to 16
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Get checkmark path for styling checkboxes
        if getattr(sys, 'frozen', False):
            # Running as bundled app
            base_path = sys._MEIPASS
            self.checkmark_path = os.path.join(
                base_path, "assets", "icons", "checkmark.svg")
        else:
            # Running in development
            app_dir = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
            self.checkmark_path = os.path.join(
                app_dir, "ui", "assets", "icons", "checkmark.svg")

        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { 
                background-color: transparent; 
            }
        """)

        # Content widget for scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)  # Removed 8px right padding

        # General search settings section
        general_section = SectionFrame(
            "Web Search Settings",
            "Configure how Dasi performs web searches and presents results."
        )

        # Default search provider
        provider_container = QWidget()
        provider_container.setProperty("class", "transparent-container")
        provider_layout = QVBoxLayout(provider_container)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.setSpacing(8)

        provider_label = QLabel("Default Search Provider")
        provider_label.setProperty("class", "setting-label")

        self.default_provider = CustomComboBox()
        # Updated modern UI styling that matches the global stylesheet
        self.default_provider.setStyleSheet("""
            QComboBox {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 10px 12px;
                color: #e0e0e0;
                min-height: 20px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #e67e22;
                background-color: #2a2a2a;
            }
            QComboBox:focus {
                border: 1px solid #e67e22;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border-left: 1px solid #333333;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: transparent;
            }
        """)

        # Add search providers
        # Move DuckDuckGo first as it's now default
        self.default_provider.addItem("DuckDuckGo Search", "ddg_search")
        self.default_provider.addItem("Google Serper", "google_serper")
        self.default_provider.addItem("Brave Search", "brave_search")
        self.default_provider.addItem("Exa Search", "exa_search")
        self.default_provider.addItem("Tavily Search", "tavily_search")

        # Set current default provider - changed to ddg_search as default
        current_provider = self.settings.get(
            'web_search', 'default_provider', default='ddg_search')
        index = self.default_provider.findData(current_provider)
        if index >= 0:
            self.default_provider.setCurrentIndex(index)

        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.default_provider)

        # Max results
        results_container = QWidget()
        results_container.setProperty("class", "transparent-container")
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(8)

        results_label = QLabel("Maximum Search Results")
        results_label.setProperty("class", "setting-label")

        # Create a custom container for spinbox with buttons
        value_container = QWidget()
        value_container.setFixedWidth(80)
        value_layout = QHBoxLayout(value_container)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(4)

        # Create spinbox without buttons - update default to 3
        self.max_results = QSpinBox()
        self.max_results.setRange(1, 20)
        self.max_results.setValue(self.settings.get(
            'web_search', 'max_results', default=3))
        self.max_results.setFixedWidth(50)
        self.max_results.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.max_results.setStyleSheet("""
            QSpinBox {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 5px;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 1px solid #3b82f6;
                background-color: #2a2a2a;
            }
        """)

        # Create custom up/down buttons in a vertical layout
        button_container = QWidget()
        button_container.setFixedWidth(20)
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(1)

        # Up button
        up_button = QPushButton("▲")
        up_button.setFixedSize(20, 14)
        up_button.setCursor(Qt.CursorShape.PointingHandCursor)
        up_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 2px;
                font-size: 8px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #666666;
            }
        """)

        # Down button
        down_button = QPushButton("▼")
        down_button.setFixedSize(20, 14)
        down_button.setCursor(Qt.CursorShape.PointingHandCursor)
        down_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 2px;
                font-size: 8px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #666666;
            }
        """)

        # Add buttons to the button layout
        button_layout.addWidget(up_button)
        button_layout.addWidget(down_button)

        # Add spinbox and buttons to the value layout
        value_layout.addWidget(self.max_results)
        value_layout.addWidget(button_container)

        # Connect custom buttons
        up_button.clicked.connect(self._increment_max_results)
        down_button.clicked.connect(self._decrement_max_results)

        # Connect change signal
        self.max_results.valueChanged.connect(self._on_any_change)

        results_layout.addWidget(results_label)
        results_layout.addWidget(value_container)

        # Add all to general layout
        general_section.layout.addWidget(provider_container)
        general_section.layout.addWidget(results_container)

        # Add sections to main layout
        layout.addWidget(general_section)
        layout.addStretch()

        # Set scroll area widget
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Create button container at the bottom
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
        save_all_button = QPushButton("Save")
        save_all_button.setProperty("class", "primary")
        save_all_button.setStyleSheet("""
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
        save_all_button.clicked.connect(self._save_all_changes)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(save_all_button)

        main_layout.addWidget(self.button_container)
        self.button_container.hide()  # Initially hide the buttons

        # Connect change signals
        self.default_provider.currentIndexChanged.connect(self._on_any_change)
        self.max_results.valueChanged.connect(self._on_any_change)

    def _on_any_change(self):
        """Handler for any change in the settings."""
        try:
            self.check_for_changes()
        except Exception as e:
            logging.error(
                f"Error handling settings change: {e}", exc_info=True)
            # Don't show error dialog here to avoid spamming the user
            # Just log the error for debugging

    def _cancel_changes(self):
        """Cancel all changes and restore original values."""
        try:
            # Restore default provider
            index = self.default_provider.findData(
                self.original_values['default_provider'])
            if index >= 0:
                self.default_provider.setCurrentIndex(index)

            # Restore max results
            self.max_results.setValue(self.original_values['max_results'])

            self.has_unsaved_changes = False
            self.update_button_visibility()
        except Exception as e:
            logging.error(f"Error canceling changes: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to cancel changes: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _save_all_changes(self):
        """Save all changes to settings."""
        try:
            logging.info("Saving web search settings")
            current = self.get_current_values()

            # Save default provider - Corrected argument order
            self.settings.set('web_search', 'default_provider',
                              current['default_provider'])

            # Save max results
            self.settings.set('web_search', 'max_results',
                              current['max_results'])

            # Save enabled providers - all providers are always enabled
            self.settings.set('web_search', 'enabled_providers',
                              current['enabled_providers'])

            # Update original values
            self.save_original_values()
            logging.info("Web search settings saved successfully")

            # Emit signal that search settings changed
            self.search_settings_changed.emit()

            # Show simple success message instead of always prompting for restart
            QMessageBox.information(
                self,
                "Settings Saved",
                "Web search settings saved successfully."
            )
        except Exception as e:
            logging.error(f"Error saving settings: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _increment_max_results(self):
        """Increment max results value."""
        try:
            current_value = self.max_results.value()
            new_value = min(current_value + 1, 20)
            self.max_results.setValue(new_value)
        except Exception as e:
            logging.error(
                f"Error incrementing max results: {str(e)}", exc_info=True)

    def _decrement_max_results(self):
        """Decrement max results value."""
        try:
            current_value = self.max_results.value()
            new_value = max(current_value - 1, 1)
            self.max_results.setValue(new_value)
        except Exception as e:
            logging.error(
                f"Error decrementing max results: {str(e)}", exc_info=True)

    def _reset_changes(self):
        """Reset all changes and restore original values."""
        try:
            # Restore default provider
            index = self.default_provider.findData(
                self.original_values['default_provider'])
            if index >= 0:
                self.default_provider.setCurrentIndex(index)

            # Restore max results
            self.max_results.setValue(self.original_values['max_results'])

            self.has_unsaved_changes = False
            self.update_button_visibility()
        except Exception as e:
            logging.error(f"Error resetting changes: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to reset changes: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
