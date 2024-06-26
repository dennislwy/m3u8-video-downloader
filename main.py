from typing import Tuple
import os
import time
import argparse
import ffmpeg
import asyncio
import aiohttp

temp_dir = 'temp' # Directory to save downloaded .ts files
output_dir = 'output' # Directory to save the final .mp4 file
os.makedirs(temp_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

async def main(m3u8_url: str,
               output_file: str | None = None,
               output_dir: str | None = None):
    """
    Downloads and converts a video from an m3u8 URL to an mp4 file.

    Args:
        m3u8_url (str): The URL of the m3u8 file.
        output_file (str, optional): The name of the output mp4 file. If not provided, a timestamped name will be used. Defaults to None.
        output_dir (str, optional): The directory where the output file will be saved. If not provided, the 'output' directory will be used. Defaults to None.

    Returns:
        None
    """
    # Generate a timestamp for the output file if not provided
    ts = str(int(time.time()*1000))

    output_file = f"{ts}-output.mp4" if output_file is None else output_file
    output_dir = "output" if output_dir is None else output_dir

    # download m3u8_url & parse for .ts files
    ts_urls = await download_parse_m3u8(m3u8_url)

    # download .ts files
    await download_files(ts_urls, temp_dir, prefix=ts)

    # create a file list
    ts_files = [f'{ts}-file{i+1}.ts' for i in range(len(ts_urls))]

    # Create a text file listing all the .ts files for ffmpeg
    ts_list_file = f'temp/{ts}-ts_list.txt'
    with open(ts_list_file, 'w', encoding='utf-8') as f:
        for ts_file in ts_files:
            f.write(f"file '{ts_file}'\n")

    # convert .ts files to .mp4
    success = await ts_files_to_mp4(ts_list_file, output=f'{output_dir}/{output_file}')

    # on success, remove temp files
    if success:
        print("Deleting temp files")
        for ts_file in ts_files:
            os.remove(ts_file)
        os.remove(ts_list_file)

async def download_parse_m3u8(m3u8_url: str) -> list[str]:
    """
    Downloads and parses an m3u8 file from the given URL.

    Args:
        m3u8_url (str): The URL of the m3u8 file.

    Returns:
        list[str]: A list of URLs for the ts files extracted from the m3u8 file.
    """
    base_url = get_base_url(m3u8_url)
    print(f"Base URL: {base_url}")

    # download m3u8_url to temp_dir
    m3u8_file = f'{temp_dir}/{get_filename_from_url(m3u8_url)}'
    async with aiohttp.ClientSession() as session:
        await download_file(session, m3u8_url, m3u8_file)

    # check is m3u8 file a master m3u8 file?
    is_m3u8_master, m3u8_master_url = await check_m3u8_master(m3u8_file)

    if is_m3u8_master:
        os.remove(m3u8_file)
        m3u8_url = f'{base_url}/{m3u8_master_url}'
        print(m3u8_url)
        m3u8_file = f'{temp_dir}/{get_filename_from_url(m3u8_url)}'
        async with aiohttp.ClientSession() as session:
            await download_file(session, m3u8_url, m3u8_file)

    ts_urls = []

    # parse .m3u8 file for ts_urls
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        add_next_line = False
        for line in f:
            if line.startswith('#EXTINF'):
                add_next_line = True
            elif add_next_line:
                ts_url = f'{base_url}/{line.strip()}'
                ts_urls.append(ts_url)
                add_next_line = False

    os.remove(m3u8_file)

    return ts_urls

async def check_m3u8_master(m3u8_file: str) -> Tuple[bool, str]:
    """
    Check if the given .m3u8 file is a master playlist and return the first stream URL.

    Args:
        m3u8_file (str): The path to the .m3u8 file.

    Returns:
        Tuple[bool, str]: A tuple containing a boolean indicating whether the file is a master playlist
                          and the first stream URL if it is, otherwise an empty string.
    """
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        get_next_line = False
        for line in f:
            if line.startswith('#EXT-X-STREAM-INF'):
                get_next_line = True
            elif get_next_line:
                return True, line.strip()
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

async def download_files(urls: list[str], output_dir: str, prefix: str='', max_concurrent_tasks: int=10):
    """
    Downloads multiple files concurrently from the given URLs and saves them to the specified directory.

    Args:
        urls (list[str]): A list of URLs pointing to the files to be downloaded.
        output_dir (str): The directory where the downloaded files will be saved.
        prefix (str, optional): A prefix to be added to the filenames of the downloaded files. Defaults to an empty string.
        max_concurrent_tasks (int, optional): The maximum number of concurrent download tasks. Defaults to 10.
    """
    sem = asyncio.Semaphore(max_concurrent_tasks)

    async def bound_download_file(session, url, file_path):
        async with sem:
            await download_file(session, url, file_path)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, url in enumerate(urls):
            file_path = os.path.join(output_dir, f'{prefix}-file{i+1}.ts')
            task = bound_download_file(session, url, file_path)
            tasks.append(task)
        await asyncio.gather(*tasks)

async def download_file(session, url, file_path):
    """
    Downloads a file from the given URL and saves it to the specified file path.

    Args:
        session (aiohttp.ClientSession): The aiohttp client session to use for the download.
        url (str): The URL of the file to download.
        file_path (str): The file path where the downloaded file should be saved.

    Returns:
        None
    """
    # remove query parameters from url
    url_without_params = url.split('?')[0]
    filename_from_url = get_filename_from_url(url)

    print(f"Downloading '{url_without_params}'")
    async with session.get(url) as response:
        if response.status == 200:
            with open(file_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
                print(f"Downloaded '{url_without_params}'")
        else:
            print(f"Failed to download '{url_without_params}'")

async def ts_files_to_mp4(file: str, output: str) -> bool:
    """
    Converts a series of .ts files to a single .mp4 file using ffmpeg.

    Args:
        file (str): The path to the input .ts file or a text file containing a list of .ts files.
        output (str): The path to save the output .mp4 file.

    Returns:
        None
    """
    try:
        print(f"Converting files in '{file}' to .mp4 '{output}'")
        # Use ffmpeg to concatenate the .ts files and save as .mp4
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
    parser = argparse.ArgumentParser(description='m3u8 Video Downloader')
    parser.add_argument('-m3u8', type=str, required=True, help='The m3u8 url to process')
    parser.add_argument('-output', type=str, required=False, help='The output file name')

    args = parser.parse_args()

    asyncio.run(main(m3u8_url=args.m3u8, output_file=args.output))
