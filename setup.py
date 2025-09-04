from setuptools import setup, find_packages

setup(
    name="video2audio",
    version="0.1.0",
    description="Convert videos (any format) to audio (any format, e.g., MP3, WAV, AAC) using FFmpeg",
    author="Thomas R. Holy",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "dash>=2.0.0",
        "flask>=2.0.0",
        "dash-bootstrap-components"
    ],
    entry_points={
        "console_scripts": [
            "video2audio=video2audio.cli:main",  # CLI entry point
            "video2audio-web=video2audio.webapp:run",  # Web UI entry point
        ],
    },
)
