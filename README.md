# BorrowedBox

Software for pulling BorrowBox audiobooks from your Android phone and converting them into `.m4b` audiobook files with embeded metadata (title, author, etc.), and cover art.

> **Note:**
> This project is intended for educational purposes only. Please respect copyright laws and the terms of service.

![Last Updated](https://img.shields.io/github/last-commit/PizzaP0cket/BorrowedBox?label=Last%20Updated)
![Repo Stars](https://img.shields.io/github/stars/PizzaP0cket/BorrowedBox?style=social)
![Python](https://img.shields.io/badge/Python-3%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Cross--Platform-009688?logo=windows&logoColor=white)
![License](https://img.shields.io/github/license/aviiciii/tokybook?color=orange)

## What it does

BorrowedBox has two tabs:

**Importer** — connects to your Android phone over ADB, finds your BorrowBox audiobooks, and copies them to your computer. It automatically renames files, reads the album tag from the MP3s to name the folder correctly, and keeps a log so books already imported are never pulled again.

**Converter** — takes the imported MP3 folders and converts them into a single `.m4b` file per book, complete with metadata (title, artist), and embedded cover art. Finished books are automatically sorted into series subfolders inside your Library.

---

## Requirements

### Python dependencies

```bash
pip install customtkinter mutagen
```

### External tools

| Tool | Purpose | Download |
|------|---------|----------|
| [ffmpeg](https://ffmpeg.org/about.html) | Audio encoding and M4B creation | https://ffmpeg.org/download.html |
| [ADB (Android Debug Bridge)](https://developer.android.com/tools/adb) | Communicating with your Android phone | https://developer.android.com/tools/releases/platform-tools |


Both must be available in your system `PATH`.

### Android phone setup

Enable **USB Debugging** on your phone:
1. Go to **Settings → About Phone**
2. Tap **Build Number** seven times to unlock Developer Options
3. Go to **Settings → Developer Options** and enable **USB Debugging**
4. Connect your phone via USB and accept the ADB authorisation prompt

---

## Installation

```bash
git clone https://github.com/PizzaP0cket/BorrowedBox.git
cd borrowedbox
pip install customtkinter mutagen
python main.py
```

---

## Usage

### Importer tab

1. Connect your Android phone via USB
2. The app will detect your phone and automatically find your BorrowBox audiobooks folder
3. Set your destination folder (defaults to `~/Documents/BorrowedBox/Library`)
4. Click **Start Import**

Books already imported are tracked in `pull_log.json`. To re-import a book, click the **⚙** button and remove it from the log.

### Converter tab

1. Select the folders you want to convert (or use **Select All**)
2. Set your output folder (defaults to `~/Documents/BorrowedBox/Library/Bookshelf`)
3. Click **Start Conversion**

Each book is converted to `.m4b` with:
- Title and artist metadata from the MP3 tags
- Embedded cover art (extracted from the first MP3)
- Automatic sorting into series subfolders (e.g. a file named `A Song of Ice and Fire_ Game of Thrones.m4b` is sorted into the `Game of Thrones` folder)

Optionally check **Delete MP3 folder after conversion** to clean up the source files once a book is done.

---

## Platform notes

| Feature | macOS | Windows | Linux |
|---------|-------|---------|-------|
| AAC encoding | `aac_at` (Apple hardware encoder) | `aac` (ffmpeg software) | `aac` (ffmpeg software) |
| Completion sound | `Glass.aiff` (afplay) | System beep (winsound) | Silent |

---

## Troubleshooting

**Phone not detected** — make sure USB Debugging is enabled and you have accepted the ADB authorisation on your phone. Run `adb devices` in a terminal to verify.

**ffmpeg not found** — ensure ffmpeg is installed and on your PATH. On macOS: `brew install ffmpeg`. On Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

**BorrowBox folder not found automatically** — you can set the source path manually using the Browse button. The path is typically inside `/sdcard/Android/Data/com.bolindadigital.BorrowBoxLibrary/files/`.

**Book skipped during conversion** — a `.m4b` with the same name already exists in your Library. Delete or rename it if you want to re-convert.
