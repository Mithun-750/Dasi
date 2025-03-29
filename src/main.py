import os
import sys
import logging
import pyautogui
import pyperclip
from pathlib import Path
from hotkey_listener import HotkeyListener
from ui import CopilotUI
from llm_handler import LLMHandler
from ui.settings import Settings, SettingsWindow
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt
from typing import Optional, Callable
# Import constants
from constants import DEFAULT_CHAT_PROMPT, DEFAULT_COMPOSE_PROMPT
# Import instance manager
from instance_manager import DasiInstanceManager
# Import theme system
from ui.assets import apply_theme


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


class Dasi:
    def __init__(self):
        """Initialize Dasi."""
        try:
            logging.info("Starting Dasi application")

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

            # Initialize system tray
            logging.info("Setting up system tray")
            self.tray = None  # Initialize to None first
            self.setup_tray()

            # Initialize LLM handler
            logging.info("Initializing LLM handler")
            self.llm_handler = LLMHandler()

            # Make default prompts available to LLMHandler
            # This is a workaround to avoid modifying llm_handler.py
            import llm_handler
            if not hasattr(llm_handler, 'DEFAULT_CHAT_PROMPT'):
                llm_handler.DEFAULT_CHAT_PROMPT = DEFAULT_CHAT_PROMPT
            if not hasattr(llm_handler, 'DEFAULT_COMPOSE_PROMPT'):
                llm_handler.DEFAULT_COMPOSE_PROMPT = DEFAULT_COMPOSE_PROMPT

            # Initialize UI
            logging.info("Initializing UI")
            self.ui = CopilotUI(self.process_query)

            # Initialize hotkey listener but don't start it yet
            logging.info("Initializing hotkey listener")
            self.hotkey_listener = HotkeyListener(self.ui.show_popup)

            # Initialize settings window (but don't show it)
            self.settings_window = None

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

    def process_query(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None) -> str:
        """Process a query and return the response."""
        try:
            # Handle special commands
            if query.startswith('!'):
                if query.startswith('!clear_session:'):
                    session_id = query.split(':', 1)[1]
                    self.llm_handler.clear_chat_history(session_id)
                    return ""
                elif query.startswith('!session:'):
                    # Extract session ID and actual query
                    _, rest = query.split(':', 1)
                    session_id, actual_query = rest.split('|', 1)
                    return self.llm_handler.get_response(actual_query, callback, model, session_id)
                elif query.startswith('!paste:'):
                    # Handle paste command
                    text = query[6:]  # Remove !paste: prefix
                    # Ensure no leading colon in the text
                    if text.startswith(':'):
                        text = text[1:].lstrip()
                    pyperclip.copy(text)  # Copy to clipboard
                    pyautogui.hotkey('ctrl', 'v')  # Simulate paste
                    return ""
                elif query.startswith('!type:'):
                    # Handle type command
                    text = query[6:]  # Remove !type: prefix
                    # Ensure no leading colon in the text
                    if text.startswith(':'):
                        text = text[1:].lstrip()
                    pyautogui.write(text, interval=0.01)
                    return ""
                else:
                    return "Unknown command"

            # Process normal query
            response = self.llm_handler.get_response(query, callback, model)

            # Check for quota errors and enhance the error message
            if "⚠️ Error:" in response and ("quota" in response.lower() or "rate limit" in response.lower() or "resourceexhausted" in response.lower()):
                # Get the current provider
                provider = "unknown"
                if self.llm_handler.current_provider:
                    provider = self.llm_handler.current_provider

                # Add troubleshooting information based on provider
                if provider == "google":
                    troubleshooting = """
                    
To resolve this issue:
1. Check your Google AI Studio quota at https://aistudio.google.com/app/apikey
2. Consider upgrading to a paid plan if you're on the free tier
3. If on a paid plan, check your billing information
4. Try again later when your quota resets"""
                elif provider in ["openai", "custom_openai"]:
                    troubleshooting = """
                    
To resolve this issue:
1. Check your usage at https://platform.openai.com/usage
2. Add funds to your account if needed
3. Consider upgrading your rate limits
4. Try again later"""
                else:
                    troubleshooting = """
                    
To resolve this issue:
1. Check your usage and billing information
2. Consider upgrading your plan
3. Try again later when your quota resets"""

                # Get alternative models
                alternative_models = []
                try:
                    selected_models = self.settings.get_selected_models()
                    current_model = model
                    if not current_model and self.llm_handler.llm:
                        if hasattr(self.llm_handler.llm, 'model'):
                            current_model = self.llm_handler.llm.model
                        elif hasattr(self.llm_handler.llm, 'model_name'):
                            current_model = self.llm_handler.llm.model_name

                    # Filter out models from the current provider
                    if current_model and provider:
                        alternative_models = [
                            m['name'] for m in selected_models
                            if m['provider'] != provider
                        ][:3]  # Limit to 3 alternatives
                except Exception as e:
                    logging.error(
                        f"Error getting alternative models: {str(e)}", exc_info=True)

                # Add alternative models to the message if available
                alternatives_text = ""
                if alternative_models:
                    alternatives_text = "\n\nTry these alternative models:\n- " + \
                        "\n- ".join(alternative_models)

                # Enhance the error message
                return f"{response}{troubleshooting}{alternatives_text}"

            return response

        except Exception as e:
            logging.error(f"Error processing query: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

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
