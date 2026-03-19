import json
import os
import platform
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from mutagen.mp3 import MP3

from base import BaseTab
from helpers import (
    sanitize_filename,
    is_phone_connected,
    find_borrowbox_path,
    get_phone_folders,
    get_files_with_sizes,
)

LOG_FILE = "pull_log.json"


class ImporterTab(BaseTab):
    def __init__(self, parent_frame, config_data, on_import_complete):
        super().__init__()
        self.config_data = config_data
        self.on_import_complete = on_import_complete
        self.importer_connected = False
        self._cancel_event = threading.Event()

        self.copied_folders = {}  # original_id -> renamed_title
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE) as f:
                data = json.load(f)
            for entry in data.get("imported", []):
                self.copied_folders[entry["original"]] = entry["renamed"]

        self._build(parent_frame)

    def _build(self, parent):
        # --- Phone status ---
        self.phone_status = ctk.CTkLabel(
            parent, text="📱 Checking...", text_color="yellow"
        )
        self.phone_status.pack(pady=(8, 2))

        # --- Path config ---
        frame_paths = ctk.CTkFrame(parent)
        frame_paths.pack(pady=6, fill="x", padx=20)
        frame_paths.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_paths, text="Source (Phone):").grid(
            row=0, column=0, sticky="w", padx=(10, 5), pady=(8, 4)
        )
        self.source_entry = ctk.CTkEntry(frame_paths)
        self.source_entry.grid(row=0, column=1, padx=5, pady=(8, 4), sticky="ew")
        self.source_entry.insert(0, self.config_data.get("importer_source", ""))
        ctk.CTkButton(
            frame_paths, text="Browse", width=80, command=self._browse_source
        ).grid(row=0, column=2, padx=(5, 10), pady=(8, 4))

        ctk.CTkLabel(frame_paths, text="Destination:").grid(
            row=1, column=0, sticky="w", padx=(10, 5), pady=(4, 8)
        )
        self.dest_entry = ctk.CTkEntry(frame_paths)
        self.dest_entry.grid(row=1, column=1, padx=5, pady=(4, 8), sticky="ew")
        self.dest_entry.insert(0, self.config_data.get("importer_destination", ""))
        ctk.CTkButton(
            frame_paths, text="Browse", width=80, command=self._browse_dest
        ).grid(row=1, column=2, padx=(5, 10), pady=(4, 8))

        # --- Buttons + already-imported count ---
        frame_buttons = ctk.CTkFrame(parent)
        frame_buttons.pack(pady=6, fill="x", padx=20)

        self.import_button = ctk.CTkButton(
            frame_buttons, text="Start Import", width=120, command=self._start_import
        )
        self.import_button.pack(side="left", padx=(10, 5), pady=8)

        self.cancel_button = ctk.CTkButton(
            frame_buttons,
            text="Cancel",
            width=80,
            fg_color="transparent",
            border_width=1,
            command=self._cancel_import,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=5, pady=8)

        self.cog_button = ctk.CTkButton(
            frame_buttons,
            text="⚙",
            width=36,
            fg_color="transparent",
            border_width=1,
            command=self._open_log_manager,
        )
        self.cog_button.pack(side="left", padx=(0, 5), pady=8)
        self._update_cog_visibility()

        self.already_imported_label = ctk.CTkLabel(
            frame_buttons, text=self._already_imported_text(), text_color="gray"
        )
        self.already_imported_label.pack(side="left", padx=15, pady=8)

        self.clear_log_button = ctk.CTkButton(
            frame_buttons,
            text="Clear Log",
            width=80,
            fg_color="transparent",
            border_width=1,
            command=lambda: self.clear_log_display(self.log_widget),
        )
        self.clear_log_button.pack(side="right", padx=(5, 10), pady=8)

        # --- Progress bar ---
        self.progress_bar = ctk.CTkProgressBar(
            parent, mode="determinate", progress_color="#4B4D50"
        )
        self.progress_bar.pack(pady=4, fill="x", padx=20)
        self.progress_bar.set(0)

        # --- Log ---
        self.log_widget = ctk.CTkTextbox(parent, state="disabled")
        self.log_widget.pack(pady=(4, 10), padx=20, expand=True, fill="both")

        self._log("Waiting for phone connection...")

    def _already_imported_text(self):
        n = len(self.copied_folders)
        return f"{n} book{'s' if n != 1 else ''} already imported" if n else ""

    def start_phone_polling(self, after_fn):
        self._after = after_fn
        self._check_phone_loop()

    def _check_phone_loop(self):
        connected = is_phone_connected()
        if connected and not self.importer_connected:
            self.phone_status.configure(text="📱 Connected ✅", text_color="green")
            self._log("📲 Phone detected.")
            self.importer_connected = True
            self._log("🔍 Searching for BorrowBox audiobooks folder...")
            threading.Thread(target=self._find_and_set_source_path, daemon=True).start()
        elif not connected and self.importer_connected:
            self.phone_status.configure(text="📱 Disconnected ❌", text_color="red")
            self._log("🔌 Phone disconnected.")
            self.importer_connected = False
        self._after(3000, self._check_phone_loop)

    def _find_and_set_source_path(self):
        path = find_borrowbox_path()
        if path:
            self._after(0, self._log, f"✅ Found path: {path}")
            self._after(0, self.source_entry.delete, 0, tk.END)
            self._after(0, self.source_entry.insert, 0, path)
        else:
            self._after(0, self._log, "⚠️ Could not automatically find BorrowBox path.")

    def _browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, path)
            self.config_data["importer_source"] = path
            self.save_config()

    def _browse_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, path)
            self.config_data["importer_destination"] = path
            self.save_config()

    def _start_import(self):
        if not self.importer_connected:
            self._log("❌ Connect your phone first.")
            return
        self.config_data["importer_source"] = self.source_entry.get()
        self.config_data["importer_destination"] = self.dest_entry.get()
        self.save_config()
        self._cancel_event.clear()
        self.progress_line_index = None
        self.import_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        threading.Thread(target=self._import_thread, daemon=True).start()

    def _cancel_import(self):
        self._cancel_event.set()
        self._log("⏹ Cancelling after current file...")
        self.cancel_button.configure(state="disabled")

    def _finish_import(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", progress_color="#4B4D50")
        self.progress_bar.set(0)
        self.import_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.already_imported_label.configure(text=self._already_imported_text())

    def _update_cog_visibility(self):
        if self.copied_folders:
            self.cog_button.configure(state="normal", border_width=1, text="⚙")
        else:
            self.cog_button.configure(state="disabled", border_width=0, text="")

    def _open_log_manager(self):
        popup = ctk.CTkToplevel()
        popup.title("Import Log")
        popup.geometry("600x400")
        popup.grab_set()

        ctk.CTkLabel(
            popup,
            text="Imported Books",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(12, 4))
        ctk.CTkLabel(
            popup,
            text="Remove an entry to allow it to be re-imported.",
            text_color="gray",
        ).pack(pady=(0, 8))

        header = ctk.CTkFrame(popup, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            header, text="Original ID", width=140, anchor="w", text_color="gray"
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(header, text="Imported As", anchor="w", text_color="gray").pack(
            side="left", expand=True, fill="x"
        )

        scroll = ctk.CTkScrollableFrame(popup)
        scroll.pack(expand=True, fill="both", padx=16, pady=(0, 12))

        def build_rows():
            for widget in scroll.winfo_children():
                widget.destroy()
            for original, renamed in list(self.copied_folders.items()):
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=original, width=140, anchor="w").pack(
                    side="left", padx=(0, 8)
                )
                ctk.CTkLabel(row, text=renamed, anchor="w").pack(
                    side="left", expand=True, fill="x"
                )
                ctk.CTkButton(
                    row,
                    text="✕",
                    width=30,
                    height=26,
                    fg_color="transparent",
                    border_width=1,
                    text_color=("gray40", "gray60"),
                    command=lambda o=original: remove_entry(o),
                ).pack(side="right", padx=(8, 0))

        def remove_entry(original):
            del self.copied_folders[original]
            self._save_log()
            self.already_imported_label.configure(text=self._already_imported_text())
            self._update_cog_visibility()
            build_rows()

        build_rows()

    def _save_log(self):
        data = {
            "imported": [
                {"original": orig, "renamed": renamed}
                for orig, renamed in self.copied_folders.items()
            ]
        }
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def _import_thread(self):
        source_path = self.source_entry.get()
        dest_path = self.dest_entry.get()
        os.makedirs(dest_path, exist_ok=True)

        def log(msg, is_progress=False):
            self._after(0, self.log_to_widget, self.log_widget, msg, is_progress)

        all_folders = get_phone_folders(source_path)
        folders_to_import = [f for f in all_folders if f not in self.copied_folders]

        if not folders_to_import:
            log("✅ No new books to import.")
            self._after(0, lambda: (self.progress_bar.set(1), self._finish_import()))
            return

        log(f"📚 Found {len(folders_to_import)} new book(s) to import.")
        log("🔍 Calculating total size...")

        all_files_to_pull = []
        total_size = 0
        for folder in folders_to_import:
            for file_info in get_files_with_sizes(
                os.path.join(source_path, folder), log
            ):
                all_files_to_pull.append(file_info)
                total_size += file_info["size"]

        if total_size == 0:
            log("🤷 No files found in new folders.")
            self._after(0, self._finish_import)
            return

        log(
            f"Total import: {len(all_files_to_pull)} files ({total_size / (1024*1024):.2f} MB)"
        )

        # Switch to determinate now that we know the total
        self._after(
            0,
            lambda: (
                self.progress_bar.stop(),
                self.progress_bar.configure(
                    mode="determinate", progress_color=["#2CC985", "#2FA572"]
                ),
                self.progress_bar.set(0),
            ),
        )

        pulled_size = 0
        log("⚙️ Importing... 0%", is_progress=True)
        for file_info in all_files_to_pull:
            if self._cancel_event.is_set():
                log("⏹ Import cancelled.")
                self._after(0, self._finish_import)
                return

            remote_path = file_info["path"]
            local_path = os.path.join(
                dest_path, os.path.relpath(remote_path, source_path)
            )
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            try:
                subprocess.run(
                    ["adb", "pull", remote_path, local_path],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                log(
                    f"❌ Failed to pull {os.path.basename(remote_path)}: {e.stderr.decode()}"
                )
                continue
            pulled_size += file_info["size"]
            percent = pulled_size / total_size
            self._after(0, lambda p=percent: self.progress_bar.set(p))
            log(f"⚙️ Importing... {int(percent*100)}%", is_progress=True)

        log("⚙️ Post-processing downloaded folders...")
        for folder in folders_to_import:
            renamed = self._process_local_folder(os.path.join(dest_path, folder), log)
            self.copied_folders[folder] = renamed or folder
            self._save_log()

        self._after(0, self._update_cog_visibility)

        log("✅ Import complete.")
        threading.Thread(target=self._play_complete_sound, daemon=True).start()
        self._after(
            0,
            lambda: (
                self.progress_bar.set(1),
                self._finish_import(),
            ),
        )

    def _play_complete_sound(self):
        try:
            system = platform.system()
            if system == "Darwin":
                os.system("afplay /System/Library/Sounds/Glass.aiff")
            elif system == "Windows":
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _process_local_folder(self, folder_path, log_callback):
        first_audio_album = None

        for f in os.listdir(folder_path):
            if f.lower().endswith(".mp3package"):
                new_name = f[:-11] + ".mp3"
                os.rename(
                    os.path.join(folder_path, f), os.path.join(folder_path, new_name)
                )
                log_callback(f"🎵 Renamed {f} → {new_name}")

        for f in os.listdir(folder_path):
            if f.lower().endswith(".mp3"):
                name_clean = f[:-4].rstrip(".")
                if name_clean.isdigit():
                    new_name = f"Chapter {name_clean}.mp3"
                    os.rename(
                        os.path.join(folder_path, f),
                        os.path.join(folder_path, new_name),
                    )

        for f in os.listdir(folder_path):
            if f.lower().endswith(".mp3") and first_audio_album is None:
                try:
                    audio = MP3(os.path.join(folder_path, f))
                    if "TALB" in audio:
                        first_audio_album = sanitize_filename(audio["TALB"].text[0])
                except Exception:
                    pass

        if first_audio_album:
            new_folder_path = os.path.join(
                os.path.dirname(folder_path), first_audio_album
            )
            if new_folder_path != folder_path:
                if os.path.exists(new_folder_path):
                    shutil.rmtree(new_folder_path)
                    log_callback(f"⚠️ Removed existing folder: {first_audio_album}")
                shutil.move(folder_path, new_folder_path)
                log_callback(f"📚 Renamed folder to → {first_audio_album}")
            return first_audio_album

        return os.path.basename(folder_path)

    def _log(self, msg):
        self.log_to_widget(self.log_widget, msg)
