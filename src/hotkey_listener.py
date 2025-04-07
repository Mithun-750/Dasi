from pynput import keyboard as pynput_keyboard
import pyautogui
import logging
import platform
from typing import Callable, Optional
from ui.settings import Settings

# Use different library for Windows which has better suppression capability
if platform.system() == 'Windows':
    try:
        import keyboard
    except ImportError:
        logging.warning("keyboard library not found, falling back to pynput")


class HotkeyListener:
    # Map of special keys to pynput format
    SPECIAL_KEY_MAP = {
        'Tab': '<tab>',
        'Space': '<space>',
        'Enter': '<enter>',
        'Esc': '<esc>',
        'Insert': '<insert>',
        'Delete': '<delete>',
        'Home': '<home>',
        'End': '<end>',
        'PgUp': '<page_up>',
        'PgDn': '<page_down>',
        'F1': '<f1>',
        'F2': '<f2>',
        'F3': '<f3>',
        'F4': '<f4>',
        'F5': '<f5>',
        'F6': '<f6>',
        'F7': '<f7>',
        'F8': '<f8>',
        'F9': '<f9>',
        'F10': '<f10>',
        'F11': '<f11>',
        'F12': '<f12>',
    }

    def __init__(self, callback: Callable[..., None]):
        """Initialize hotkey listener with a callback function.

        Args:
            callback: Function to call when hotkey is pressed. The function will be called 
                     with cursor position (x, y) coordinates.
        """
        self.callback = callback
        self.settings = Settings()
        self._running = False
        self.listener = None
        self.using_keyboard_lib = platform.system() == 'Windows' and 'keyboard' in globals()
        self._register_hotkey()

    def _register_hotkey(self):
        """Register the hotkey based on current settings."""
        # Get hotkey settings
        hotkey = self.settings.get('general', 'hotkey', default={
            'ctrl': True,
            'alt': True,
            'shift': True,
            'super': False,
            'fn': False,
            'key': 'I'
        })

        # Use the keyboard library on Windows for better event suppression
        if self.using_keyboard_lib:
            # Build hotkey string for keyboard library
            hotkey_parts = []
            if hotkey['ctrl']:
                hotkey_parts.append('ctrl')
            if hotkey['alt']:
                hotkey_parts.append('alt')
            if hotkey['shift']:
                hotkey_parts.append('shift')
            if hotkey['super']:
                hotkey_parts.append('windows')

            # Add the main key
            hotkey_parts.append(hotkey['key'].lower())

            # Create the hotkey string
            hotkey_str = '+'.join(hotkey_parts)
            logging.info(f"Registering Windows hotkey: {hotkey_str}")

            try:
                # First, unregister any previously registered hotkey
                try:
                    keyboard.remove_hotkey(hotkey_str)
                except:
                    pass

                # Register the hotkey with the keyboard library
                # The suppress parameter is key - it prevents the key from being sent
                keyboard.add_hotkey(
                    hotkey_str, self._handle_hotkey, suppress=True)
                logging.info("Windows hotkey registration successful")
                return
            except Exception as e:
                logging.error(f"Failed to register Windows hotkey: {str(e)}")
                # Fall back to pynput if keyboard library fails

        # Build hotkey string for pynput
        hotkey_parts = []
        if hotkey['ctrl']:
            hotkey_parts.append('<ctrl>')
        if hotkey['alt']:
            hotkey_parts.append('<alt>')
        if hotkey['shift']:
            hotkey_parts.append('<shift>')
        if hotkey['super']:
            hotkey_parts.append(
                '<cmd>' if pyautogui.platform == 'darwin' else '<windows>')

        # Handle the main key
        key = hotkey['key']
        if key in self.SPECIAL_KEY_MAP:
            hotkey_parts.append(self.SPECIAL_KEY_MAP[key])
        else:
            hotkey_parts.append(key.lower())

        hotkey_str = '+'.join(hotkey_parts)
        logging.info(f"Registering pynput hotkey: {hotkey_str}")

        try:
            self.listener = pynput_keyboard.GlobalHotKeys({
                hotkey_str: self._handle_hotkey
            })
            logging.info("Pynput hotkey registration successful")
        except Exception as e:
            logging.error(f"Failed to register pynput hotkey: {str(e)}")
            self.listener = None
            raise

    def _handle_hotkey(self):
        """Handle hotkey press by getting cursor position and calling callback."""
        try:
            logging.debug("Hotkey triggered")

            # Import modules needed for the function
            import time

            # On Windows, wait a little longer before showing the popup
            # This gives the system time to fully process the hotkey event
            if platform.system() == 'Windows':
                # Slightly longer delay for better focus handling
                time.sleep(0.15)

                try:
                    # Import clipboard related tools inline to avoid circular imports
                    from PyQt6.QtWidgets import QApplication
                    from PyQt6.QtGui import QClipboard

                    # Save selected text before it gets lost
                    if QApplication.instance():
                        clipboard = QApplication.clipboard()
                        # On Windows, try to preserve the selection
                        selected_text = clipboard.text(
                            QClipboard.Mode.Selection)
                        if selected_text:
                            # Keep a copy in the regular clipboard too in case Selection mode gets cleared
                            clipboard.setText(selected_text)
                            logging.debug(
                                f"Saved selection: {selected_text[:30]}...")
                except Exception as e:
                    logging.debug(
                        f"Non-critical clipboard handling error: {str(e)}")

            # Get cursor position for popup
            x, y = pyautogui.position()

            # Check what arguments the callback accepts
            import inspect
            sig = inspect.signature(self.callback)
            param_count = len(sig.parameters)

            if param_count == 0:
                # No parameters expected
                self.callback()
            elif param_count == 1:
                # One parameter expected - probably position as tuple
                self.callback((x, y))
            else:
                # Two or more parameters expected - pass x, y separately
                self.callback(x, y)

            logging.debug(f"Callback executed with position ({x}, {y})")
        except Exception as e:
            logging.error(f"Error handling hotkey: {str(e)}")

    def start(self):
        """Start listening for hotkeys.

        Returns:
            bool: True if successfully started, False otherwise.
        """
        if self._running:
            logging.info("Hotkey listener already running")
            return True

        if self.using_keyboard_lib:
            # For keyboard library, the hotkeys are already registered and active
            self._running = True
            logging.info("Windows keyboard listener running")
            return True

        if not self.listener:
            try:
                self._register_hotkey()
            except Exception as e:
                logging.error(f"Failed to register hotkey: {str(e)}")
                return False

        try:
            self.listener.start()
            self._running = True
            logging.info("Pynput hotkey listener started")
            return True
        except Exception as e:
            self._running = False
            logging.error(f"Failed to start hotkey listener: {str(e)}")
            return False

    def stop(self):
        """Stop listening for hotkeys.

        Returns:
            bool: True if successfully stopped, False otherwise.
        """
        if not self._running:
            logging.info("Hotkey listener not running")
            return True

        try:
            if self.using_keyboard_lib:
                # For keyboard library, we would unregister all hotkeys
                # This is simplified; you might want to store specific hotkey references
                keyboard.unhook_all()
                logging.info("Windows keyboard hotkeys unregistered")
            elif self.listener:
                self.listener.stop()

            self._running = False
            logging.info("Hotkey listener stopped")
            return True
        except Exception as e:
            logging.error(f"Failed to stop hotkey listener: {str(e)}")
            return False

    def is_running(self) -> bool:
        """Check if the hotkey listener is running."""
        return self._running

    def is_active(self) -> bool:
        """Check if the hotkey listener is active. Alias for is_running()."""
        return self.is_running()

    def reload_settings(self):
        """Reload hotkey settings and re-register the hotkey."""
        was_running = self._running

        # Stop current listener if running
        if was_running:
            self.stop()

        # Re-register with new settings
        try:
            self._register_hotkey()

            # Restart if it was running before
            if was_running:
                self.start()
            return True
        except Exception as e:
            logging.error(f"Failed to reload hotkey settings: {str(e)}")
            return False
