import os
import re
import shutil
import subprocess

INVALID_CHARS = r'[\/:*?"<>|]'


def sanitize_filename(name):
    return re.sub(INVALID_CHARS, "_", name)


def escape_ffmetadata(value):
    """Escape special characters for ffmpeg metadata values."""
    return (
        value.replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace(";", "\\;")
        .replace("#", "\\#")
        .replace("\n", "\\n")
    )


def check_ffmpeg_tools():
    if not shutil.which("ffmpeg"):
        return False, "ffmpeg is not installed or not in your PATH."
    if not shutil.which("ffprobe"):
        return False, "ffprobe is not installed or not in your PATH."
    return True, "ffmpeg and ffprobe found."


def is_phone_connected():
    try:
        output = subprocess.check_output(["adb", "devices"]).decode()
        return any("device" in line for line in output.splitlines()[1:])
    except Exception:
        return False


def find_borrowbox_path():
    base_path = "/sdcard/Android/Data/com.bolindadigital.BorrowBoxLibrary/files"
    try:
        result = subprocess.check_output(
            ["adb", "shell", f"ls -1 {base_path}"]
        ).decode()
        hash_dir = result.strip().splitlines()[0]
        return os.path.join(base_path, hash_dir, "audiobooks/") if hash_dir else None
    except (subprocess.CalledProcessError, IndexError, FileNotFoundError, OSError):
        return None


def get_phone_folders(path):
    try:
        escaped = path.replace("'", "'\\''")
        result = subprocess.check_output(
            ["adb", "shell", f"find '{escaped}' -mindepth 1 -maxdepth 1 -type d"]
        ).decode()
        return [
            os.path.basename(line.strip())
            for line in result.splitlines()
            if line.strip()
        ]
    except subprocess.CalledProcessError:
        return []


def get_files_with_sizes(path, log_callback):
    escaped = path.replace("'", "'\\''")
    try:
        result = subprocess.check_output(
            ["adb", "shell", f"find '{escaped}' -type f -exec stat -c '%s %n' {{}} +"]
        ).decode()
        files = []
        for line in result.splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].isdigit():
                files.append({"path": parts[1], "size": int(parts[0])})
        return files
    except subprocess.CalledProcessError as e:
        log_callback(f"❌ Error getting file list: {e}")
        return []
