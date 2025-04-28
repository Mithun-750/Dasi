from core.cache_manager import CacheManager
from ui.settings_window import SettingsWindow
from ui.settings import Settings
from core.langgraph_handler import LangGraphHandler
import os
import sys
import logging
import pyautogui
import pyperclip
import time
from pathlib import Path
from hotkey_listener import HotkeyListener
from ui.popup.ui import CopilotUI
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from typing import Optional, Callable
# Import constants

# Import instance manager
from core.instance_manager import DasiInstanceManager
# Import theme system
from ui.assets import apply_theme

# Global cache manager instance
cache_manager = None

# Import necessary handlers and classes directly


def setup_logging():
    """Set up logging with proper error handling."""
    try:
        # Get user's home directory
        home = str(Path.home())
        config_dir = os.path.join(home, '.config', 'dasi')
        log_dir = os.path.join(config_dir, 'logs')

        # Create directories with proper permissions
        os.makedirs(config_dir, mode=0o755, exist_ok=True)
        os.makedirs(log_dir, mode=0o755, exist_ok=True)

        log_file = os.path.join(log_dir, 'dasi.log')

        # Create log file if it doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                pass
            os.chmod(log_file, 0o644)

        # Set up logging
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='a'
        )

        # Add console handler for development
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

        logging.info("Logging setup completed")

    except Exception as e:
        # If we can't set up logging to file, set up console-only logging
        print(f"Failed to setup file logging: {str(e)}", file=sys.stderr)
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        logging.error(f"Failed to setup file logging: {str(e)}")


# Set up logging first thing
setup_logging()


class StartupThread(QThread):
    """Background thread for handling slow startup tasks."""
    finished = pyqtSignal()

    def __init__(self, llm_integration):
        super().__init__()
        self.llm_integration = llm_integration
        self.cache_manager = cache_manager

    def run(self):
        """Execute startup tasks in background."""
        logging.info("Starting background initialization...")
        start_time = time.time()

        # Perform any heavy initialization here
        # For example, pre-loading models or resources
        try:
            # Check if we have a cached model initialization
            if self.cache_manager:
                # Warm up the LLM with a simple query that's cached
                cached_response = self.cache_manager.get_from_cache(
                    "startup_warmup", namespace="system")
                if not cached_response:
                    logging.info("Creating startup cache...")
                    # Don't actually make a query, just initialize the model
                    self.llm_integration.initialize_llm()
                    # Create a cache entry so we know initialization completed
                    self.cache_manager.save_to_cache(
                        "startup_warmup",
                        {"status": "completed", "timestamp": time.time(),
                         "namespace": "system"},
                        namespace="system")
                else:
                    logging.info("Using startup cache")
        except Exception as e:
            logging.error(f"Error in startup thread: {str(e)}", exc_info=True)

        elapsed = time.time() - start_time
        logging.info(f"Background initialization completed in {elapsed:.2f}s")
        self.finished.emit()


class Dasi:
    def __init__(self):
        """Initialize Dasi."""
        try:
            logging.info("Starting Dasi application")
            start_time = time.time()

            # Initialize cache manager first for fastest startup
            global cache_manager
            cache_manager = CacheManager()
            logging.info("Cache manager initialized")

            # Ensure we have only one QApplication instance
            if not QApplication.instance():
                self.app = QApplication(sys.argv)
            else:
                self.app = QApplication.instance()

            # Apply our modern theme
            apply_theme(self.app, "dark")

            # Keep running when windows are closed
            self.app.setQuitOnLastWindowClosed(False)

            # Register this instance with the instance manager
            DasiInstanceManager.set_instance(self)

            # Initialize settings
            self.settings = Settings()

            # LangGraph is now the only implementation
            # Set use_langgraph to True in settings for backward compatibility
            self.settings.set('general', 'use_langgraph', True)

            # Initialize system tray
            logging.info("Setting up system tray")
            self.tray = None  # Initialize to None first
            self.setup_tray()

            # Initialize LangGraphHandler directly
            self.llm_handler = LangGraphHandler()
            logging.info("LangGraphHandler initialized directly in Dasi")

            # Initialize UI
            logging.info("Initializing UI")
            self.ui = CopilotUI(self.process_query)

            # Initialize hotkey listener but don't start it yet
            logging.info("Initializing hotkey listener")
            self.hotkey_listener = HotkeyListener(self.ui.show_popup)

            # Initialize settings window (but don't show it)
            self.settings_window = None

            # Start background initialization thread for non-critical tasks
            self.startup_thread = StartupThread(self.llm_handler)
            self.startup_thread.finished.connect(
                self.on_background_init_complete)
            self.startup_thread.start()

            logging.info(
                f"Application initialized in {time.time() - start_time:.2f}s")

        except Exception as e:
            logging.error(
                f"Error during initialization: {str(e)}", exc_info=True)
            raise

    def setup_tray(self):
        """Setup system tray icon and menu."""
        try:
            # Check if system tray is available first
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logging.error("System tray is not available on this system")
                raise RuntimeError(
                    "System tray is not available on this system")

            self.tray = QSystemTrayIcon()

            # Get the current hotkey settings
            settings = Settings()
            hotkey = settings.get('general', 'hotkey', default={
                'ctrl': True,
                'alt': True,
                'shift': True,
                'super': False,
                'fn': False,
                'key': 'I'
            })

            # Build hotkey display string
            hotkey_parts = []
            if hotkey['ctrl']:
                hotkey_parts.append('Ctrl')
            if hotkey['alt']:
                hotkey_parts.append('Alt')
            if hotkey['shift']:
                hotkey_parts.append('Shift')
            if hotkey['super']:
                hotkey_parts.append('Super')
            if hotkey['fn']:
                hotkey_parts.append('Fn')
            hotkey_parts.append(hotkey['key'])

            hotkey_display = '+'.join(hotkey_parts)

            # Get the absolute path to the icon
            if getattr(sys, 'frozen', False):
                # If we're running as a bundled app
                base_path = sys._MEIPASS
                logging.info(f"Running as bundled app, base path: {base_path}")
            else:
                # If we're running in development
                base_path = os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__)))
                logging.info(f"Running in development, base path: {base_path}")

            # Try multiple icon paths
            potential_icon_paths = [
                # First check environment variable (used by AppImage)
                os.environ.get('DASI_ICON_PATH'),
                # Check for dedicated icon locations within the AppImage
                '/usr/share/icons/hicolor/256x256/apps/dasi.png',
                '/usr/share/pixmaps/dasi.png',
                # Check standard directories
                os.path.join(base_path, 'assets', 'Dasi.png'),
                os.path.join(base_path, 'assets', 'icons', 'dasi.png'),
                os.path.join(base_path, 'Dasi.png'),
                os.path.join(os.path.dirname(base_path), 'assets', 'Dasi.png'),
                # Check user installation directories
                os.path.expanduser('~/.local/share/icons/dasi.png'),
                os.path.expanduser(
                    '~/.local/share/icons/hicolor/256x256/apps/dasi.png'),
            ]

            icon_path = None
            for path in potential_icon_paths:
                if path and os.path.exists(path):
                    logging.info(f"Found icon at path: {path}")
                    icon_path = path
                    break
                elif path:
                    logging.debug(f"Icon not found at: {path}")

            if icon_path is None:
                logging.warning(
                    "Icon not found in any standard locations. Using fallback icon.")
                # Create a simple fallback icon
                pixmap = QPixmap(32, 32)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(
                    pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
                painter.end()
                self.tray.setIcon(QIcon(pixmap))
            else:
                logging.info(f"Using icon from: {icon_path}")
                icon = QIcon(icon_path)
                # Check if the icon is valid
                if icon.isNull():
                    logging.warning(
                        f"Icon at {icon_path} is invalid. Using fallback icon.")
                    pixmap = QPixmap(32, 32)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap)
                    painter.setPen(Qt.GlobalColor.white)
                    painter.drawText(
                        pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
                    painter.end()
                    self.tray.setIcon(QIcon(pixmap))
                else:
                    self.tray.setIcon(icon)

            # Create tray menu
            menu = QMenu()

            # Add menu items
            settings_action = menu.addAction("Settings")
            settings_action.triggered.connect(self.show_settings)

            menu.addSeparator()

            quit_action = menu.addAction("Quit")
            quit_action.triggered.connect(self.quit_app)

            # Set the menu
            self.tray.setContextMenu(menu)

            # Show the tray icon
            self.tray.show()

            # Show startup notification with actual hotkey
            self.tray.showMessage(
                "Dasi",
                f"Dasi is running. Press {hotkey_display} to activate.",
                QSystemTrayIcon.MessageIcon.Information,
                3000  # Show for 3 seconds
            )

            logging.info("System tray setup completed successfully")

        except Exception as e:
            logging.error(
                f"Failed to setup system tray: {str(e)}", exc_info=True)
            # Don't raise here - we want the app to continue even without tray
            self.tray = None

    def show_settings(self):
        """Show settings window."""
        try:
            if not self.settings_window:
                from ui.settings import SettingsWindow
                self.settings_window = SettingsWindow(dasi_instance=self)

                # Apply theme again to ensure all widgets are styled properly
                apply_theme(self.app, "dark")

            self.settings_window.show()
            self.settings_window.activateWindow()
            # Force a style refresh to ensure correct appearance
            self.settings_window.style().unpolish(self.settings_window)
            self.settings_window.style().polish(self.settings_window)
            # Also refresh child widgets
            for widget in self.settings_window.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        except Exception as e:
            logging.error(f"Error showing settings: {str(e)}", exc_info=True)

    def quit_app(self):
        """Quit the application."""
        try:
            logging.info("Shutting down application")
            if self.hotkey_listener:
                self.hotkey_listener.stop()
            if self.tray:
                self.tray.hide()

            # Clear the instance from manager
            DasiInstanceManager.clear_instance()

            if QApplication.instance():
                QApplication.instance().quit()
        except Exception as e:
            logging.error(f"Error during shutdown: {str(e)}", exc_info=True)
            sys.exit(1)  # Force exit if clean shutdown fails
        sys.exit(0)

    def on_background_init_complete(self):
        """Handle completion of background initialization."""
        logging.info("Background initialization completed")
        # Any tasks that should run after initialization

    def process_query(self, query: str, callback: Optional[Callable[[str], None]] = None,
                      model: Optional[str] = None, image_data: Optional[str] = None) -> str:
        """Process a query and return the response."""
        start_time = time.time()

        # Handle special commands
        try:
            # Handle special commands
            if query.startswith('!'):
                if query.startswith('!clear_session:'):
                    session_id = query.split(':', 1)[1]
                    self.llm_handler.clear_chat_history(session_id)
                    # Don't cache this command or make an LLM call
                    return ""
                elif query.startswith('!paste:'):
                    # Extract the text to paste
                    text = query[7:]  # Skip !paste:
                    if text:
                        # Copy to clipboard
                        pyperclip.copy(text)
                        # Perform paste operation
                        pyautogui.hotkey('ctrl', 'v')
                        logging.info(
                            f"Pasted text via clipboard: {text[:50]}...")
                    return ""
                elif query.startswith('!type:'):
                    # Extract the text to type
                    text = query[6:]  # Skip !type:
                    if text:
                        # Type the text character by character with a small delay
                        pyautogui.write(text, interval=0.01)
                        logging.info(f"Typed text: {text[:50]}...")
                    return ""
                # Handle other special commands...
        except Exception as e:
            logging.error(
                f"Error processing special command: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

        # Check for cache if it's enabled in settings
        use_cache = self.settings.get('general', 'use_cache', default=True)
        session_id = "default"  # Extract session ID if present in query

        # Extract session ID if this is a session-specific query
        if query.startswith('!session:'):
            # Extract session ID and actual query
            _, rest = query.split(':', 1)
            extracted_session_id, actual_query = rest.split('|', 1)
            session_id = extracted_session_id
            # For caching purposes, use the actual query
            cache_query = actual_query
        else:
            cache_query = query

        if use_cache and cache_manager:
            # Create a cache key from the query, model AND session_id
            cache_key = f"{session_id}:{cache_query}"
            if model:
                cache_key = f"{model}:{session_id}:{cache_query}"

            # Add image_data to cache key if present
            if image_data:
                # Just use presence of image as cache key, not the full data
                cache_key = f"image:{cache_key}"

            # Try to get response from cache
            cached_data = cache_manager.get_from_cache(cache_key, namespace="queries",
                                                       max_age=86400)  # 24 hour cache

            if cached_data and 'response' in cached_data:
                logging.info(
                    f"Cache hit for query (took {time.time() - start_time:.3f}s)")
                response = cached_data['response']

                # Call the callback if provided, with the full cached response
                if callback:
                    callback(response)

                return response

        # If not cached or caching disabled, call LLM handler
        # Pass image_data to the handler
        logging.info(
            f"Calling LLM handler with query, has_image_data={image_data is not None}")
        mode = "compose" if "=====MODE=====<user selected mode>\ncompose" in query else "chat"

        # Extract selected text if it exists in the query
        selected_text = None
        if "=====SELECTED_TEXT=====" in query:
            try:
                # Extract selected text between markers
                start_marker = "=====SELECTED_TEXT=====<text selected by the user>\n"
                end_marker = "\n======================="
                start_idx = query.find(start_marker) + len(start_marker)
                end_idx = query.find(end_marker, start_idx)
                if start_idx > len(start_marker) - 1 and end_idx > start_idx:
                    selected_text = query[start_idx:end_idx]
            except Exception as e:
                logging.error(f"Error extracting selected_text: {str(e)}")

        response = self.llm_handler.get_response(
            query, callback, model, session_id, selected_text, mode, image_data)

        # Cache the response if caching is enabled (and it's not a special command)
        if use_cache and cache_manager and response and not query.startswith('!'):
            # Include session ID in the cache key
            cache_key = f"{session_id}:{cache_query}"
            if model:
                cache_key = f"{model}:{session_id}:{cache_query}"

            cache_manager.save_to_cache(
                cache_key,
                {"response": response, "timestamp": time.time(),
                 "namespace": "queries", "session_id": session_id},
                namespace="queries"
            )

        logging.info(f"Query processed in {time.time() - start_time:.3f}s")
        return response

    def check_selected_models(self):
        """Check if any models are selected in the settings."""
        try:
            return bool(self.settings.get_selected_models())
        except Exception as e:
            logging.error(
                f"Error checking for selected models: {str(e)}", exc_info=True)
            return False

    def run(self):
        """Start the application."""
        try:
            logging.info("Starting application main loop")

            # Only start hotkey listener if models are selected
            if self.check_selected_models():
                print("Dasi is running. Press Ctrl+Alt+Shift+I to activate.")
                self.hotkey_listener.start()
            else:
                logging.info("No models selected, showing settings window")
                self.show_settings()

            sys.exit(self.app.exec())
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}", exc_info=True)
            raise


def check_selected_models():
    """Check if any models are selected in the settings."""
    try:
        settings = Settings()
        return bool(settings.get_selected_models())
    except Exception as e:
        logging.error(
            f"Error checking for selected models: {str(e)}", exc_info=True)
        return False


def is_already_running():
    """Check if Dasi is already running by using the instance manager."""
    return DasiInstanceManager.is_running()


if __name__ == "__main__":
    try:
        if is_already_running():
            print("Another instance of Dasi is already running.")
            sys.exit(1)

        # Check if any models are selected
        if not check_selected_models():
            # Launch settings window if no models are selected
            logging.info("No models selected, launching settings window")
            app = QApplication(sys.argv)
            # Apply theme before creating window
            apply_theme(app, "dark")
            window = SettingsWindow()
            window.show()
            # Force a style refresh to ensure correct appearance
            window.style().unpolish(window)
            window.style().polish(window)
            # Also refresh child widgets
            for widget in window.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            sys.exit(app.exec())
        else:
            # Launch main application
            logging.info("Models selected, launching main application")
            app = Dasi()
            app.run()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
