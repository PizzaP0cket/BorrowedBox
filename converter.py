import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import customtkinter as ctk
from tkinter import filedialog
from mutagen.mp3 import MP3

from base import BaseTab
from helpers import check_ffmpeg_tools, escape_ffmetadata


class ConverterTab(BaseTab):
    def __init__(self, parent_frame, config_data):
        super().__init__()
        self.config_data = config_data
        self.converter_checkboxes = {}
        self._cancel_event = threading.Event()
        self._current_proc = None

        self._build(parent_frame)

    def _build(self, parent):
        # --- Source path ---
        frame_source = ctk.CTkFrame(parent)
        frame_source.pack(fill="x", padx=10, pady=(10, 0))
        frame_source.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_source, text="Source folder:").grid(
            row=0, column=0, sticky="w", padx=(10, 5), pady=8
        )
        self.source_entry = ctk.CTkEntry(frame_source)
        self.source_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        self.source_entry.insert(0, self.config_data.get("converter_source", ""))
        ctk.CTkButton(
            frame_source, text="Browse", width=80, command=self._browse_source
        ).grid(row=0, column=2, padx=(5, 10), pady=8)

        # --- Controls ---
        controls_frame = ctk.CTkFrame(parent)
        controls_frame.pack(fill="x", padx=10, pady=(6, 0))

        ctk.CTkButton(
            controls_frame, text="Refresh Folders", command=self.refresh_folders
        ).pack(side="left", padx=(10, 5), pady=8)
        ctk.CTkButton(controls_frame, text="Select All", command=self._select_all).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(
            controls_frame, text="Deselect All", command=self._deselect_all
        ).pack(side="left", padx=5, pady=8)

        self.cleanup_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            controls_frame,
            text="Delete MP3 folder after conversion",
            variable=self.cleanup_var,
        ).pack(side="left", padx=15, pady=8)

        # --- Folder list ---
        # Scrollable grid container with auto-hide scrollbar
        self.folder_list_frame = ctk.CTkScrollableFrame(
            parent, label_text="Select books to convert"
        )
        self.folder_list_frame.pack(expand=True, fill="both", padx=10, pady=5)

        # --- Output path ---
        frame_output = ctk.CTkFrame(parent)
        frame_output.pack(fill="x", padx=10, pady=(0, 6))
        frame_output.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_output, text="Output folder:").grid(
            row=0, column=0, sticky="w", padx=(10, 5), pady=8
        )
        self.output_entry = ctk.CTkEntry(frame_output)
        self.output_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        _default_output = self.config_data.get("converter_output", "")
        self.output_entry.insert(0, _default_output)
        ctk.CTkButton(
            frame_output, text="Browse", width=80, command=self._browse_output
        ).grid(row=0, column=2, padx=(5, 10), pady=8)

        # --- Bottom: buttons + progress ---
        bottom_frame = ctk.CTkFrame(parent)
        bottom_frame.pack(fill="x", padx=10, pady=(0, 0))

        self.convert_button = ctk.CTkButton(
            bottom_frame,
            text="Start Conversion",
            width=140,
            command=self._start_conversion,
        )
        self.convert_button.pack(side="left", padx=(10, 5), pady=8)

        self.cancel_button = ctk.CTkButton(
            bottom_frame,
            text="Cancel",
            width=80,
            fg_color="transparent",
            border_width=1,
            command=self._cancel_conversion,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=5, pady=8)

        self.book_label = ctk.CTkLabel(bottom_frame, text="", text_color="gray")
        self.book_label.pack(side="left", padx=12, pady=8)

        self.progress_bar = ctk.CTkProgressBar(bottom_frame, progress_color="#4B4D50")
        self.progress_bar.pack(side="left", expand=True, fill="x", padx=(5, 10), pady=8)
        self._set_progress(0)

        # --- Log ---
        self.log_widget = ctk.CTkTextbox(parent, height=160, state="disabled")
        self.log_widget.pack(expand=True, fill="both", padx=10, pady=(0, 10))

        self.refresh_folders()

    def _browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, path)
            self.config_data["converter_source"] = path
            self.save_config()
            self.refresh_folders()

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)
            self.config_data["converter_output"] = path
            self.save_config()

    def refresh_folders(self):
        for widget in self.folder_list_frame.winfo_children():
            widget.destroy()
        self.converter_checkboxes = {}

        dest_path = self.source_entry.get()
        if not dest_path:
            ctk.CTkLabel(
                self.folder_list_frame, text="No source folder set.", text_color="gray"
            ).pack(pady=20)
            return

        try:
            subfolders = sorted(
                f.name
                for f in os.scandir(dest_path)
                if f.is_dir() and f.name.lower() != "bookshelf"
            )
            if not subfolders:
                ctk.CTkLabel(
                    self.folder_list_frame,
                    text="No folders found. Run the Importer tab first.",
                    text_color="gray",
                ).pack(pady=20)
                return

            COLUMNS = 3
            MAX_CHARS = 30
            for idx, folder_name in enumerate(subfolders):
                row, col = divmod(idx, COLUMNS)
                var = ctk.StringVar(value="off")
                label = (
                    folder_name
                    if len(folder_name) <= MAX_CHARS
                    else folder_name[: MAX_CHARS - 1] + "…"
                )
                ctk.CTkCheckBox(
                    self.folder_list_frame,
                    text=label,
                    variable=var,
                    onvalue=folder_name,
                    offvalue="off",
                ).grid(row=row, column=col, sticky="w", padx=12, pady=4)
                self.converter_checkboxes[folder_name] = var

            for col in range(COLUMNS):
                self.folder_list_frame.grid_columnconfigure(col, weight=0, minsize=220)
        except Exception as e:
            self.log_to_widget(
                self.log_widget, f"Error reading destination folder: {e}"
            )

    def _select_all(self):
        for folder_name, var in self.converter_checkboxes.items():
            var.set(folder_name)

    def _deselect_all(self):
        for var in self.converter_checkboxes.values():
            var.set("off")

    def _start_conversion(self):
        selected = [
            var.get()
            for var in self.converter_checkboxes.values()
            if var.get() != "off"
        ]
        if not selected:
            self.log_to_widget(self.log_widget, "No folders selected for conversion.")
            return

        ffmpeg_ok, msg = check_ffmpeg_tools()
        if not ffmpeg_ok:
            self.log_to_widget(self.log_widget, f"❌ {msg}")
            return

        self.config_data["converter_source"] = self.source_entry.get()
        self.config_data["converter_output"] = self.output_entry.get()
        self.save_config()
        self._cancel_event.clear()
        self.convert_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self._set_progress(0)
        threading.Thread(
            target=self._conversion_thread, args=(selected,), daemon=True
        ).start()

    def _cancel_conversion(self):
        self._cancel_event.set()
        if self._current_proc and self._current_proc.poll() is None:
            self._current_proc.terminate()
        self.log_to_widget(self.log_widget, "⏹ Cancelling after current step...")
        self.cancel_button.configure(state="disabled")

    def _set_progress(self, value):
        self.progress_bar.set(value)
        if value <= 0:
            self.progress_bar.configure(progress_color="#4B4D50")
        else:
            self.progress_bar.configure(progress_color=["#2CC985", "#2FA572"])

    def _finish_conversion(self, cancelled=False):
        self.convert_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.book_label.configure(text="")
        if cancelled:
            self._set_progress(0)

    def _conversion_thread(self, folders_to_convert):
        dest_path = self.source_entry.get()
        library_root = self.output_entry.get() or os.path.join(dest_path, "Library")

        total = len(folders_to_convert)

        for i, folder_name in enumerate(folders_to_convert):
            if self._cancel_event.is_set():
                self.log_to_widget(self.log_widget, "⏹ Conversion cancelled.")
                self._finish_conversion(cancelled=True)
                return

            self.book_label.configure(text=f"Book {i+1} of {total}")
            input_dir = os.path.join(dest_path, folder_name)
            output_file = os.path.join(library_root, f"{folder_name}.m4b")
            m4b_name = f"{folder_name}.m4b"

            # Check if already converted — in Library root or any series subfolder
            already_exists = any(
                f == m4b_name for _, _, files in os.walk(library_root) for f in files
            )
            if already_exists:
                self.log_to_widget(
                    self.log_widget,
                    f"\n⏭ Skipping '{folder_name}' — already converted.",
                )
                self._set_progress((i + 1) / total)
                continue

            self.log_to_widget(
                self.log_widget, f"\n--- Converting: {folder_name} ({i+1}/{total}) ---"
            )

            slice_start = i / total
            slice_end = (i + 1) / total

            def set_progress(fraction, _s=slice_start, _e=slice_end):
                self._set_progress(_s + fraction * (_e - _s))

            if self._run_single_conversion(input_dir, output_file, set_progress):
                self._set_progress(slice_end)
                self.log_to_widget(
                    self.log_widget,
                    f"✅ Successfully created: {os.path.basename(output_file)}",
                )
                self._sort_book(output_file, library_root)
                if self.cleanup_var.get():
                    try:
                        shutil.rmtree(input_dir)
                        self.log_to_widget(
                            self.log_widget, f"🧹 Deleted MP3 folder: {folder_name}"
                        )
                    except Exception as e:
                        self.log_to_widget(
                            self.log_widget,
                            f"⚠️ Could not delete folder '{folder_name}': {e}",
                        )
            else:
                if self._cancel_event.is_set():
                    self.log_to_widget(self.log_widget, "⏹ Conversion cancelled.")
                    self._finish_conversion(cancelled=True)
                    return
                self.log_to_widget(
                    self.log_widget, f"❌ Failed to convert: {folder_name}"
                )

        self.log_to_widget(self.log_widget, "\n--- All conversions finished. ---")
        threading.Thread(target=self._play_complete_sound, daemon=True).start()
        self.refresh_folders()
        self._finish_conversion()

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

    def _sort_book(self, m4b_path, library_root):
        """Sort a .m4b into a series subfolder within library_root, or leave it at the root."""
        filename = os.path.basename(m4b_path)

        if "_ " not in filename:
            dest = os.path.join(library_root, filename)
        else:
            _, right = filename.split("_ ", 1)
            series_name = re.sub(r"\s+-?\d+(\.\d+)?$", "", os.path.splitext(right)[0])
            series_dir = os.path.join(library_root, series_name)
            os.makedirs(series_dir, exist_ok=True)  # ← always create if missing
            dest = os.path.join(series_dir, filename)  # ← always sort into it

        try:
            if os.path.abspath(m4b_path) != os.path.abspath(dest):
                shutil.move(m4b_path, dest)
                self.log_to_widget(
                    self.log_widget,
                    f"📂 Sorted into: {os.path.relpath(dest, library_root)}",
                )
        except Exception as e:
            self.log_to_widget(self.log_widget, f"⚠️ Could not sort '{filename}': {e}")

    def _run_single_conversion(self, input_dir, output_file, set_progress=None):
        # Step weights as fractions of 1.0: step1=5%, step2=85%, step3=2%, step4=8%
        STEP_STARTS = [0.0, 0.05, 0.90, 0.92]
        STEP_ENDS = [0.05, 0.90, 0.92, 1.00]

        def report(step, inner=1.0):
            """Push progress for a given step (0-indexed). inner=0..1 for step 2."""
            if set_progress:
                set_progress(
                    STEP_STARTS[step] + inner * (STEP_ENDS[step] - STEP_STARTS[step])
                )

        def log(msg):
            self.log_to_widget(self.log_widget, msg)

        def natural_sort_key(s):
            return [
                int(t) if t.isdigit() else t.lower() for t in re.split("([0-9]+)", s)
            ]

        all_files = sorted(
            [
                os.path.join(input_dir, f)
                for f in os.listdir(input_dir)
                if f.lower().endswith(".mp3")
            ],
            key=lambda f: natural_sort_key(os.path.basename(f)),
        )

        if not all_files:
            log(f"No MP3 files found in {os.path.basename(input_dir)}.")
            return False

        with tempfile.TemporaryDirectory() as temp_dir:
            # --- Step 1: Read metadata ---
            log("Step 1/4: Reading metadata and file info...")
            mp3_data = []
            title, artist, cover_art_path = os.path.basename(input_dir), None, None

            try:
                first_audio = MP3(all_files[0])
                if hasattr(first_audio, "tags") and first_audio.tags:
                    tags = first_audio.tags
                    title = (
                        str(tags.get("TALB", [os.path.basename(input_dir)])[0])
                        if "TALB" in tags
                        else title
                    )
                    artist = str(tags.get("TPE1", [""])[0]) if "TPE1" in tags else None

                    for tag in tags.values():
                        if tag.FrameID == "APIC":
                            mime = tag.mime.lower()
                            ext = (
                                "jpg"
                                if ("jpeg" in mime or "jpg" in mime)
                                else ("png" if "png" in mime else mime.split("/")[-1])
                            )
                            cover_art_path = os.path.join(temp_dir, f"cover.{ext}")
                            with open(cover_art_path, "wb") as img:
                                img.write(tag.data)
                            log(f"Found and extracted cover art ({ext.upper()}).")
                            break
                    else:
                        log("⚠️ No cover art found in the first MP3.")
                else:
                    log("⚠️ No ID3 tags found in the first MP3.")
            except Exception as e:
                log(f"⚠️ Could not read metadata from first file: {e}")

            log(f"Title: {title}" + (f", Artist: {artist}" if artist else ""))

            for file_path in all_files:
                try:
                    audio = MP3(file_path)
                    mp3_data.append(
                        {
                            "path": file_path,
                            "duration": int(audio.info.length * 1000),
                            "title": os.path.splitext(os.path.basename(file_path))[0],
                        }
                    )
                except Exception as e:
                    log(f"⚠️ Skipping {os.path.basename(file_path)}: {e}")

            if not mp3_data:
                log("❌ No valid MP3 files could be processed.")
                return False

            report(0)  # step 1 done

            # --- Step 2: Concatenate with live progress ---
            log("Step 2/4: Encoding audio...")
            self.progress_line_index = None
            filelist_path = os.path.join(temp_dir, "filelist.txt")
            with open(filelist_path, "w", encoding="utf-8") as f:
                for data in mp3_data:
                    f.write(
                        f"file '{os.path.abspath(data['path']).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n"
                    )

            concatenated_audio = os.path.join(temp_dir, "combined.m4a")
            total_duration_s = sum(d["duration"] for d in mp3_data) / 1000.0

            self._current_proc = subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    filelist_path,
                    "-map",
                    "0:a",
                    "-ac",
                    "1",
                    "-c:a",
                    "aac_at" if platform.system() == "Darwin" else "aac",
                    "-b:a",
                    "128k",
                    "-ar",
                    "44100",
                    concatenated_audio,
                ],
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            stderr_lines = []
            step2_start = time.monotonic()
            time_pattern = re.compile(r"time=(\d+):(\d+):([\d.]+)")

            for line in self._current_proc.stderr:
                if self._cancel_event.is_set():
                    self._current_proc.terminate()
                    break
                stderr_lines.append(line)
                m = time_pattern.search(line)
                if m and total_duration_s > 0:
                    encoded_s = (
                        int(m.group(1)) * 3600
                        + int(m.group(2)) * 60
                        + float(m.group(3))
                    )
                    pct = min(encoded_s / total_duration_s, 1.0)
                    report(1, pct)
                    elapsed = time.monotonic() - step2_start
                    if pct > 0:
                        eta_s = int((elapsed / pct) * (1.0 - pct))
                        eta_str = (
                            f"{eta_s // 60}m {eta_s % 60}s"
                            if eta_s >= 60
                            else f"{eta_s}s"
                        )
                        progress_msg = f"Step 2/4: Encoding... {int(pct * 100)}%  (~{eta_str} remaining)"
                    else:
                        progress_msg = "Step 2/4: Encoding... 0%"
                    self.log_to_widget(
                        self.log_widget, progress_msg, is_progress_update=True
                    )

            self._current_proc.wait()
            if self._cancel_event.is_set():
                return False
            if self._current_proc.returncode != 0:
                log(f"❌ Error encoding audio: {''.join(stderr_lines)}")
                return False
            self.log_to_widget(
                self.log_widget,
                "Step 2/4: Encoding... done ✅",
                is_progress_update=True,
            )

            if self._cancel_event.is_set():
                return False

            # --- Step 3: Chapter metadata ---
            log("Step 3/4: Generating chapters...")
            metadata_path = os.path.join(temp_dir, "chapters.txt")
            with open(metadata_path, "w", encoding="utf-8") as f:
                f.write(";FFMETADATA1\n")
                if title:
                    f.write(f"title={escape_ffmetadata(title)}\n")
                if artist:
                    f.write(f"artist={escape_ffmetadata(artist)}\n")
                start_time = 0
                for data in mp3_data:
                    end_time = start_time + data["duration"]
                    f.write(
                        f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={start_time}\nEND={end_time}\ntitle={escape_ffmetadata(data['title'])}\n"
                    )
                    start_time = end_time

            report(2)  # step 3 done

            # --- Step 4: Final M4B ---
            log("Step 4/4: Creating M4B with chapters and cover art...")
            final_cmd = ["ffmpeg", "-y", "-i", concatenated_audio]
            cover_index = None
            if cover_art_path and os.path.exists(cover_art_path):
                final_cmd.extend(["-i", cover_art_path])
                cover_index = 1
            final_cmd.extend(["-i", metadata_path, "-map", "0:a"])
            if cover_index is not None:
                final_cmd.extend(["-map", f"{cover_index}:v"])
            final_cmd.extend(
                ["-map_metadata", str(2 if cover_index else 1), "-c:a", "copy"]
            )
            if cover_index is not None:
                final_cmd.extend(["-c:v", "copy", "-disposition:v:0", "attached_pic"])
            final_cmd.append(os.path.abspath(output_file))

            self._current_proc = subprocess.Popen(
                final_cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            _, stderr_out = self._current_proc.communicate()
            if self._cancel_event.is_set():
                return False
            if self._current_proc.returncode != 0:
                log(f"❌ Error creating M4B: {stderr_out}")
                return False

        return True
