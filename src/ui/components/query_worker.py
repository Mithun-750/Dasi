from PyQt6.QtCore import QThread
from typing import Callable, Optional


class QueryWorker(QThread):
    """Worker thread for processing queries."""

    def __init__(self, process_fn: Callable[[str], str],
                 query: str, signals, model: Optional[str] = None,
                 session_id: Optional[str] = None):
        super().__init__()
        self.process_fn = process_fn
        self.query = query
        self.signals = signals
        self.model = model
        self.session_id = session_id
        self.is_stopped = False

    def run(self):
        """Process the query and emit result."""
        try:
            # Pass a callback to handle streaming updates
            def stream_callback(partial_response: str):
                if not self.is_stopped:
                    self.signals.process_response.emit(partial_response)

            # Add session ID to query if available
            if self.session_id:
                self.query = f"!session:{self.session_id}|{self.query}"

            result = self.process_fn(self.query, stream_callback, self.model)
            if not self.is_stopped and not result:
                self.signals.process_error.emit("No response received")
            # Signal completion
            if not self.is_stopped:
                self.signals.process_response.emit("<COMPLETE>")
        except Exception as e:
            if not self.is_stopped:
                self.signals.process_error.emit(str(e))
        finally:
            self.quit()

    def stop(self):
        """Stop the worker cleanly."""
        self.is_stopped = True 