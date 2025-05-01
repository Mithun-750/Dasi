from PyQt6.QtCore import QObject, pyqtSignal


class UISignals(QObject):
    """Signals for UI operations."""
    show_window = pyqtSignal(int, int, bool)  # x, y coordinates, centered flag
    process_response = pyqtSignal(str)  # Response text
    process_error = pyqtSignal(str)  # Error message
