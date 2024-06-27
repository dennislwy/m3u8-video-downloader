from typing import Tuple
import os
import time
import argparse
import asyncio
import ffmpeg
import aiohttp

# Directory to save downloaded chunk files
TEMP_DIR = 'temp'

# Create a temporary directory (if not exist)
os.makedirs(TEMP_DIR, exist_ok=True)

async def main(m3u8_url: str,
               output_file: str | None = None,
               output_dir: str | None = None):
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
        await download_files(session, chunk_urls, TEMP_DIR, prefix=epoch_ms)

    # Create a list of the chunk file names
    chunk_files = [f'{epoch_ms}-file{i+1}.ts' for i in range(len(chunk_urls))]

    # Create a text file listing all the chunk files for ffmpeg
    chunk_list_file = f'temp/{epoch_ms}-chunk_list.txt'
    with open(chunk_list_file, 'w', encoding='utf-8') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file}'\n")

    # Convert the chunk files to an mp4 file using ffmpeg
    success = await convert_chunk_files_to_mp4(chunk_list_file, f'{output_dir}/{output_file}')

    # If the conversion was successful, delete the temporary files
    if success:
        print("Deleting temp files")
        for chunk_file in chunk_files:
            os.remove(f'{TEMP_DIR}/{chunk_file}')
        os.remove(chunk_list_file)

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
    print(f"Base URL: {base_url}")

    # Define the path to the m3u8 file in the temporary directory
    m3u8_file = f'{TEMP_DIR}/{get_filename_from_url(m3u8_url)}'

    # Download the m3u8 file
    await download_file(session, m3u8_url, m3u8_file)

    # Check if the m3u8 file is a master m3u8 file
    is_m3u8_master, m3u8_master_url = await check_m3u8_master(m3u8_file)

    # If the m3u8 file is a master m3u8 file, download the child m3u8 file
    if is_m3u8_master:
        os.remove(m3u8_file)
        m3u8_url = f'{base_url}/{m3u8_master_url}'
        m3u8_file = f'{TEMP_DIR}/{get_filename_from_url(m3u8_url)}'
        await download_file(session, m3u8_url, m3u8_file)

    chunk_urls = []

    # Parse the m3u8 file to extract the URLs of the chunk files
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        add_next_line = False
        for line in f:
            if line.startswith('#EXTINF'):
                add_next_line = True
            elif add_next_line:
                chunk_url = f'{base_url}/{line.strip()}'
                chunk_urls.append(chunk_url)
                add_next_line = False

    # Remove the m3u8 file
    os.remove(m3u8_file)

    return chunk_urls

async def check_m3u8_master(m3u8_file: str) -> Tuple[bool, str]:
    """
    Checks if the given m3u8 file is a master playlist.

    This function opens the given m3u8 file and reads it line by line. If a line starts with
    '#EXT-X-STREAM-INF', the file is a master playlist and the function returns True and the
    URL of the first stream. If no line starts with '#EXT-X-STREAM-INF', the file is not a
    master playlist and the function returns False and an empty string.

    Args:
        m3u8_file (str): The path to the m3u8 file.

    Returns:
        Tuple[bool, str]: A tuple where the first element is a boolean indicating whether the
                          file is a master playlist and the second element is the URL of the
                          first stream if the file is a master playlist, or an empty string
                          otherwise.
    """
    # Open the m3u8 file and read it line by line
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        get_next_line = False
        for line in f:
            # If the line starts with '#EXT-X-STREAM-INF', the file is a master playlist
            if line.startswith('#EXT-X-STREAM-INF'):
                get_next_line = True
            # If the previous line started with '#EXT-X-STREAM-INF',
            # this line contains URL of the first stream
            elif get_next_line:
                return True, line.strip()
    # If no line started with '#EXT-X-STREAM-INF', the file is not a master playlist
    return False, ''

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

async def download_file(session: aiohttp.ClientSession, url: str, file_path: str) -> bool:
    """
    Downloads a file from the given URL and saves it to the specified file path.

    This function uses aiohttp to download a file asynchronously. It sends a GET request to the
    URL and reads the response content in chunks of 1024 bytes, which it writes to the file at the
    specified path. If the response status is not 200, it prints an error message and does not
    create or modify the file.

    Args:
        session (aiohttp.ClientSession): The aiohttp client session to use for the request.
        url (str): The URL of the file to download.
        file_path (str): The file path to save the downloaded file.

    Returns:
        bool: True if the file was downloaded successfully, False otherwise.
    """

    # Remove query parameters from the URL to get the filename
    url_without_params = url.split('?')[0]
    filename = get_filename_from_url(url_without_params)

    # Print a message indicating that the download has started
    print(f"Downloading '{filename}' from '{url}'")

    # Send a GET request to the URL
    async with session.get(url) as response:
        # If the response status is 200, read the content and write it to the file
        if response.status == 200:
            with open(file_path, 'wb') as f:
                while True:
                    # Read the content in chunks of 1024 bytes
                    chunk = await response.content.read(1024)
                    # If there is no more content to read, break the loop
                    if not chunk:
                        break
                    # Write the chunk to the file
                    f.write(chunk)
                # Print a message indicating that the download has finished
                print(f"Downloaded '{filename}'")
                return True
        # If the response status is not 200, print an error message
        print(f"Failed to download '{filename}'")
        return False

async def download_files(session: aiohttp.ClientSession, urls: list[str], output_dir: str, prefix: str='', max_concurrent_tasks: int=10):
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
        Defaults to 10.

    Returns:
        None
    """
    # Create a semaphore with the maximum number of concurrent tasks
    sem = asyncio.Semaphore(max_concurrent_tasks)

    async def bound_download_file(session, url, file_path):
        # Use the semaphore to limit the number of concurrent download tasks
        async with sem:
            # Download the file and save it to the specified path
            await download_file(session, url, file_path)

    tasks = []
    # For each URL, create a task that downloads the file and saves it to the output directory
    for i, url in enumerate(urls):
        file_path = os.path.join(output_dir, f'{prefix}-file{i+1}.ts')
        task = bound_download_file(session, url, file_path)
        tasks.append(task)
    # Wait for all tasks to complete
    await asyncio.gather(*tasks)

async def convert_chunk_files_to_mp4(file: str, output: str) -> bool:
    """
    Converts a series of chunk files to a single .mp4 file using ffmpeg.

    Args:
        file (str): The path to the input chunk file or a text file containing a list of chunk
        files.
        output (str): The path to save the output .mp4 file.

    Returns:
        None
    """
    try:
        print(f"Converting files in '{file}' to .mp4 '{output}'")
        # Use ffmpeg to concatenate the chunk files and save as .mp4
        (
            ffmpeg
            .input(file, format='concat', safe=0)
            .output(output, c='copy')
            # .run_async(overwrite_output=True, pipe_stdout=True, pipe_stderr=True)
            .run(overwrite_output=True)
        )

        print(f"Finished converting to .mp4, '{output}'")
        return True
    except ffmpeg.Error as e:
        print(f"Error converting to .mp4: {e.stderr}")
        return False

if __name__ == '__main__':
    # Create an argument parser
    parser = argparse.ArgumentParser(description='m3u8 Video Downloader')

    # Add the url argument. This argument is required.
    parser.add_argument('-u', '--url', type=str, required=True, help='The m3u8 url to process')

    # Add the output argument. This argument is optional.
    parser.add_argument('-o', '--output', type=str, required=False, help='The output file name')

    # Add the path argument. This argument is optional.
    parser.add_argument('-p', '--path', type=str, required=False, help='The output directory')

    # Parse the arguments
    args = parser.parse_args()

    # Run the main function with the parsed arguments
    asyncio.run(main(m3u8_url=args.url, output_file=args.output, output_dir=args.path))
