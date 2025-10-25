from setuptools import setup, find_packages

setup(
    name="video2audio",
    version="0.1.0",
    description="Video2Audio Transcoder - Convert video to audio with FFmpeg!",
    url="https://github.com/trholy/video2audio",
    long_description=open('README.md', encoding='utf-8').read(),
    author="Thomas R. Holy",
    python_requires=">=3.10",
    license_files=('LICENSE',),
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={
        "video2audio": [
            "templates/*",    # include templates in package
            "static/**/*",    # include all static files (css/js)
        ],
    },
    install_requires=[
        "flask>=2.0.0",
        "dash>=2.0.0",
        "dash-bootstrap-components",
    ],
    entry_points={
        "console_scripts": [
            "video2audio=video2audio.cli:main",
            "video2audio-web=video2audio.webapp:run",
        ],
    },
)
