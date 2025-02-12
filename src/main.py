import pyautogui
from hotkey_listener import HotkeyListener
from ui.ui import CopilotUI
from llm_handler import LLMHandler

class LinuxCopilot:
    def __init__(self):
        """Initialize the Linux Copilot application."""
        # Initialize LLM handler
        self.llm_handler = LLMHandler()
        
        # Initialize UI
        self.ui = CopilotUI(self.process_query)
        
        # Initialize hotkey listener
        self.hotkey_listener = HotkeyListener(self.ui.show_popup)
    
    def process_query(self, query: str) -> str:
        """Process query and return response. If query starts with '!', it's a response to be typed."""
        if query.startswith('!'):
            # This is a response to be typed
            response = query[1:]  # Remove the ! prefix
            pyautogui.write(response, interval=0.01)
            return response
        else:
            # This is a query to be processed
            response = self.llm_handler.get_response(query)
            return response if response else "Error: Failed to get response"
    
    def run(self):
        """Start the application."""
        print("Linux Copilot is running. Press Ctrl+Alt+Shift+I to activate.")
        self.hotkey_listener.start()
        self.ui.run()

if __name__ == "__main__":
    app = LinuxCopilot()
    app.run()
