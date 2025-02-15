from pynput import keyboard
import pyautogui
import logging
from typing import Callable
from ui.settings import Settings


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

    def __init__(self, callback: Callable[[], None]):
        """Initialize hotkey listener with a callback function."""
        self.callback = callback
        self.settings = Settings()

        # Get hotkey settings
        hotkey = self.settings.get('general', 'hotkey', default={
            'ctrl': True,
            'alt': True,
            'shift': True,
            'super': False,
            'fn': False,
            'key': 'I'
        })

        # Build hotkey string
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
        # Note: Fn key is not directly supported by pynput, so we skip it

        # Handle the main key
        key = hotkey['key']
        if key in self.SPECIAL_KEY_MAP:
            hotkey_parts.append(self.SPECIAL_KEY_MAP[key])
        else:
            hotkey_parts.append(key.lower())

        hotkey_str = '+'.join(hotkey_parts)
        logging.info(f"Registering hotkey: {hotkey_str}")

        try:
            self.listener = keyboard.GlobalHotKeys({
                hotkey_str: self._handle_hotkey
            })
            logging.info("Hotkey registration successful")
        except Exception as e:
            logging.error(f"Failed to register hotkey: {str(e)}")
            raise

    def _handle_hotkey(self):
        """Handle hotkey press by getting cursor position and calling callback."""
        try:
            logging.debug("Hotkey triggered")
            x, y = pyautogui.position()
            self.callback(x, y)
            logging.debug(f"Callback executed with position ({x}, {y})")
        except Exception as e:
            logging.error(f"Error handling hotkey: {str(e)}")

    def start(self):
        """Start listening for hotkeys."""
        try:
            self.listener.start()
            logging.info("Hotkey listener started")
        except Exception as e:
            logging.error(f"Failed to start hotkey listener: {str(e)}")
            raise

    def stop(self):
        """Stop listening for hotkeys."""
        try:
            self.listener.stop()
            logging.info("Hotkey listener stopped")
        except Exception as e:
            logging.error(f"Failed to stop hotkey listener: {str(e)}")
            raise
