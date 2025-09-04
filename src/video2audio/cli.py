import argparse
from pathlib import Path
from video2audio.transcoder import Video2Audio


def main():
    parser = argparse.ArgumentParser(description="Convert video to audio with FFmpeg")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("output", help="Output audio file")
    parser.add_argument("--codec", default="mp3", help="Audio codec (default: mp3)")
    parser.add_argument("--bitrate", help="Audio bitrate (e.g., 192k). Use --auto to detect automatically")
    parser.add_argument("--samplerate", type=int, help="Sample rate (e.g., 44100). Use --auto to detect automatically")
    parser.add_argument("--channels", type=int, help="Number of channels (1=mono, 2=stereo). Use --auto to detect automatically")
    parser.add_argument("--loudnorm", action="store_true", help="Enable loudness normalization")
    parser.add_argument("--auto", action="store_true", help="Automatically detect best bitrate, samplerate, and channels")
    args = parser.parse_args()

    transcoder = Video2Audio()
    transcoder.convert(
        input_file=Path(args.input),
        output_file=Path(args.output),
        codec=args.codec,
        bitrate=args.bitrate,
        samplerate=args.samplerate,
        channels=args.channels,
        loudnorm=args.loudnorm,
        auto=args.auto,
    )
    print(f"✅ Converted {args.input} → {args.output}")


if __name__ == "__main__":
    main()
