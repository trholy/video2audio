from setuptools import setup, find_packages

setup(
    name="video2audio",
    version="0.1.0",
    description="Convert videos to audio",
    author="Thomas R. Holy",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,  # <- important
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
