from PyQt6.QtCore import QObject, pyqtSignal
import logging


class ToolCallHandler(QObject):
    """
    Handles tool call requests, confirmation, and execution.
    Emits signals to the UI for confirmation and receives user responses.
    """
    # Signal emitted when a tool call requires user confirmation
    # e.g., {"tool": "web_search", "args": {...}}
    tool_call_requested = pyqtSignal(dict)
    # Signal emitted when a tool call is completed (success or failure)
    # e.g., {"tool": "web_search", "result": ...}
    tool_call_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_tool_call = None
        self.awaiting_confirmation = False
        logging.info("ToolCallHandler initialized")

    def request_tool_call(self, tool_name, args):
        """Request a tool call and emit a signal for UI confirmation."""
        logging.info(f"Tool call requested: {tool_name} with args: {args}")
        self.pending_tool_call = {"tool": tool_name, "args": args}
        self.awaiting_confirmation = True
        # Emit signal to UI - this should trigger the confirmation panel to be shown
        logging.debug("Emitting tool_call_requested signal")
        self.tool_call_requested.emit(self.pending_tool_call)

    def handle_user_response(self, accepted: bool):
        """Handle the user's response to the tool call confirmation."""
        if not self.awaiting_confirmation or not self.pending_tool_call:
            logging.warning("No pending tool call to confirm.")
            return

        tool_name = self.pending_tool_call.get("tool", "unknown")
        if accepted:
            logging.info(f"User accepted tool call: {tool_name}")
            self.execute_tool_call(self.pending_tool_call)
        else:
            logging.info(f"User rejected tool call: {tool_name}")
            self.tool_call_completed.emit({
                "tool": self.pending_tool_call["tool"],
                "result": "rejected"
            })
        self.awaiting_confirmation = False
        self.pending_tool_call = None

    def execute_tool_call(self, tool_call):
        """Execute the tool call. For now, only web_search is supported."""
        tool = tool_call["tool"]
        args = tool_call["args"]
        logging.info(f"Executing tool call: {tool} with args: {args}")

        # For now, only web_search is implemented
        if tool == "web_search":
            # This is where you would call the actual web search handler
            # For now, just emit a dummy result
            query = args.get('query', '')
            logging.info(f"Performing web search for: '{query}'")
            result = {"status": "success", "data": f"Searched for {query}"}
            logging.info(f"Web search completed, emitting result")
            self.tool_call_completed.emit({"tool": tool, "result": result})
        else:
            logging.error(f"Unknown tool: {tool}")
            self.tool_call_completed.emit(
                {"tool": tool, "result": "error: unknown tool"})
