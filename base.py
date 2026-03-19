import json
import tkinter as tk
import customtkinter as ctk

CONFIG_FILE = "config.json"


class BaseTab:
    """Shared helpers for importer and converter tabs."""

    def __init__(self):
        self.progress_line_index = None

    def save_config(self):
        """Write current config_data to disk."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config_data, f, indent=4)
        except OSError:
            pass

    def log_to_widget(self, widget, message, is_progress_update=False):
        widget.configure(state="normal")
        if is_progress_update:
            if self.progress_line_index is None:
                widget.insert("end", "\n" + message)
                widget.see("end")
                self.progress_line_index = int(widget.index("end-1c").split(".")[0])
            else:
                line = self.progress_line_index
                widget.delete(f"{line}.0", f"{line}.end")
                widget.insert(f"{line}.0", message)
        else:
            widget.insert("end", "\n" + message)
            widget.see("end")
        widget.configure(state="disabled")

    def clear_log_display(self, widget):
        widget.configure(state="normal")
        widget.delete(1.0, tk.END)
        widget.configure(state="disabled")
