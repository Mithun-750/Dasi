from pynput import keyboard
import pyautogui
from typing import Callable


class HotkeyListener:
    def __init__(self, callback: Callable[[], None]):
        """Initialize hotkey listener with a callback function."""
        self.callback = callback
        self.listener = keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+<shift>+i': self._handle_hotkey
        })

    def _handle_hotkey(self):
        """Handle hotkey press by getting cursor position and calling callback."""
        x, y = pyautogui.position()
        # Pass raw coordinates to UI for positioning
        self.callback(x, y)

    def start(self):
        """Start listening for hotkeys."""
        self.listener.start()

    def stop(self):
        """Stop listening for hotkeys."""
        self.listener.stop()
