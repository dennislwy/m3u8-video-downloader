import os
import sys
import asyncio
import aiohttp
from typing import Optional
from utils.progress import ProgressTracker

async def download_file(session: aiohttp.ClientSession, 
                       url: str, 
                       file_path: str, 
                       max_retries: int = 3, 
                       timeout_total: int = 30,
                       timeout_connect: int = 10,
                       chunk_size: int = 8192,
                       progress_tracker: Optional[ProgressTracker] = None) -> bool:
    """Downloads a file from the given URL with retry logic and exponential backoff.
    
    This function attempts to download a file from a URL with robust error handling,
    including retry logic with exponential backoff for failed attempts. It operates
    silently with optional progress tracking integration.
    
    Args:
        session (aiohttp.ClientSession): The aiohttp client session for HTTP requests.
        url (str): The URL of the file to download.
        file_path (str): The local file path where the downloaded file will be saved.
        max_retries (int, optional): Maximum number of retry attempts for failed 
            downloads. Defaults to 3.
        timeout_total (int, optional): Total timeout for the request. Defaults to 30.
        timeout_connect (int, optional): Connection timeout. Defaults to 10.
        chunk_size (int, optional): Size of chunks to read. Defaults to 8192.
        progress_tracker (ProgressTracker, optional): Progress tracker instance to 
            report current file being downloaded. Defaults to None.
    
    Returns:
        bool: True if the file was successfully downloaded, False otherwise.
    
    Raises:
        No exceptions are raised directly, but logs errors to stderr on final failure.
    """
    # Extract clean filename from URL for display purposes
    filename = _get_filename_from_url(url.split('?')[0])
    
    # Report current file to progress tracker if available
    if progress_tracker:
        progress_tracker.set_current_file(filename)
    
    # Attempt download with retry logic
    for attempt in range(max_retries):
        try:
            status = await _attempt_download(session, url, file_path, timeout_total, timeout_connect, chunk_size)
            if status == 200:
                return True
            else:
                _log_http_error(filename, status, attempt, max_retries)
                
        except asyncio.TimeoutError:
            _log_timeout_error(filename, attempt, max_retries)
        except Exception as e:
            _log_general_error(filename, e, attempt, max_retries)
        
        # Apply exponential backoff delay before retry (except on last attempt)
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    
    return False

async def download_files(session: aiohttp.ClientSession,
                         urls: list[str],
                         output_dir: str,
                         prefix: str = '',
                         max_concurrent_tasks: int = 6,
                         max_retries: int = 3,
                         timeout_total: int = 30,
                         timeout_connect: int = 10,
                         chunk_size: int = 8192) -> int:
    """Downloads multiple files concurrently with progress tracking and clean display.
    
    This function manages concurrent downloads of multiple files using asyncio tasks
    with a semaphore to control the maximum number of simultaneous downloads. It
    provides real-time progress tracking and handles both successful and failed
    downloads gracefully.
    
    Args:
        session (aiohttp.ClientSession): The aiohttp client session for HTTP requests.
        urls (list[str]): List of URLs to download files from.
        output_dir (str): Directory where downloaded files will be saved.
        prefix (str, optional): Prefix to add to downloaded filenames for organization.
            Defaults to empty string.
        max_concurrent_tasks (int, optional): Maximum number of concurrent download 
            tasks. Defaults to 6.
        max_retries (int, optional): Maximum retries per file. Defaults to 3.
        timeout_total (int, optional): Total timeout for requests. Defaults to 30.
        timeout_connect (int, optional): Connection timeout. Defaults to 10.
        chunk_size (int, optional): Size of chunks to read. Defaults to 8192.
    
    Returns:
        int: Number of files successfully downloaded.
    
    Raises:
        No exceptions are raised directly, but individual download failures are 
        handled gracefully and reported in the final summary.
    """
    from utils.colors import printc, Colors  # Import here to avoid circular imports
    
    # Create semaphore to limit concurrent downloads and prevent overwhelming the server
    sem = asyncio.Semaphore(max_concurrent_tasks)
    
    # Initialize progress tracker for real-time download status
    progress = ProgressTracker(len(urls))

    async def bound_download_file(session, url, file_path):
        """Inner function to handle individual file download with semaphore control.
        
        Args:
            session: aiohttp session for the request
            url: URL to download from
            file_path: Local path to save the file
            
        Returns:
            bool: Success status of the download
        """
        # Acquire semaphore before starting download (limits concurrency)
        async with sem:
            # Perform the actual file download
            success = await download_file(session, url, file_path, 
                                        max_retries=max_retries,
                                        timeout_total=timeout_total,
                                        timeout_connect=timeout_connect,
                                        chunk_size=chunk_size,
                                        progress_tracker=progress)
            # Update progress tracker with result
            progress.update(success)
            return success

    tasks = []

    # Create download tasks for each URL
    for i, url in enumerate(urls):
        # Generate unique filename with prefix and sequential numbering
        file_path = os.path.join(output_dir, f'{prefix}-file{i+1}.ts')
        
        # Create async task for this download
        task = asyncio.create_task(bound_download_file(session, url, file_path))
        tasks.append(task)

    # Execute all download tasks concurrently and wait for completion
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Finalize progress display
    progress.finish()
    
    # Calculate success statistics
    success_count = sum(1 for result in results if result is True)
    failed_count = len(urls) - success_count
    
    # Display final download summary
    if failed_count > 0:
        summary_msg = (f"⚠ Download completed: {success_count}/{len(urls)} "
                      f"successful, {failed_count} failed")
        printc(summary_msg, Colors.YELLOW)
    else:
        printc(f"✓ All {success_count} files downloaded successfully", Colors.GREEN)
    
    return success_count

async def _attempt_download(session: aiohttp.ClientSession, url: str, file_path: str, 
                           timeout_total: int, timeout_connect: int, chunk_size: int) -> int:
    """Attempts a single download operation.
    
    Args:
        session: The aiohttp client session
        url: The URL to download from
        file_path: The local file path to save to
        timeout_total: Total timeout for the request
        timeout_connect: Connection timeout
        chunk_size: Size of chunks to read
        
    Returns:
        int: HTTP status code of the response (200 for success)
        
    Raises:
        asyncio.TimeoutError: If request times out
        Exception: For other download errors
    """
    timeout = aiohttp.ClientTimeout(
        total=timeout_total, 
        connect=timeout_connect
    )
    
    async with session.get(url, timeout=timeout) as response:
        if response.status == 200:            
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    f.write(chunk)
        
        return response.status

def _log_timeout_error(filename: str, attempt: int, max_retries: int) -> None:
    """Logs timeout error on final attempt."""
    if attempt == max_retries - 1:
        timeout_msg = (f"\n✗ Timeout downloading '{filename}' "
                      f"after {max_retries} attempts\n")
        sys.stderr.write(timeout_msg)

def _log_general_error(filename: str, error: Exception, attempt: int, max_retries: int) -> None:
    """Logs general error on final attempt."""
    if attempt == max_retries - 1:
        error_msg = f"\n✗ Error downloading '{filename}': {error}\n"
        sys.stderr.write(error_msg)

def _log_http_error(filename: str, status: int, attempt: int, max_retries: int) -> None:
    """Logs HTTP error on final attempt."""
    if attempt == max_retries - 1:
        error_msg = (f"\n✗ HTTP {status} for '{filename}' "
                    f"after {max_retries} attempts\n")
        sys.stderr.write(error_msg)

def _get_filename_from_url(url: str) -> str:
    """
    Extracts the filename from a given URL.

    Args:
        url (str): The URL from which to extract the filename.

    Returns:
        str: The extracted filename.
    """
    return url.split('/')[-1].split('?')[0]