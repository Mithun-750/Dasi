import pyautogui
from hotkey_listener import HotkeyListener
from ui import CopilotUI
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
    
    def process_query(self, query: str):
        """Process user query and simulate typing the response."""
        response = self.llm_handler.get_response(query)
        if response:
            pyautogui.write(response)
    
    def run(self):
        """Start the application."""
        print("Linux Copilot is running. Press Ctrl+Alt+Shift+I to activate.")
        self.hotkey_listener.start()
        self.ui.run()

if __name__ == "__main__":
    app = LinuxCopilot()
    app.run()
