import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
from video2audio.transcoder import Video2Audio
import threading
import shutil

UPLOAD_FOLDER = "uploads"
PROCESSING_FOLDER = "processing"
PROCESSED_FOLDER = "processed"

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, PROCESSING_FOLDER, PROCESSED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app = Flask(__name__)

# Lists to track files
upload_list = []
processing_list = []
processed_list = []

transcoder = Video2Audio(ffmpeg_bin="ffmpeg", ffprobe_bin="ffprobe")


# Add these globals
settings = {
    "codec": "mp3",
    "bitrate": None,
    "samplerate": None,
    "channels": None,
}


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/upload', methods=['POST'])
def upload():
    global upload_list
    files = request.files.getlist("files[]")
    saved_files = []
    for f in files:
        if f.filename:
            filepath = os.path.join(UPLOAD_FOLDER, f.filename)
            f.save(filepath)
            if f.filename not in upload_list:
                upload_list.append(f.filename)
            saved_files.append(f.filename)
    return jsonify({"files": upload_list})


@app.route('/upload_list')
def get_upload_list():
    return jsonify({"files": upload_list})


@app.route('/start_processing', methods=['POST'])
def start_processing():
    global upload_list, processing_list, processed_list
    selected_files = request.json.get("files", [])

    # Move selected files to processing list
    for f in selected_files:
        if f in upload_list:
            upload_list.remove(f)
            processing_list.append(f)

    # Start processing in a separate thread to avoid blocking
    thread = threading.Thread(target=process_files, args=(selected_files,))
    thread.start()

    return jsonify({"processing": processing_list})


@app.route('/settings', methods=['POST'])
def update_settings():
    """Update transcoding settings from UI"""
    global settings
    data = request.json
    settings["codec"] = data.get("codec", "mp3")
    settings["bitrate"] = data.get("bitrate") or None
    settings["samplerate"] = int(data["samplerate"]) if data.get("samplerate") else None
    settings["channels"] = int(data["channels"]) if data.get("channels") else None
    return jsonify({"status": "ok", "settings": settings})


def process_files(files):
    global processing_list, processed_list, settings
    for f in files:
        input_path = Path(UPLOAD_FOLDER).resolve() / f
        output_ext = settings["codec"]
        output_name = Path(f).stem + f".{output_ext}"
        output_path = Path(PROCESSED_FOLDER).resolve() / output_name

        try:
            print(f"🔄 Converting {input_path} → {output_path} with settings {settings}")
            transcoder.convert(
                input_file=input_path,
                output_file=output_path,
                codec=settings["codec"],
                bitrate=settings["bitrate"],
                samplerate=settings["samplerate"],
                channels=settings["channels"],
                auto=True,
            )
            print(f"✅ Done: {output_path}")
        except Exception as e:
            print(f"❌ Error converting {f}: {e}")
        finally:
            if f in processing_list:
                processing_list.remove(f)
            if output_path.exists():
                if output_name not in processed_list:
                    processed_list.append(output_name)



@app.route('/processed_files')
def get_processed_files():
    return jsonify({"files": processed_list})


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(PROCESSED_FOLDER, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
