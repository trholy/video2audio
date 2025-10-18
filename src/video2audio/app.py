import os
import re
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging
import urllib.parse

from flask import Flask, render_template, request, jsonify, send_file
from video2audio.transcoder import Video2Audio


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    """Sanitize filenames for saving, processing, and downloading."""
    name, ext = os.path.splitext(filename)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "file"
    return f"{name}{ext.lower()}"


# -------------------------------------------------------------------
# Codec Defaults and Validation
# -------------------------------------------------------------------

CODEC_DEFAULTS = {
    "mp3": {"bitrate": "192k", "samplerate": 44100,
            "channels": 2, "lossless": False},
    "aac": {"bitrate": "256k", "samplerate": 44100,
            "channels": 2, "lossless": False},
    "wav": {"bitrate": None, "samplerate": 44100,
            "channels": 2, "lossless": True},
    "flac": {"bitrate": None, "samplerate": 44100,
             "channels": 2, "lossless": True}
}

VALID_SAMPLE_RATES = {
    "mp3": [32000, 44100, 48000],
    "aac": [44100, 48000],
    "wav": [44100, 48000, 88200, 96000, 192000],
    "flac": [44100, 48000, 88200, 96000, 192000],
}


def validate_settings(
        codec: str,
        bitrate: Optional[str],
        samplerate: Optional[int],
        channels: Optional[int]
) -> Dict:
    """Validate and adjust settings based on codec rules."""
    codec = codec.lower()
    if codec not in CODEC_DEFAULTS:
        codec = "mp3"

    defaults = CODEC_DEFAULTS[codec]
    lossless = defaults["lossless"]

    # Bitrate
    if lossless:
        bitrate = None
    elif bitrate:
        try:
            kbps = int(bitrate.replace("k", ""))
            if codec == "mp3":
                kbps = min(max(kbps, 32), 320)
            elif codec == "aac":
                kbps = min(max(kbps, 64), 256)
            bitrate = f"{kbps}k"
        except Exception:
            bitrate = defaults["bitrate"]
    else:
        bitrate = defaults["bitrate"]

    # Sample rate
    if samplerate not in VALID_SAMPLE_RATES.get(codec, []):
        samplerate = defaults["samplerate"]

    # Channels
    if codec in ["mp3", "aac"]:
        if channels not in [1, 2]:
            channels = 2
    else:
        if not channels:
            channels = defaults["channels"]

    return {
        "codec": codec,
        "bitrate": bitrate,
        "samplerate": samplerate,
        "channels": channels,
        "lossless": lossless,
    }


# -------------------------------------------------------------------
# Dataclasses
# -------------------------------------------------------------------

@dataclass
class TranscodeSettings:
    """Holds user-selected transcoding options."""
    codec: str = "mp3"
    bitrate: Optional[str] = None
    samplerate: Optional[int] = None
    channels: Optional[int] = None
    lossless: bool = False


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
        for f in filenames:
            if f in self.upload_list:
                self.upload_list.remove(f)
                self.processing_list.append(f)

        thread = threading.Thread(target=self._process_files, args=(filenames,))
        thread.start()

    def _process_files(self, files: List[str]) -> None:
        for f in files:
            input_path = UPLOAD_FOLDER.resolve() / f
            output_ext = self.settings.codec
            output_name = clean_filename(f"{Path(f).stem}.{output_ext}")
            output_path = PROCESSED_FOLDER.resolve() / output_name

            try:
                logger.info(
                    f"🔄 Converting {input_path} → {output_path}"
                    f" with {self.settings}")

                # Skip bitrate if lossless
                bitrate = None if self.settings.lossless else self.settings.bitrate

                self.transcoder.convert(
                    input_file=input_path,
                    output_file=output_path,
                    codec=self.settings.codec,
                    bitrate=bitrate,
                    samplerate=self.settings.samplerate,
                    channels=self.settings.channels,
                    auto=True,
                )
                logger.info(f"✅ Done: {output_path}")
            except Exception as e:
                logger.error(f"❌ Error converting {f}: {e}")
            finally:
                if f in self.processing_list:
                    self.processing_list.remove(f)
                if output_path.exists() and output_name not in self.processed_list:
                    self.processed_list.append(output_name)

    # -------------------------------
    # Settings Management
    # -------------------------------
    def update_settings(self, data: Dict) -> None:
        validated = validate_settings(
            codec=data.get("codec", "mp3"),
            bitrate=data.get("bitrate"),
            samplerate=int(data["samplerate"]) if data.get("samplerate") else None,
            channels=int(data["channels"]) if data.get("channels") else None,
        )
        self.settings = TranscodeSettings(**validated)
        logger.info(f"⚙️ Updated transcoding settings: {self.settings}")


# -------------------------------------------------------------------
# Flask App
# -------------------------------------------------------------------

app = Flask(__name__)
manager = TranscodeManager(
    Video2Audio(ffmpeg_bin="ffmpeg", ffprobe_bin="ffprobe"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files[]")
    manager.save_uploads(files)
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

@app.route("/download/<path:filename>")
def download_file(filename):
    """
    Securely serve processed audio files for download.
    Returns a valid file or a JSON error message if not found or inaccessible.
    """
    safe_name = urllib.parse.unquote(filename)
    file_path = (PROCESSED_FOLDER / safe_name).resolve()

    # Safety: ensure file stays inside processed folder
    if not str(file_path).startswith(str(PROCESSED_FOLDER.resolve())):
        logging.warning(
            f"⚠️ Security check failed: {file_path} outside processed folder")
        return jsonify({"error": "Invalid file path"}), 400

    if not file_path.exists():
        logging.error(f"❌ File not found: {file_path}")
        return jsonify({"error": f"File not found: {safe_name}"}), 404

    try:
        logging.info(f"⬇️ Downloading: {safe_name}")
        return send_file(
            file_path,
            as_attachment=True,
            download_name=safe_name)
    except Exception as e:
        logging.exception(f"❌ Failed to send {safe_name}: {e}")
        return jsonify({"error": f"Failed to download {safe_name}"}), 500

@app.route('/clear_uploads', methods=['POST'])
def clear_uploads():
    """Delete selected uploaded files (not processed) from disk and list."""
    files_to_delete = request.json.get("files", [])
    deleted_files = []

    for f in files_to_delete:
        file_path = UPLOAD_FOLDER / f
        if file_path.exists():
            try:
                file_path.unlink()
                deleted_files.append(f)
                if f in manager.upload_list:
                    manager.upload_list.remove(f)
            except Exception as e:
                logger.error(f"❌ Failed to delete {f}: {e}")

    return jsonify(
        {"status": "ok",
         "deleted": deleted_files,
         "files": manager.upload_list
         })


@app.route('/clear_processed', methods=['POST'])
def clear_processed():
    """Delete all processed files from disk and update manager list."""
    deleted_files = []

    for f in manager.processed_list:
        file_path = PROCESSED_FOLDER / f
        if file_path.exists():
            try:
                file_path.unlink()
                deleted_files.append(f)
            except Exception as e:
                logger.error(f"❌ Failed to delete {f}: {e}")

    # Update manager processed list
    manager.processed_list = [
        f for f in manager.processed_list if f not in deleted_files]

    return jsonify(
        {"status": "ok",
         "deleted": deleted_files,
         "files": manager.processed_list
         })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
