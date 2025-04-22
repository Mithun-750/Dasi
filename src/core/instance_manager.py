import logging
import socket
from typing import Optional
from PyQt6.QtWidgets import QApplication


class DasiInstanceManager:
    """
    Singleton manager for the main Dasi application instance.
    Helps access the main app instance from child windows or other components.
    """
    _instance = None
    _tool_call_handler = None

    SOCKET_NAME = '\0dasi_lock'

    @classmethod
    def set_instance(cls, instance):
        """Set the Dasi application instance."""
        cls._instance = instance
        app = QApplication.instance()
        if app:
            app.setProperty("dasi_instance", instance)
            logging.debug("Dasi instance stored in QApplication")

    @classmethod
    def get_instance(cls):
        """Get the Dasi application instance."""
        if cls._instance:
            return cls._instance

        # Fallback to QApplication property
        app = QApplication.instance()
        if app:
            return app.property("dasi_instance")
        return None

    @classmethod
    def get_tool_call_handler(cls):
        """Get or create the shared ToolCallHandler instance."""
        if cls._tool_call_handler is None:
            # Import here to avoid circular imports
            from core.tools.tool_call_handler import ToolCallHandler
            cls._tool_call_handler = ToolCallHandler()
        return cls._tool_call_handler

    @staticmethod
    def clear_instance():
        """Clear the Dasi instance from the application."""
        app = QApplication.instance()
        if app:
            app.setProperty("dasi_instance", None)
            logging.debug("Dasi instance cleared from QApplication")

    @staticmethod
    def is_running():
        """Check if Dasi is already running by trying to bind to the socket."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(DasiInstanceManager.SOCKET_NAME)
            sock.close()
            # If we get here, Dasi is not running
            return False
        except socket.error:
            # If we can't bind, Dasi is already running
            return True
