from PyQt6.QtWidgets import QApplication
import logging
import socket
import sys
import os
import msvcrt  # For Windows file locking
import errno
from pathlib import Path


class DasiInstanceManager:
    """Singleton class to manage the Dasi instance across the application."""

    SOCKET_NAME = '\0dasi_lock'  # Used for Linux/macOS
    # Define lock file path for Windows
    LOCK_FILE_PATH = os.path.join(Path.home(), '.config', 'dasi', 'dasi.lock')

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

    _server_socket = None  # Keep a reference to the bound socket (Linux/macOS)
    # Keep a reference to the lock file handle (Windows)
    _lock_file_handle = None

    @staticmethod
    def is_running():
        """Check if Dasi is already running using platform-specific methods."""
        if sys.platform == 'win32':
            # Ensure the config directory exists
            os.makedirs(os.path.dirname(
                DasiInstanceManager.LOCK_FILE_PATH), exist_ok=True)
            try:
                # Open the lock file in binary read/write mode
                DasiInstanceManager._lock_file_handle = os.open(
                    DasiInstanceManager.LOCK_FILE_PATH,
                    os.O_CREAT | os.O_RDWR | os.O_BINARY
                )
                # Try to acquire an exclusive, non-blocking lock
                msvcrt.locking(
                    DasiInstanceManager._lock_file_handle, msvcrt.LK_NBLCK, 1)
                logging.debug(
                    f"Successfully acquired lock on {DasiInstanceManager.LOCK_FILE_PATH}. Assuming this is the primary instance.")
                # Lock acquired, so no other instance is running
                return False
            except IOError as e:
                if e.errno == errno.EACCES or e.errno == errno.EROFS or e.errno == errno.EAGAIN:
                    # Lock already held by another instance
                    logging.warning(
                        f"Could not acquire lock on {DasiInstanceManager.LOCK_FILE_PATH}. Another instance might be running.")
                    if DasiInstanceManager._lock_file_handle:
                        os.close(DasiInstanceManager._lock_file_handle)
                        DasiInstanceManager._lock_file_handle = None
                    return True
                else:
                    # Other unexpected IO error
                    logging.error(
                        f"Unexpected IO error when checking for existing instance via file lock: {e}")
                    if DasiInstanceManager._lock_file_handle:
                        os.close(DasiInstanceManager._lock_file_handle)
                        DasiInstanceManager._lock_file_handle = None
                    return True  # Assume another instance is running on unexpected error
            except Exception as e:
                # Catch any other potential exceptions
                logging.error(f"Unexpected error during file lock check: {e}")
                if DasiInstanceManager._lock_file_handle:
                    os.close(DasiInstanceManager._lock_file_handle)
                    DasiInstanceManager._lock_file_handle = None
                return True  # Assume running on error
        else:
            # Use abstract Unix domain socket for Linux/macOS
            try:
                DasiInstanceManager._server_socket = socket.socket(
                    socket.AF_UNIX, socket.SOCK_STREAM)
                # The leading null byte creates an abstract socket
                DasiInstanceManager._server_socket.bind(
                    DasiInstanceManager.SOCKET_NAME)
                logging.debug(
                    f"Successfully bound to abstract socket {DasiInstanceManager.SOCKET_NAME}. Assuming this is the primary instance.")
                return False
            except socket.error as e:
                # EADDRINUSE usually means another instance is running
                if e.errno == socket.errno.EADDRINUSE:
                    logging.warning(
                        f"Abstract socket {DasiInstanceManager.SOCKET_NAME} is already in use. Another instance might be running.")
                    return True
                else:
                    logging.error(
                        f"Unexpected socket error when checking for existing instance: {e}")
                    return True  # Assume another instance is running on unexpected error

    @staticmethod
    def release_lock():
        """Release the instance lock (file lock on Windows, socket on Linux/macOS)."""
        if sys.platform == 'win32':
            if DasiInstanceManager._lock_file_handle:
                try:
                    msvcrt.locking(
                        DasiInstanceManager._lock_file_handle, msvcrt.LK_UNLCK, 1)
                    os.close(DasiInstanceManager._lock_file_handle)
                    DasiInstanceManager._lock_file_handle = None
                    # Optionally remove the lock file, though not strictly necessary
                    # try:
                    #     os.remove(DasiInstanceManager.LOCK_FILE_PATH)
                    # except OSError as e:
                    #     logging.warning(f"Could not remove lock file {DasiInstanceManager.LOCK_FILE_PATH}: {e}")
                    logging.debug("File lock released.")
                except Exception as e:
                    logging.error(f"Error releasing file lock: {e}")
        else:
            if DasiInstanceManager._server_socket:
                try:
                    DasiInstanceManager._server_socket.close()
                    DasiInstanceManager._server_socket = None
                    logging.debug("Instance check socket released.")
                except Exception as e:
                    logging.error(f"Error closing instance check socket: {e}")
