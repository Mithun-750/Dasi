from PyQt6.QtWidgets import QApplication
import logging
import socket
import os
import sys
import tempfile
import platform

class DasiInstanceManager:
    """Singleton class to manage the Dasi instance across the application."""
    
    # Use different socket approaches based on platform
    IS_WINDOWS = platform.system() == "Windows"
    
    # For Unix systems, use AF_UNIX socket
    SOCKET_NAME = '\0dasi_lock'
    
    # For Windows, use a TCP socket on localhost with a specific port
    WINDOWS_HOST = '127.0.0.1'
    WINDOWS_PORT = 45678
    
    # For Windows, also use a lock file as a secondary mechanism
    @staticmethod
    def get_lock_file_path():
        """Get the path to the lock file for Windows."""
        return os.path.join(tempfile.gettempdir(), 'dasi_instance.lock')
    
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
        """Check if Dasi is already running using platform-specific methods."""
        if DasiInstanceManager.IS_WINDOWS:
            # Windows implementation using TCP socket
            try:
                # Try to create and bind a TCP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((DasiInstanceManager.WINDOWS_HOST, DasiInstanceManager.WINDOWS_PORT))
                sock.listen(1)
                
                # Keep the socket open to prevent other instances from binding
                # Store it as a static variable so it doesn't get garbage collected
                DasiInstanceManager._lock_socket = sock
                
                # Also create a lock file as a secondary mechanism
                lock_file_path = DasiInstanceManager.get_lock_file_path()
                with open(lock_file_path, 'w') as f:
                    f.write(str(os.getpid()))
                
                # If we get here, Dasi is not running
                return False
            except socket.error:
                # If we can't bind, Dasi is already running
                return True
        else:
            # Unix implementation using AF_UNIX socket
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.bind(DasiInstanceManager.SOCKET_NAME)
                
                # Keep the socket open to prevent other instances from binding
                # Store it as a static variable so it doesn't get garbage collected
                DasiInstanceManager._lock_socket = sock
                
                # If we get here, Dasi is not running
                return False
            except socket.error:
                # If we can't bind, Dasi is already running
                return True
    
    @staticmethod
    def cleanup():
        """Clean up resources when the application exits."""
        if hasattr(DasiInstanceManager, '_lock_socket'):
            try:
                DasiInstanceManager._lock_socket.close()
                if DasiInstanceManager.IS_WINDOWS:
                    # Remove the lock file on Windows
                    lock_file_path = DasiInstanceManager.get_lock_file_path()
                    if os.path.exists(lock_file_path):
                        os.remove(lock_file_path)
            except Exception as e:
                logging.error(f"Error cleaning up instance manager: {str(e)}") 