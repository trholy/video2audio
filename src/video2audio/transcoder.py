import subprocess
from pathlib import Path
from typing import Optional
import json


class Video2Audio:
    """
    Convert video files to audio with codec-aware automatic settings.
    """

    # Max recommended bitrate per codec
    CODEC_MAX_BITRATE = {
        "mp3": 320_000,  # 320 kbps
        "aac": 256_000,  # 256 kbps
        "wav": None,     # uncompressed
        "flac": None,    # lossless
    }

    # Default minimum bitrate per codec
    CODEC_DEFAULT_BITRATE = {
        "mp3": 192_000,  # 192 kbps
        "aac": 128_000,  # 128 kbps
        "wav": None,
        "flac": None,
    }

    def __init__(self, ffmpeg_bin: str = "ffmpeg.exe", ffprobe_bin: str = "ffprobe.exe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def _get_audio_info(self, input_file: str | Path) -> dict:
        """Get bitrate, sample rate, and channels from input using ffprobe."""
        input_file = str(input_file)
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate,sample_rate,channels",
            "-of", "json",
            input_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed:\n{result.stderr}")

        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]

        return {
            "bitrate": int(stream.get("bit_rate", 0)),  # 0 if unknown
            "samplerate": int(stream.get("sample_rate", 44100)),
            "channels": int(stream.get("channels", 2)),
        }

    def _determine_bitrate(self, codec: str, input_bitrate: int) -> Optional[str]:
        """Choose a smart bitrate for output."""
        max_bitrate = self.CODEC_MAX_BITRATE.get(codec)
        default_bitrate = self.CODEC_DEFAULT_BITRATE.get(codec)

        if input_bitrate <= 0:
            # fallback to codec default if input bitrate unknown
            return f"{default_bitrate // 1000}k" if default_bitrate else None

        # If input is too low, use codec default
        if default_bitrate and input_bitrate < default_bitrate:
            return f"{default_bitrate // 1000}k"

        # Cap input bitrate to codec maximum
        if max_bitrate:
            return f"{min(input_bitrate, max_bitrate) // 1000}k"

        # For lossless/uncompressed codecs
        return None

    def convert(
        self,
        input_file: str | Path,
        output_file: str | Path,
        codec: str = "mp3",
        bitrate: Optional[str] = None,
        samplerate: Optional[int] = None,
        channels: Optional[int] = None,
        loudnorm: bool = False,
        overwrite: bool = True,
        auto: bool = True,
    ) -> None:
        input_file = Path(input_file)
        output_file = Path(output_file)

        if auto:
            audio_info = self._get_audio_info(input_file)

            if bitrate is None:
                bitrate = self._determine_bitrate(codec, audio_info["bitrate"])
            if samplerate is None:
                samplerate = audio_info["samplerate"]
            if channels is None:
                channels = audio_info["channels"]

        cmd = [self.ffmpeg_bin]
        if overwrite:
            cmd.append("-y")
        cmd += ["-i", str(input_file), "-vn"]

        if loudnorm:
            cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
        if samplerate:
            cmd += ["-ar", str(samplerate)]
        if channels:
            cmd += ["-ac", str(channels)]
        if bitrate:
            cmd += ["-b:a", str(bitrate)]

        cmd += ["-f", codec, str(output_file)]

        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed with code {process.returncode}:\n{process.stderr}"
            )
