# M3U8 Video Downloader

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A high-performance, async Python application for downloading M3U8 video streams and converting them to MP4 format. Features intelligent master playlist handling, concurrent downloads, retry logic, and an interactive command-line interface.

## ✨ Features

- **🚀 High Performance**: Asynchronous downloads with configurable concurrency (default: 6 concurrent streams)
- **🧠 Smart Playlist Handling**: Automatically detects and selects the highest quality stream from master playlists
- **🔄 Robust Downloads**: Retry logic with exponential backoff for handling network issues
- **📊 Real-time Progress**: Live progress tracking with download rates and ETA
- **💻 Interactive Mode**: User-friendly prompts when command-line arguments are not provided
- **🛡️ Error Resilience**: Comprehensive error handling and graceful failure recovery
- **🎨 Colored Output**: Clear, colored terminal output for better user experience
- **🔧 Cross-platform**: Works on Windows, macOS, and Linux with proper path handling
- **🧹 Auto Cleanup**: Automatic cleanup of temporary files after conversion

## 📋 Prerequisites

### FFmpeg Installation

This application requires **FFmpeg** to be installed and available in your system PATH.

#### Windows
```powershell
# Download from https://ffmpeg.org/download.html#build-windows
# Extract to C:\ffmpeg and add to environament PATH: C:\ffmpeg\bin

# Or using winget (Windows 10+)
winget install ffmpeg
```

#### macOS
```bash
# Using Homebrew
brew install ffmpeg

# Using MacPorts
sudo port install ffmpeg
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# CentOS/RHEL/Fedora
sudo dnf install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

**Verify Installation:**
```bash
ffmpeg -version
```

### Python Requirements
- **Python 3.11+** is required
- Dependencies: `aiohttp`, `ffmpeg-python`

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/dennislwy/m3u8-video-downloader.git
cd m3u8-video-downloader

# Option 1: Using Poetry (recommended)
poetry install
poetry shell

# Option 2: Using pip
pip install -r requirements.txt
```

### Basic Usage

```bash
# Interactive mode (prompts for URL and filename)
python main.py

# Quick download with auto-generated filename
python main.py -u "https://example.com/playlist.m3u8"
```

## 📖 Usage Guide

### Command Line Interface

```bash
python main.py [OPTIONS]
```

| Option         | Description            | Required | Default                  |
| -------------- | ---------------------- | -------- | ------------------------ |
| `-u, --url`    | M3U8 playlist URL      | No*      | Interactive prompt       |
| `-o, --output` | Output filename (.mp4) | No       | Auto-generated timestamp |
| `-p, --path`   | Output directory       | No       | `./output/`              |

*\*If not provided, the application will prompt interactively*

### Usage Examples

#### 1. 🎯 Command Line Mode
```bash
# Download with all parameters specified
python main.py -u "https://example.com/playlist.m3u8" -o "my_video.mp4" -p "./downloads"

# Auto-generated filename
python main.py -u "https://example.com/playlist.m3u8" -p "./downloads"

# Use default output directory
python main.py -u "https://example.com/playlist.m3u8" -o "conference_recording.mp4"
```

#### 2. 💬 Interactive Mode
```bash
# Launch interactive mode
python main.py
```

**Interactive Session Example:**
```
==============================================================
M3U8 Video Downloader
==============================================================
M3U8 URL not specified via command line

Please enter the m3u8 URL you want to download:
Example: https://example.com/playlist.m3u8
--------------------------------------------------------------
Enter m3u8 URL: https://stream.example.com/live/playlist.m3u8
✓ Using URL: https://stream.example.com/live/playlist.m3u8

--------------------------------------------------------------
Enter output filename (press Enter for auto-generated name): webinar_2025
✓ Using filename: webinar_2025.mp4

==============================================================
Final Download Configuration:
  📺 URL: https://stream.example.com/live/playlist.m3u8
  📁 Output: webinar_2025.mp4
  📂 Directory: output
==============================================================

Press Enter to start download or Ctrl+C to cancel...
```

#### 3. 🔄 Mixed Mode
```bash
# Specify URL, get prompted for filename
python main.py -u "https://example.com/playlist.m3u8"

# Specify output, get prompted for URL
python main.py -o "important_video.mp4"
```

### URL Validation & Support

The application intelligently validates M3U8 URLs:
- ✅ **HTTP/HTTPS protocols**: `https://example.com/playlist.m3u8`
- ✅ **Master playlists**: Automatically selects highest quality stream
- ✅ **Relative URLs**: Properly resolves chunk file paths
- ⚠️ **Non-.m3u8 URLs**: Shows warning but continues (some streams don't use .m3u8 extension)

### Output Files

#### Automatic Filename Generation
When no output filename is specified:
```
Format: {timestamp}-output.mp4
Example: 1733404123847-output.mp4
```

#### Manual Filename
- Automatically adds `.mp4` extension if missing
- Sanitizes invalid characters for cross-platform compatibility

## 🔧 Advanced Configuration

### Environment Variables
```bash
# Customize concurrent downloads (default: 6)
export M3U8_MAX_CONCURRENT=10

# Custom temporary directory (detault: temp)
export M3U8_TEMP_DIR="./custom_temp"
```

## 📊 Progress & Monitoring

The application provides detailed progress information:

```
Base URL: https://example.com/stream
Progress: 153/276 (55.4%) [█████████████░░░░░░░░░░░░] ✓ 153 ✗ 0 | 2.1 files/s | ETA: 57s | Downloading: jcrLWLei.ts  
```

### Progress Indicators
- 🔵 **Blue**: Configuration and informational messages
- 🟢 **Green**: Successful operations
- 🟡 **Yellow**: Warnings and retries
- 🔴 **Red**: Errors and failures

## 🛡️ Error Handling & Recovery

### Automatic Retry Logic
- **3 retry attempts** per failed download
- **Exponential backoff**: 1s, 2s, 4s delays between retries
- **Timeout handling**: 30s total, 10s connection timeout
- **Graceful degradation**: Continues with partial downloads

### Common Error Scenarios

| Error                 | Cause                            | Solution                           |
| --------------------- | -------------------------------- | ---------------------------------- |
| `ffmpeg not found`    | FFmpeg not installed             | Install FFmpeg and add to PATH     |
| `Timeout downloading` | Network issues                   | Automatic retry with backoff       |
| `HTTP 403/404`        | Invalid URL or restricted access | Check URL and permissions          |
| `Permission denied`   | Write permissions                | Check output directory permissions |

### Keyboard Shortcuts
- **Ctrl+C**: Gracefully cancel download
- **Enter**: Confirm prompts or use defaults

## 🔍 Technical Details

### Architecture
- **Async/await**: Non-blocking concurrent downloads
- **aiohttp**: High-performance HTTP client
- **Semaphore**: Controls concurrent download limits
- **FFmpeg**: Video concatenation and conversion

### Performance Optimizations
- **8KB chunk size** for optimal memory usage
- **Connection pooling** via aiohttp sessions
- **Concurrent downloads** with configurable limits
- **Streaming downloads** to handle large files

### File Format Support
- **Input**: M3U8 playlists, TS segments
- **Output**: MP4 containers with original codecs
- **Master playlists**: HLS adaptive streaming support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Submit a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FFmpeg** - The backbone of video processing
- **aiohttp** - Excellent async HTTP client
- **Python asyncio** - Making concurrent programming accessible

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/dennislwy/m3u8-video-downloader/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/dennislwy/m3u8-video-downloader/discussions)
- 📧 **Contact**: [wylee2000@gmail.com](mailto:wylee2000@gmail.com)

---

<div align="center">
  Made with ❤️ by <a href="https://github.com/dennislwy">Dennis Lee</a>
</div>