from PyQt6.QtWidgets import QApplication
import logging
import socket

class DasiInstanceManager:
    """Singleton class to manage the Dasi instance across the application."""
    
    SOCKET_NAME = '\0dasi_lock'
    
    @staticmethod
    def set_instance(instance):
        """Store the Dasi instance in the application."""
        app = QApplication.instance()
        if app:
            app.setProperty("dasi_instance", instance)
            logging.debug("Dasi instance stored in QApplication")
    
    @staticmethod
    def get_instance():
        """Get the Dasi instance from the application."""
        app = QApplication.instance()
        if app:
            return app.property("dasi_instance")
        return None
    
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