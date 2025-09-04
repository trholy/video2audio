import os
import re
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional

from flask import Flask, render_template, request, jsonify, send_from_directory
from video2audio.transcoder import Video2Audio


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

UPLOAD_FOLDER = Path("uploads")
PROCESSING_FOLDER = Path("processing")
PROCESSED_FOLDER = Path("processed")

for folder in [UPLOAD_FOLDER, PROCESSING_FOLDER, PROCESSED_FOLDER]:
    folder.mkdir(exist_ok=True)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def clean_filename(filename: str) -> str:
    """
    Sanitize filenames for saving, processing, and downloading.
    Keeps alphanumeric, dot, dash, underscore. Replaces others with '_'.
    """
    name, ext = os.path.splitext(filename)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "file"
    return f"{name}{ext.lower()}"


@dataclass
class TranscodeSettings:
    """Holds user-selected transcoding options."""
    codec: str = "mp3"
    bitrate: Optional[str] = None
    samplerate: Optional[int] = None
    channels: Optional[int] = None


# -------------------------------------------------------------------
# Manager Class
# -------------------------------------------------------------------

class TranscodeManager:
    """Handles upload tracking, processing, and transcoding logic."""

    def __init__(self, transcoder: Video2Audio):
        self.transcoder = transcoder
        self.upload_list: List[str] = []
        self.processing_list: List[str] = []
        self.processed_list: List[str] = []
        self.settings = TranscodeSettings()

    # -------------------------------
    # Upload Management
    # -------------------------------
    def save_uploads(self, files) -> List[str]:
        """Save uploaded files and update tracking list."""
        saved_files = []
        for f in files:
            if f.filename:
                safe_name = clean_filename(f.filename)
                filepath = UPLOAD_FOLDER / safe_name
                f.save(filepath)
                if safe_name not in self.upload_list:
                    self.upload_list.append(safe_name)
                saved_files.append(safe_name)
        return saved_files

    # -------------------------------
    # Processing Management
    # -------------------------------
    def start_processing(self, filenames: List[str]) -> None:
        """Start processing selected files in a background thread."""
        for f in filenames:
            if f in self.upload_list:
                self.upload_list.remove(f)
                self.processing_list.append(f)

        thread = threading.Thread(target=self._process_files, args=(filenames,))
        thread.start()

    def _process_files(self, files: List[str]) -> None:
        """Convert uploaded videos to audio in background."""
        for f in files:
            input_path = UPLOAD_FOLDER.resolve() / f
            output_ext = self.settings.codec
            output_name = clean_filename(f"{Path(f).stem}.{output_ext}")
            output_path = PROCESSED_FOLDER.resolve() / output_name

            try:
                print(f"🔄 Converting {input_path} → {output_path} with {self.settings}")
                self.transcoder.convert(
                    input_file=input_path,
                    output_file=output_path,
                    codec=self.settings.codec,
                    bitrate=self.settings.bitrate,
                    samplerate=self.settings.samplerate,
                    channels=self.settings.channels,
                    auto=True,
                )
                print(f"✅ Done: {output_path}")
            except Exception as e:
                print(f"❌ Error converting {f}: {e}")
            finally:
                if f in self.processing_list:
                    self.processing_list.remove(f)
                if output_path.exists() and output_name not in self.processed_list:
                    self.processed_list.append(output_name)

    # -------------------------------
    # Settings Management
    # -------------------------------
    def update_settings(self, data: Dict) -> None:
        """Update transcoding settings from request JSON."""
        self.settings.codec = data.get("codec", "mp3")
        self.settings.bitrate = data.get("bitrate") or None
        self.settings.samplerate = (
            int(data["samplerate"]) if data.get("samplerate") else None
        )
        self.settings.channels = (
            int(data["channels"]) if data.get("channels") else None
        )


# -------------------------------------------------------------------
# Flask App
# -------------------------------------------------------------------

# Determine project root relative to this file
app = Flask(__name__)
manager = TranscodeManager(Video2Audio(ffmpeg_bin="ffmpeg", ffprobe_bin="ffprobe"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files[]")
    saved_files = manager.save_uploads(files)
    return jsonify({"files": manager.upload_list})


@app.route("/upload_list")
def get_upload_list():
    return jsonify({"files": manager.upload_list})


@app.route("/start_processing", methods=["POST"])
def start_processing():
    selected_files = request.json.get("files", [])
    manager.start_processing(selected_files)
    return jsonify({"processing": manager.processing_list})


@app.route("/settings", methods=["POST"])
def update_settings():
    manager.update_settings(request.json)
    return jsonify({"status": "ok", "settings": vars(manager.settings)})


@app.route("/processed_files")
def get_processed_files():
    return jsonify({"files": manager.processed_list})


@app.route("/download/<filename>")
def download_file(filename):
    safe_name = clean_filename(filename)
    return send_from_directory(PROCESSED_FOLDER, safe_name, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
