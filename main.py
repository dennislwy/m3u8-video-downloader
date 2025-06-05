from typing import Tuple
import os
import time
import dataclasses
import argparse
import asyncio
import ffmpeg
import aiohttp
from utils.progress import ProgressTracker
from urllib.parse import urljoin

@dataclasses.dataclass
class Config:
    """Configuration settings for the downloader"""
    # Directory to save downloaded chunk files
    temp_dir: str = os.getenv('M3U8_TEMP_DIR', 'temp')

    # Maximum number of concurrent download tasks
    max_concurrent: int = int(os.getenv('M3U8_MAX_CONCURRENT', '6'))

    # Maximum number of retries for downloading files
    max_retries: int = int(os.getenv('M3U8_MAX_RETRIES', '3'))

    # Chunk byte size for downloading files
    chunk_size: int = int(os.getenv('M3U8_CHUNK_SIZE', '8192'))

    # Timeout settings for aiohttp requests
    timeout_total: int = int(os.getenv('M3U8_TIMEOUT_TOTAL', '30'))
    # Timeout for establishing a connection 
    timeout_connect: int = int(os.getenv('M3U8_TIMEOUT_CONNECT', '10'))

# Create global config instance
config = Config()

# Create a temporary directory (if not exist)
os.makedirs(config.temp_dir, exist_ok=True)
    
async def main(m3u8_url: str,
               output_file: str | None = None,
               output_dir: str | None = None) -> None:
    """
    Downloads and converts a video from an m3u8 URL to an mp4 file.

    This function downloads an m3u8 file from the given URL, parses it to extract the URLs of the
    chunk files, downloads the chunk files, and then uses ffmpeg to convert the chunk files to a
    mp4 file. If the output file name is not provided, it generates a timestamped name. If the
    output directory is not provided, it uses the 'output' directory. It creates the output
    directory if it does not exist.

    Args:
        m3u8_url (str): The URL of the m3u8 file.
        output_file (str, optional): The name of the output mp4 file. If not provided, a timestamped
        name will be used. Defaults to None.
        output_dir (str, optional): The directory where the output file will be saved. If not
        provided, the 'output' directory will be used. Defaults to None.

    Returns:
        None
    """
    # Generate a timestamp for the output file if not provided
    epoch_ms = str(int(time.time()*1000))

    # If output_file is not provided, use a timestamped name
    output_file = f"{epoch_ms}-output.mp4" if output_file is None else output_file
    # Ensure the output file has the .mp4 extension
    if not output_file.endswith('.mp4'):
        output_file = f"{output_file}.mp4"

    # If output_dir is not provided, use the 'output' directory
    output_dir = "output" if output_dir is None else output_dir
    # Create the output directory if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    # Create a session
    async with aiohttp.ClientSession() as session:
        # Download the m3u8 file and parse it to extract the URLs of the chunk files
        chunk_urls = await download_parse_m3u8(session, m3u8_url)

        # Download the chunk files
        await download_files(session, 
                             urls=chunk_urls, 
                             output_dir=config.temp_dir, 
                             prefix=epoch_ms)

    # Create a list of the chunk file names
    chunk_files = [f'{epoch_ms}-file{i+1}.ts' for i in range(len(chunk_urls))]

    # Create a text file listing all the chunk files for ffmpeg
    chunk_list_file = os.path.join(config.temp_dir, f'{epoch_ms}-chunk_list.txt')

    with open(chunk_list_file, 'w', encoding='utf-8') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file}'\n")

    # Convert the chunk files to an mp4 file using ffmpeg
    success = await convert_chunk_files_to_mp4(chunk_list_file, os.path.join(output_dir, output_file))

    # If the conversion was successful, delete the temporary files
    if success:
        print("Deleting temp files")
        for chunk_file in chunk_files:
            try:
                os.remove(os.path.join(config.temp_dir, chunk_file))
            except OSError as e:
                printc(f"Warning: Could not delete {chunk_file}: {e}", Colors.RED)
        try:
            os.remove(chunk_list_file)
        except OSError as e:
            printc(f"Warning: Could not delete {chunk_list_file}: {e}", Colors.RED)

async def download_parse_m3u8(session: aiohttp.ClientSession, m3u8_url: str) -> list[str]:
    """
    Downloads and parses an m3u8 file from the given URL.

    This function downloads an m3u8 file from the given URL, checks if it is a master m3u8 file,
    and if so, downloads the child m3u8 file. It then parses the m3u8 file to extract the URLs
    of the chunk files.

    Args:
        session (aiohttp.ClientSession): The aiohttp client session to use for the request.
        m3u8_url (str): The URL of the m3u8 file.

    Returns:
        list[str]: A list of URLs for the chunk files extracted from the m3u8 file.
    """
    # Get the base URL from the m3u8 URL
    base_url = get_base_url(m3u8_url)
    printc(f"Base URL: {base_url}", Colors.BLUE)

    # Define the path to the m3u8 file in the temporary directory
    m3u8_file = os.path.join(config.temp_dir, get_filename_from_url(m3u8_url))

    # Download the m3u8 file with error handling
    if not await download_file(session, m3u8_url, m3u8_file):
        raise RuntimeError(f"Failed to download M3U8 file from {m3u8_url}")

    # Check if the m3u8 file is a master m3u8 file and get the best quality url stream
    is_m3u8_master, best_stream_url = await check_parse_m3u8_master(m3u8_file)

    # If the m3u8 file is a master m3u8 file
    if is_m3u8_master:
        # Remove the original m3u8 file
        os.remove(m3u8_file)

        # Resolve the best stream URL against the base URL
        m3u8_url = resolve_url(base_url, best_stream_url)
        printc(f"Resolved child m3u8 URL: {m3u8_url}", Colors.BLUE)
            
        # download the child m3u8 file
        m3u8_file = os.path.join(config.temp_dir, get_filename_from_url(m3u8_url))
        await download_file(session, m3u8_url, m3u8_file)

        # if best_stream_url contains sub-path, e.g. '1080p/video.m3u8'
        # extract path from best_stream_url and append to base_url, e.g: 'http://example.com/1080p'
        # Extract directory path from best_stream_url
        stream_path = best_stream_url.rsplit('/', 1)[0] if '/' in best_stream_url else ''
    
        # If we found a path component, update the base_url
        if stream_path:
            base_url = f"{base_url}/{stream_path}"
            printc(f"Updated base URL: {base_url}", Colors.BLUE)

    chunk_urls = []

    # Parse the m3u8 file to extract the URLs of the chunk files
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        add_next_line = False
        for line in f:
            if line.startswith('#EXTINF'):
                add_next_line = True
            elif line.startswith('#EXT-X-MAP:URI'): # #EXT-X-MAP:URI="720p.av1.mp4/init-v1-a1.mp4"
                u = line.split('=')[1].strip().replace('"', "")
                chunk_url = resolve_url(base_url, u)
                chunk_urls.append(chunk_url)
            elif add_next_line:
                chunk_url = resolve_url(base_url, line.strip())
                chunk_urls.append(chunk_url)
                add_next_line = False

    # Remove the m3u8 file
    os.remove(m3u8_file)

    return chunk_urls

async def check_parse_m3u8_master(m3u8_file: str) -> Tuple[bool, str]:
    """
    Checks if the given m3u8 file is a master playlist and extracts the URL of the highest bandwidth
    stream.

    Args:
        m3u8_file (str): _description_

    Returns:
    Args:
        m3u8_file (str): The path to the m3u8 file.

    Returns:
        Tuple[bool, str]: A tuple where the first element is a boolean indicating whether the
                          file is a master playlist and the second element is the URL of the
                          highest bandwidth stream if the file is a master playlist, or an empty
                          string otherwise.
    """
    # Example content of a master m3u8 file
    # #EXTM3U
    # #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=111070,RESOLUTION=256x144
    # 144p.av1.mp4.m3u8
    # #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=174190,RESOLUTION=426x240
    # 240p.av1.mp4.m3u8
    # #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=423790,RESOLUTION=854x480
    # 480p.av1.mp4.m3u8
    # #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=720182,RESOLUTION=1280x720
    # 720p.av1.mp4.m3u8

    # Open the m3u8 file and read it line by line
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        get_next_line = False
        child_streams = {}
        bandwidth = 0
        for line in f:
            # If the line starts with '#EXT-X-STREAM-INF', the file is a master playlist
            if line.startswith('#EXT-X-STREAM-INF'):
                # extract the bandwidth
                bandwidth = int(line.split('BANDWIDTH=')[1].split(',')[0])
                resolution = line.split('RESOLUTION=')[1].split(',')[0]
                get_next_line = True
            # If the previous line started with '#EXT-X-STREAM-INF',
            # this line contains URL of the stream
            elif get_next_line:
                url = line.strip()
                print(f"Found stream '{url}' with bandwidth {bandwidth}, resolution {resolution}")
                child_streams[bandwidth] = url
                bandwidth = 0
                get_next_line = False

        # If no line started with '#EXT-X-STREAM-INF', the file is not a master playlist
        if len(child_streams) == 0:
            return False, ''

        print(f"Found {len(child_streams)} child streams")

        # sort the childs by bandwidth
        sorted_child = dict(sorted(child_streams.items(), reverse=True))
        
        # Get the first item in the sorted dictionary, which is the highest bandwidth stream
        best_child = next(iter(sorted_child.items()))

        printc(f"Best stream is '{best_child[1]}' with bandwidth {best_child[0]}\r\n", Colors.BLUE)
        return True, best_child[1]

def get_filename_from_url(url: str) -> str:
    """
    Extracts the filename from a given URL.

    Args:
        url (str): The URL from which to extract the filename.

    Returns:
        str: The extracted filename.

    """
    return url.split('/')[-1].split('?')[0]

def get_base_url(url: str) -> str:
    """
    Extracts the base URL from the given URL.

    Args:
        url (str): The URL from which to extract the base URL.

    Returns:
        str: The base URL.

    Example:
        >>> get_base_url('https://www.example.com/path/to/file.html')
        'https://www.example.com/path/to'
    """
    return '/'.join(url.split('/')[:-1])

def resolve_url(base_url: str, target_url: str) -> str:
    """
    Resolves a target URL against a base URL, handling both relative and absolute URLs properly.
    
    Args:
        base_url (str): The base URL to resolve against
        target_url (str): The target URL (can be relative or absolute)
        
    Returns:
        str: The resolved absolute URL
        
    Examples:
        >>> resolve_url('https://example.com/videos/', 'playlist.m3u8')
        'https://example.com/videos/playlist.m3u8'
        
        >>> resolve_url('https://example.com/videos/', 'hd/playlist.m3u8')
        'https://example.com/videos/hd/playlist.m3u8'

        >>> resolve_url('https://example.com/videos/', '/hd/playlist.m3u8')
        'https://example.com/hd/playlist.m3u8'
        
        >>> resolve_url('https://example.com/videos/', 'https://cdn.example.com/playlist.m3u8')
        'https://cdn.example.com/playlist.m3u8'
    """
    # Strip whitespace from both URLs
    base_url = base_url.strip()
    target_url = target_url.strip()
    
    if target_url.startswith('http://') or target_url.startswith('https://'):
        # If the target URL is absolute, return it as is
        return target_url
    
    # Use urllib.parse.urljoin for proper URL resolution
    # This handles relative paths, absolute paths, and complex relative URLs correctly
    resolved_url = urljoin(base_url, target_url)
    
    return resolved_url
        
async def download_file(session: aiohttp.ClientSession, url: str, file_path: str, max_retries: int = 3) -> bool:
    """
    Downloads a file from the given URL with retry logic and exponential backoff.

    This function asynchronously downloads a file from a URL using aiohttp with robust error 
    handling. It implements retry logic with exponential backoff for handling temporary network 
    issues, timeouts, and HTTP errors. The file is downloaded in chunks for memory efficiency
    and saved to the specified local path.

    Features:
    - Retry logic with exponential backoff (2^attempt seconds)
    - Timeout handling (30s total, 10s connect)
    - Large chunk size (8192 bytes) for better performance
    - Progress tracking capability (content-length based)
    - Comprehensive error logging with attempt numbers

    Args:
        session (aiohttp.ClientSession): The aiohttp client session to use for the HTTP request.
            Should be properly configured with appropriate headers and settings.
        url (str): The URL of the file to download. Query parameters are stripped for filename
            extraction but preserved for the actual download request.
        file_path (str): The local file path where the downloaded file will be saved. 
            Parent directories should exist or be created beforehand.
        max_retries (int, optional): The maximum number of download attempts before giving up.
            Defaults to 3. Each retry uses exponential backoff (2^attempt seconds).

    Returns:
        bool: True if the file was downloaded successfully within the retry limit, 
              False if all attempts failed or if an unrecoverable error occurred.
    """
    for attempt in range(max_retries):
        try:
            filename = get_filename_from_url(url.split('?')[0])
            
            timeout = aiohttp.ClientTimeout(total=config.timeout_total, connect=config.timeout_connect)
            async with session.get(url, timeout=timeout) as response:
                # If the response status is 200, read the content and write it to the file
                if response.status == 200:
                    # Get content length for progress tracking
                    # content_length = response.headers.get('Content-Length')
                    # if content_length:
                    #     total_size = int(content_length)
                    #     downloaded = 0
                    
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(config.chunk_size):  # Larger chunks
                            f.write(chunk)
                            # if content_length:
                            #     downloaded += len(chunk)
                    
                    printc(f"✓ Downloaded '{filename}'", Colors.GREEN)
                    return True
                else:
                    printc(f"⚠ HTTP {response.status} for '{filename}' (attempt {attempt + 1})", Colors.YELLOW)
                    
        except asyncio.TimeoutError:
            printc(f"⚠ Timeout downloading '{filename}' (attempt {attempt + 1})", Colors.YELLOW)
        except Exception as e:
            printc(f"✗ Error downloading '{filename}' (attempt {attempt + 1}): {e}", Colors.YELLOW)
        
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    printc(f"✗ Failed to download '{filename}' after {max_retries} attempts", Colors.RED)
    return False

async def download_files(session: aiohttp.ClientSession,
                         urls: list[str],
                         output_dir: str,
                         prefix: str='',
                         max_concurrent_tasks: int=config.max_concurrent) -> None:
    """
    Downloads multiple files concurrently from the given URLs and saves them to the specified
    directory.

    This function uses asyncio and aiohttp to download multiple files concurrently. It creates
    a semaphore to limit the maximum number of concurrent download tasks. For each URL, it
    creates a task that downloads the file from the URL and saves it to the output directory
    with a filename that includes a prefix and the file number. It then waits for all tasks to
    complete.

    Args:
        session (aiohttp.ClientSession): The aiohttp client session to use for the request.
        urls (list[str]): A list of URLs pointing to the files to be downloaded.
        output_dir (str): The directory where the downloaded files will be saved.
        prefix (str, optional): A prefix to be added to the filenames of the downloaded files.
        Defaults to an empty string.
        max_concurrent_tasks (int, optional): The maximum number of concurrent download tasks.
        Defaults to DEFAULT_MAX_CONCURRENT_TASKS.

    Returns:
        int: The number of files downloaded successfully.
    """
    # Create a semaphore with the maximum number of concurrent tasks
    sem = asyncio.Semaphore(max_concurrent_tasks)
    progress = ProgressTracker(len(urls))

    async def bound_download_file(session, url, file_path):
        async with sem:
            success = await download_file(session, url, file_path)
            progress.update(success)
            return success

    tasks = []

    # For each URL, create a task that downloads the file and saves it to the output directory
    for i, url in enumerate(urls):
        file_path = os.path.join(output_dir, f'{prefix}-file{i+1}.ts')
        task = asyncio.create_task(bound_download_file(session, url, file_path))
        tasks.append(task)

    # Wait for all tasks to complete    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print()  # New line after progress
    
    success_count = sum(1 for result in results if result is True)
    return success_count

async def convert_chunk_files_to_mp4(file: str, output: str) -> bool:
    """
    Converts a series of chunk files to a single .mp4 file using ffmpeg.

    Args:
        file (str): The path to the input chunk file or a text file containing a list of chunk
        files.
        output (str): The path to save the output .mp4 file.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        printc(f"Converting files in '{file}' to '{output}'", Colors.YELLOW)
        # Use ffmpeg to concatenate the chunk files and save as .mp4
        (
            ffmpeg
            .input(file, format='concat', safe=0)
            .output(output, c='copy')
            # .run_async(overwrite_output=True, pipe_stdout=True, pipe_stderr=True)
            .run(overwrite_output=True)
        )

        printc(f"✓ Finished conversion, '{output}'", Colors.GREEN)
        return True
    
    except ffmpeg.Error as e:
        printc(f"✗ Error converting files: {e.stderr}", Colors.RED)
        return False

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

def printc(msg: str, color: str = Colors.RESET) -> None:
    """
    Prints a message with the specified color.

    Args:
        msg (str): The message to print.
        color (str): The ANSI color code to use for the message. Defaults to RESET (no color).

    Returns:
        None
    """
    if color != Colors.RESET:
        print(f"{color}{msg}{Colors.RESET}")
    else:
        print(msg)

if __name__ == '__main__':
    # Create an argument parser
    parser = argparse.ArgumentParser(description='M3U8 Video Downloader')

    # Add the url argument. This argument is required.
    parser.add_argument('-u', '--url', type=str, required=False, help='The M3U8 url to process')

    # Add the output argument. This argument is optional.
    parser.add_argument('-o', '--output', type=str, required=False, help='The output file name')

    # Add the path argument. This argument is optional.
    parser.add_argument('-p', '--path', type=str, required=False, help='The output directory')

    # Parse the arguments
    args = parser.parse_args()    # Check if we need to run in interactive mode
    interactive_mode = args.url is None or args.output is None
    
    if interactive_mode and args.url is None:
        # Display interactive header
        print("=" * 62)
        printc("M3U8 Video Downloader", Colors.CYAN)
        print("=" * 62)
        printc("⚠ m3u8 URL not specified via command line", Colors.YELLOW)
        print()
        print("Please enter the m3u8 URL you want to download:")
        printc("Example: https://example.com/playlist.m3u8", Colors.BLUE)
        print("-" * 62)

    # If URL is not provided, prompt the user
    url = args.url
    if url is None:
        try:
            url = input("Enter m3u8 URL: ").strip()
            
            if not url:
                printc("✗ URL cannot be empty", Colors.RED)
                exit(1)
            
            # Basic URL validation
            if not (url.startswith('http://') or url.startswith('https://')):
                printc("✗ URL must start with http:// or https://", Colors.RED)
                exit(1)
                
            # Strip query parameters for validation
            query_stripped_url = url.split('?')[0]  # Simple approach
            if not query_stripped_url.endswith('.m3u8'):
                printc("⚠ URL doesn't end with .m3u8, but continuing...", Colors.YELLOW)
            
            printc(f"✓ Using URL: {url}", Colors.GREEN)
            
        except KeyboardInterrupt:
            printc("\n⚠ Operation cancelled by user", Colors.YELLOW)
            exit(0)
        except EOFError:
            printc("✗ No input provided", Colors.RED)
            exit(1)

    # If output file is not provided, prompt the user
    output_file = args.output
    if output_file is None:
        try:
            if interactive_mode:
                print()
                print("-" * 62)
            output_file = input("Enter output filename (press Enter for auto-generated name): ").strip()
            # If user just pressed Enter without typing anything, keep it as None
            if not output_file:
                output_file = None
                if interactive_mode:
                    printc("✓ Using auto-generated filename", Colors.GREEN)
                else:
                    printc("Using auto-generated filename", Colors.YELLOW)
            else:
                if interactive_mode:
                    # Ensure .mp4 extension for display
                    display_name = output_file if output_file.endswith('.mp4') else f"{output_file}.mp4"
                    printc(f"✓ Using filename: {display_name}", Colors.GREEN)
                else:
                    printc(f"Using filename: {output_file}", Colors.GREEN)
        except KeyboardInterrupt:
            printc("\n⚠ Operation cancelled by user", Colors.YELLOW)
            exit(0)
        except EOFError:
            if interactive_mode:
                printc("✓ Using auto-generated filename", Colors.GREEN)
            else:
                printc("No input provided, using auto-generated filename", Colors.YELLOW)
            output_file = None

    # Display configuration summary in interactive mode
    if interactive_mode:
        print()
        print("=" * 62)
        printc("Final Download Configuration:", Colors.CYAN)
        
        # Determine output directory for display
        display_dir = args.path if args.path else "output"
        
        # Determine output filename for display
        if output_file:
            display_filename = output_file if output_file.endswith('.mp4') else f"{output_file}.mp4"
        else:
            display_filename = "auto-generated (timestamp-output.mp4)"
        
        print(f"  📺 URL: {url}")
        print(f"  📁 Output: {display_filename}")
        print(f"  📂 Directory: {display_dir}")
        print("=" * 62)
        print()
        
        try:
            input("Press Enter to start download or Ctrl+C to cancel...")
            print()
        except KeyboardInterrupt:
            printc("\n⚠ Operation cancelled by user", Colors.YELLOW)
            exit(0)

    # Run the main function with the parsed arguments
    try:
        asyncio.run(main(m3u8_url=url, output_file=output_file, output_dir=args.path))
    except KeyboardInterrupt:
        printc("\n⚠ Download interrupted by user", Colors.YELLOW)
        exit(1)
    except Exception as e:
        printc(f"✗ Error: {e}", Colors.RED)
        exit(1)