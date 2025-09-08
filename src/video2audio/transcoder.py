import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AudioInfo:
    """Structured representation of audio stream information."""
    bitrate: int
    samplerate: int
    channels: int


class CodecConfig:
    """Holds codec-specific bitrate settings."""

    MAX_BITRATE: Dict[str, Optional[int]] = {
        "mp3": 320_000,  # 320 kbps
        "aac": 256_000,  # 256 kbps
        "wav": None,     # uncompressed
        "flac": None,    # lossless
    }

    DEFAULT_BITRATE: Dict[str, Optional[int]] = {
        "mp3": 192_000,  # 192 kbps
        "aac": 128_000,  # 128 kbps
        "wav": None,
        "flac": None,
    }


class Video2Audio:
    """
    Convert video files to audio with codec-aware automatic settings.
    Provides smart defaults for bitrate, sample rate, and channels.
    """

    def __init__(
            self,
            ffmpeg_bin: str = "ffmpeg",
            ffprobe_bin: str = "ffprobe"
    ):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    @staticmethod
    def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess:
        """Run a subprocess command and return the result."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed ({' '.join(cmd)}):\n{result.stderr}"
            )
        return result

    def _get_audio_info(self, input_file: str | Path) -> AudioInfo:
        """
        Extract bitrate, sample rate, and channels using ffprobe.

        Args:
            input_file: Path to the media file.

        Returns:
            AudioInfo object with parsed stream details.
        """
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate,sample_rate,channels",
            "-of", "json",
            str(input_file),
        ]

        result = self._run_subprocess(cmd)
        info = json.loads(result.stdout)
        stream: Dict[str, Any] = info.get("streams", [{}])[0]

        return AudioInfo(
            bitrate=int(stream.get("bit_rate", 0)),
            samplerate=int(stream.get("sample_rate", 44100)),
            channels=int(stream.get("channels", 2)),
        )

    @staticmethod
    def _determine_bitrate(codec: str, input_bitrate: int) -> Optional[str]:
        """
        Determine an appropriate output bitrate based on codec and input.

        Args:
            codec: Target codec (e.g., "mp3", "aac").
            input_bitrate: Input file bitrate in bits per second.

        Returns:
            Bitrate string (e.g., "192k") or None for lossless/uncompressed codecs.
        """
        max_bitrate = CodecConfig.MAX_BITRATE.get(codec)
        default_bitrate = CodecConfig.DEFAULT_BITRATE.get(codec)

        if input_bitrate <= 0:
            return f"{default_bitrate // 1000}k" if default_bitrate else None

        if default_bitrate and input_bitrate < default_bitrate:
            return f"{default_bitrate // 1000}k"

        if max_bitrate:
            return f"{min(input_bitrate, max_bitrate) // 1000}k"

        return None  # For lossless/uncompressed

    def _build_ffmpeg_command(
        self,
        input_file: Path,
        output_file: Path,
        codec: str,
        bitrate: Optional[str],
        samplerate: Optional[int],
        channels: Optional[int],
        loudnorm: bool,
        overwrite: bool,
    ) -> list[str]:
        """Construct the ffmpeg command for audio conversion."""
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
            cmd += ["-b:a", bitrate]

        cmd += ["-f", codec, str(output_file)]
        return cmd

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
        """
        Convert a video file to audio with codec-aware defaults.

        Args:
            input_file: Path to the source video.
            output_file: Path to the generated audio.
            codec: Output audio codec.
            bitrate: Optional manual bitrate (e.g., "128k").
            samplerate: Optional sample rate in Hz.
            channels: Optional number of audio channels.
            loudnorm: Whether to apply EBU R128 loudness normalization.
            overwrite: Overwrite existing files if True.
            auto: Auto-detect settings from input if True.
        """
        input_file = Path(input_file)
        output_file = Path(output_file)

        if auto:
            audio_info = self._get_audio_info(input_file)
            bitrate = bitrate or self._determine_bitrate(codec, audio_info.bitrate)
            samplerate = samplerate or audio_info.samplerate
            channels = channels or audio_info.channels

        cmd = self._build_ffmpeg_command(
            input_file, output_file,
            codec, bitrate, samplerate, channels, loudnorm,
            overwrite
        )

        self._run_subprocess(cmd)
