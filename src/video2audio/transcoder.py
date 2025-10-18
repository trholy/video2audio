import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AudioInfo:
    """Structured representation of audio stream information."""
    bitrate: int
    samplerate: int
    channels: int


class CodecConfig:
    """Codec-specific capability table."""
    LOSSY = {"mp3", "aac"}
    LOSSLESS = {"wav", "flac"}

    MAX_BITRATE = {
        "mp3": 320_000,
        "aac": 256_000,
        "wav": None,
        "flac": None}

    DEFAULT_BITRATE = {
        "mp3": 192_000,
        "aac": 128_000,
        "wav": None,
        "flac": None}

    DEFAULT_SAMPLERATE = {
        "mp3": 44100,
        "aac": 48000,
        "wav": 44100,
        "flac": 96000}

    SUPPORTED_SAMPLERATES = {
        "mp3": [32000, 44100, 48000],
        "aac": [44100, 48000, 96000],
        "wav": [44100, 48000, 96000, 192000],
        "flac": [44100, 48000, 96000, 192000]}

    DEFAULT_CHANNELS = {
        "mp3": 2, "aac": 2, "wav": 2, "flac": 2}

    SUPPORTED_CHANNELS = {
        "mp3": [1, 2],
        "aac": [1, 2],
        "wav": [1, 2, 6, 8],
        "flac": [1, 2, 6, 8]}

class Video2Audio:
    """
    Convert video files to audio with codec-aware automatic settings.
    Provides smart defaults for bitrate, sample rate, and channels.
    """

    def __init__(
            self,
            ffmpeg_bin="ffmpeg",
            ffprobe_bin="ffprobe"
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
            str(input_file)]

        result = self._run_subprocess(cmd)
        info = json.loads(result.stdout)
        stream: Dict[str, Any] = info.get("streams", [{}])[0]

        return AudioInfo(
            bitrate=int(stream.get("bit_rate", 0) or 0),
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

        if codec in CodecConfig.LOSSLESS:
            return None
        if input_bitrate <= 0:
            return f"{default_bitrate // 1000}k" if default_bitrate else None

        if default_bitrate and input_bitrate < default_bitrate:
            return f"{default_bitrate // 1000}k"

        if max_bitrate:
            return f"{min(input_bitrate, max_bitrate) // 1000}k"

        return None  # For lossless/uncompressed

    @staticmethod
    def _validate_params(
            codec: str,
            samplerate: int,
            channels: int
    ):
        """Ensure valid samplerate/channels for given codec."""
        sr_list = CodecConfig.SUPPORTED_SAMPLERATES[codec]
        ch_list = CodecConfig.SUPPORTED_CHANNELS[codec]
        if samplerate not in sr_list:
            samplerate = CodecConfig.DEFAULT_SAMPLERATE[codec]
        if channels not in ch_list:
            channels = CodecConfig.DEFAULT_CHANNELS[codec]
        return samplerate, channels

    def _build_ffmpeg_command(
            self,
            input_file: Path,
            output_file: Path,
            codec: str,
            bitrate: Optional[str],
            samplerate: Optional[int],
            channels: Optional[int],
            loudnorm: bool,
            overwrite: bool
    ) -> list[str]:
        """Construct the ffmpeg command for audio conversion."""
        cmd = [self.ffmpeg_bin]
        if overwrite:
            cmd.append("-y")

        cmd += ["-i", str(input_file), "-vn"]

        # ------------------------------------------------------------
        # Codec and container handling
        # ------------------------------------------------------------
        # Map logical codec to correct FFmpeg format/container
        # (AAC must use mp4 container, not 'aac' muxer)
        format_map = {
            "mp3": "mp3",
            "aac": "mp4",
            "wav": "wav",
            "flac": "flac"
        }
        fmt = format_map.get(codec, codec)

        # ------------------------------------------------------------
        # Audio filters
        # ------------------------------------------------------------
        if loudnorm:
            cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]

        # ------------------------------------------------------------
        # Parameter validation
        # ------------------------------------------------------------
        # Clamp samplerate for lossy codecs (MP3/AAC)
        if codec in ["mp3", "aac"] and samplerate and samplerate > 48000:
            logger.warning(
                f"⚠️ {codec.upper()} supports ≤ 48000 Hz."
                f" Using 48000 instead of {samplerate}.")
            samplerate = 48000

        # Skip bitrate for lossless formats (WAV, FLAC)
        if codec in ["wav", "flac"]:
            bitrate = None

        # ------------------------------------------------------------
        # Audio parameters
        # ------------------------------------------------------------
        if samplerate:
            cmd += ["-ar", str(samplerate)]
        if channels:
            cmd += ["-ac", str(channels)]
        if bitrate and codec in ["mp3", "aac"]:
            cmd += ["-b:a", bitrate]

        # ------------------------------------------------------------
        # Metadata + Output
        # ------------------------------------------------------------
        cmd += ["-map_metadata", "0", "-f", fmt, str(output_file)]
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
            auto: bool = True
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
        input_file, output_file = Path(input_file), Path(output_file)

        if auto:
            audio_info = self._get_audio_info(input_file)
            bitrate = bitrate or self._determine_bitrate(codec, audio_info.bitrate)
            samplerate = samplerate or audio_info.samplerate
            channels = channels or audio_info.channels

        samplerate, channels = self._validate_params(codec, samplerate, channels)
        cmd = self._build_ffmpeg_command(
            input_file, output_file,
            codec, bitrate, samplerate, channels, loudnorm,
            overwrite
        )

        self._run_subprocess(cmd)
