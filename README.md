# m3u8 Video Downloader

This is a Python script that downloads and converts videos from an m3u8 URL to an mp4 file.
It downloads the m3u8 file, parses it for .ts files, downloads these .ts files, and then combines them into a single .mp4 file.

## Prerequisites

This script requires FFmpeg to be installed on your system. FFmpeg is a free and open-source software project consisting of a large suite of libraries and programs for handling video, audio, and other multimedia files and streams.

### Installing FFmpeg on Windows

1. Download the latest version of FFmpeg from the [official website](https://ffmpeg.org/download.html#build-windows).

2. Extract the downloaded zip file. This will give you a folder named something like `ffmpeg-2024-06-24-git-6ec22731ae-full_build`.

3. Move this folder to `C:\` and rename it to `ffmpeg`.

4. Add `C:\ffmpeg\bin` to your system's PATH environment variable:
    - Search for "Environment Variables" in your computer's search bar and select "Edit the system environment variables".
    - In the System Properties window that appears, click the "Environment Variables" button.
    - In the Environment Variables window, under "System variables", find the "Path" variable, select it, and click "Edit".
    - In the Edit Environment Variable window, click "New", and then type `C:\ffmpeg\bin`.
    - Click "OK" in all windows to apply the changes.

You can verify the installation by opening a new command prompt window and running `ffmpeg -version`. If the installation was successful, this will print information about the installed version of FFmpeg.

## Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management. If you haven't installed Poetry yet, you can do so by following the instructions on their [official website](https://python-poetry.org/docs/#installation).

Once you have Poetry installed, you can install the project and its dependencies with:

```bash
# Clone the repository
git clone https://github.com/dennislwy/m3u8-video-downloader.git

# Navigate into the project directory
cd m3u8-video-downloader

# Install the project and its dependencies
poetry install
```

Alternatively, you can use pip to install the dependencies from the requirements.txt file:
```bash
# Clone the repository
git clone https://github.com/dennislwy/m3u8-video-downloader.git

# Navigate into the project directory
cd m3u8-video-downloader

# Install the project and its dependencies
pip install -r requirements.txt
```

## Usage
You can run the script with the following command:
```bash
poetry run python main.py -u "your_m3u8_url"
```

You can also specify the output file name and directory:
```bash
poetry run python main.py -u "your_m3u8_url" -o "your_output_file.mp4" -p "your_output_directory"
```
By default, if no output file name is provided, a timestamped name will be used. If no output directory is provided, the 'output' directory will be used.