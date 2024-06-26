# m3u8 Video Downloader

This is a Python script that downloads and converts videos from an m3u8 URL to an mp4 file.
It downloads the m3u8 file, parses it for .ts files, downloads these .ts files, and then combines them into a single .mp4 file.

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

## Usage
You can run the script with the following command:
```
poetry run python main.py --m3u8_url "your_m3u8_url_here"
```

You can also specify the output file name and directory:
```
poetry run python main.py --m3u8_url "your_m3u8_url_here" --output_file "your_output_file_name_here" --output_dir "your_output_directory_here"
```
By default, if no output file name is provided, a timestamped name will be used. If no output directory is provided, the 'output' directory will be used.