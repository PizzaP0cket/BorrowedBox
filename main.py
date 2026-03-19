import os
import json
import customtkinter as ctk

from importer import ImporterTab
from converter import ConverterTab

CONFIG_FILE = "config.json"

_BORROWEDBOX_DIR = os.path.expanduser("~/Documents/BorrowedBox/Library")
_LIBRARY_DIR = os.path.join(_BORROWEDBOX_DIR, "Bookshelf")

DEFAULT_CONFIG = {
    "importer_source": "",
    "importer_destination": _BORROWEDBOX_DIR,
    "converter_source": _BORROWEDBOX_DIR,
    "converter_output": _LIBRARY_DIR,
}


def _load_config():
    """Load config from disk, fill in missing keys, and always save."""
    first_run = not os.path.exists(CONFIG_FILE)

    if not first_run:
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            config = {}
            first_run = True
    else:
        config = {}

    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)

    # Only create default directories on first run
    if first_run:
        os.makedirs(config["importer_destination"], exist_ok=True)
        os.makedirs(config["converter_source"], exist_ok=True)
        os.makedirs(config["converter_output"], exist_ok=True)

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except OSError:
        pass

    return config


class BorrowedBoxApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BorrowedBox")
        self.geometry("850x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.config_data = _load_config()

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)

        importer_frame = self.tab_view.add("Importer")
        converter_frame = self.tab_view.add("Converter")

        self.converter_tab = ConverterTab(converter_frame, self.config_data)
        self.importer_tab = ImporterTab(
            importer_frame,
            self.config_data,
            on_import_complete=self._on_import_complete,
        )

        self.after(1000, lambda: self.importer_tab.start_phone_polling(self.after))

    def _on_import_complete(self):
        self.converter_tab.refresh_folders()
        self.tab_view.set("Converter")


if __name__ == "__main__":
    app = BorrowedBoxApp()
    app.mainloop()
