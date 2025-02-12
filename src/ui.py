import customtkinter as ctk
from typing import Callable, Tuple


class CopilotUI:
    def __init__(self, process_query: Callable[[str], None]):
        """Initialize UI with a callback for processing queries."""
        self.process_query = process_query

        # Configure theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Create root window (hidden)
        self.root = ctk.CTk()
        self.root.withdraw()

        # Window dimensions
        self.WINDOW_WIDTH = 320
        self.WINDOW_HEIGHT = 180
        self.SCREEN_PADDING = 20

        # Create a temporary window to measure window manager offsets
        temp = ctk.CTkToplevel(self.root)
        temp.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+100+100")
        temp.update_idletasks()
        self.offset_x = temp.winfo_x() - 100
        self.offset_y = temp.winfo_y() - 100
        temp.destroy()

    def _adjust_position(self, x: int, y: int) -> Tuple[int, int]:
        """Adjust window position to ensure it stays within screen boundaries."""

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Add slight offset to avoid cursor overlap
        x += 10
        y += 10

        # Ensure window stays within screen bounds
        if x + self.WINDOW_WIDTH > screen_width - self.SCREEN_PADDING:
            x = screen_width - self.WINDOW_WIDTH - self.SCREEN_PADDING
        if y + self.WINDOW_HEIGHT > screen_height - self.SCREEN_PADDING:
            y = screen_height - self.WINDOW_HEIGHT - self.SCREEN_PADDING

        # Prevent negative positions
        x = max(self.SCREEN_PADDING, x)
        y = max(self.SCREEN_PADDING, y)

        return x, y

    def show_popup(self, x: int, y: int):
        """Show popup window at specified coordinates."""

        # Adjust position for screen boundaries
        x, y = self._adjust_position(x, y)

        # Calculate window position (centered on cursor)
        final_x = x - self.WINDOW_WIDTH // 2
        final_y = y + 20  # Show slightly below cursor

        # Create popup window (hidden)
        popup = ctk.CTkToplevel(self.root)
        popup.withdraw()

        # Configure window
        popup.title("")
        popup.attributes('-topmost', True)

        # Use splash window type instead of overrideredirect on Linux
        try:
            popup.wm_attributes('-type', 'splash')
        except:
            # Fallback to overrideredirect on other platforms
            popup.overrideredirect(True)

        # Ensure window can receive focus
        popup.focus_force()
        popup.grab_set()

        # Set initial geometry
        popup.wm_geometry(
            f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{final_x}+{final_y}")

        # Create main frame with shadow effect
        frame = ctk.CTkFrame(popup, corner_radius=12)
        frame.pack(padx=2, pady=2, fill="both", expand=True)

        # Create header with drag functionality
        header = ctk.CTkFrame(frame, corner_radius=12)
        header.pack(padx=2, pady=2, fill="x")

        title = ctk.CTkLabel(header, text="Linux Copilot",
                             font=("Arial", 14, "bold"))
        title.pack(side="left", padx=10, pady=5)

        # Make window draggable by header
        self._make_draggable(popup, header)

        # Create input frame
        input_frame = ctk.CTkFrame(frame)
        input_frame.pack(padx=10, pady=(5, 10), fill="both", expand=True)

        # Create input field
        self.input_field = ctk.CTkEntry(
            input_frame, placeholder_text="Type your query...")
        self.input_field.pack(fill="both", expand=True, padx=5, pady=5)

        # Bind events
        self.input_field.bind('<Return>', lambda e: self._handle_submit(popup))
        self.input_field.bind('<Escape>', lambda e: self._close_popup(popup))
        popup.bind('<FocusIn>', lambda e: self._ensure_input_focus(popup))
        popup.bind('<Button-1>', lambda e: self._ensure_input_focus(popup))

        # Update window
        popup.update_idletasks()

        # Force position using wm_geometry
        popup.wm_geometry(
            f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{final_x}+{final_y}")

        # Show window with a small delay
        self.root.after(10, lambda: self._show_popup_with_position(
            popup, final_x, final_y))

        return popup

    def _show_popup_with_position(self, popup, x, y):
        """Helper to show popup and ensure correct position."""
        # Show window
        popup.deiconify()
        popup.lift()

        # Force position again after showing
        popup.wm_geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{x}+{y}")
        popup.update_idletasks()

        # Verify position
        actual_x = popup.winfo_x()
        actual_y = popup.winfo_y()

        if actual_x != x or actual_y != y:
            popup.wm_geometry(
                f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{x}+{y}")
            popup.update()

        # Focus the input field
        self.input_field.focus_force()

    def _handle_submit(self, popup):
        """Handle submit button click."""
        query = self.input_field.get()
        if query.strip():
            self._close_popup(popup)  # Close window before processing
            self.process_query(query)

    def _close_popup(self, popup):
        """Safely close the popup window."""
        popup.grab_release()
        popup.destroy()

    def _ensure_input_focus(self, popup):
        """Ensure input field has focus."""
        self.input_field.focus_set()

    def _ensure_input_focus(self, popup):
        """Ensure input field has focus."""
        self.input_field.focus_set()

    def _make_draggable(self, window, widget):
        """Make a window draggable by clicking and dragging on a widget."""
        def start_drag(event):
            self._drag_data = {'x': event.x, 'y': event.y}

        def stop_drag(event):
            self._drag_data = {}

        def do_drag(event):
            if hasattr(self, '_drag_data'):
                # Calculate new position
                dx = event.x - self._drag_data['x']
                dy = event.y - self._drag_data['y']
                x = window.winfo_x() + dx
                y = window.winfo_y() + dy
                window.geometry(f"+{x}+{y}")

        widget.bind('<Button-1>', start_drag)
        widget.bind('<ButtonRelease-1>', stop_drag)
        widget.bind('<B1-Motion>', do_drag)

    def run(self):
        """Start the UI event loop."""
        self.root.mainloop()
