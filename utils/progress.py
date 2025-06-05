import sys
import time
import threading

class ProgressTracker:
    """A thread-safe progress tracker for download operations.
    
    This class provides real-time progress tracking with visual progress bar,
    speed calculation, and ETA estimation for batch download operations.
    """
    
    def __init__(self, total: int):
        """Initialize the progress tracker.
        
        Args:
            total (int): Total number of items to be processed.
        """
        self.total = total
        self.completed = 0  # Counter for successful downloads
        self.failed = 0     # Counter for failed downloads
        self.start_time = time.time()
        self.last_update = 0  # Timestamp of last display update
        self.current_file = ""  # Currently downloading file name
        self.lock = threading.Lock()  # Thread synchronization lock
        
    def set_current_file(self, filename: str):
        """Set the current file being downloaded and update display.
        
        Args:
            filename (str): Name of the file currently being downloaded.
        """
        with self.lock:
            self.current_file = filename
            self._display_progress()
    
    def update(self, success: bool):
        """Update progress counters and refresh display.
        
        Args:
            success (bool): True if the download was successful, False otherwise.
        """
        with self.lock:
            # Update appropriate counter based on success/failure
            if success:
                self.completed += 1
            else:
                self.failed += 1
            
            # Clear current file when download completes
            self.current_file = ""
            
            # Update progress display with throttling to prevent flickering
            current_time = time.time()
            # Update at most 10 times per second (every 0.1 seconds)
            if current_time - self.last_update >= 0.1:
                self._display_progress()
                self.last_update = current_time
    
    def _display_progress(self):
        """Display the current progress with bar, stats, and ETA.
        
        This method creates a comprehensive progress display including:
        - Progress percentage and counts
        - Visual progress bar
        - Success/failure counters
        - Download speed
        - Estimated time of arrival (ETA)
        - Current file being downloaded
        """
        # Calculate basic progress metrics
        processed = self.completed + self.failed
        percentage = (processed / self.total) * 100 if self.total > 0 else 0
        
        # Calculate download speed (files per second)
        elapsed = time.time() - self.start_time
        speed = processed / elapsed if elapsed > 0 else 0
        
        # Estimate time remaining based on current speed
        remaining = self.total - processed
        eta = remaining / speed if speed > 0 else 0
        
        # Create visual progress bar
        bar_width = 25
        filled = int(bar_width * processed / self.total) if self.total > 0 else 0
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # Add current file info if available
        current_info = (f" | Downloading: {self.current_file}" 
                       if self.current_file else "")
        
        # Build the complete progress line
        progress_line = (
            f"\rProgress: {processed}/{self.total} ({percentage:.1f}%) "
            f"[{bar}] "
            f"✓ {self.completed} ✗ {self.failed} "
            f"| {speed:.1f} files/s "
            f"| ETA: {self._format_time(eta)}"
            f"{current_info}"
        )
        
        # Truncate line if it exceeds terminal width to prevent wrapping
        max_line_length = 120
        if len(progress_line) > max_line_length:
            progress_line = progress_line[:117] + "..."
        
        # Clear existing line and write new progress
        sys.stderr.write('\r' + ' ' * max_line_length + '\r')  # Clear line
        sys.stderr.write(progress_line)
        sys.stderr.flush()
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into human readable time string.
        
        Args:
            seconds (float): Time in seconds to format.
            
        Returns:
            str: Formatted time string (e.g., "5s", "2m 30s", "1h 15m").
        """
        # Handle invalid values (infinity and NaN)
        if seconds == float('inf') or seconds != seconds:
            return "--:--"
        
        # Convert to integer seconds for formatting
        seconds = int(seconds)
        
        # Format based on duration magnitude
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:  # Less than 1 hour
            return f"{seconds//60}m {seconds%60}s"
        else:  # 1 hour or more
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def finish(self):
        """Finalize the progress display when all downloads are complete.
        
        This method clears the current file indicator, displays final progress,
        and adds a newline to separate the progress from subsequent output.
        """
        with self.lock:
            self.current_file = ""  # Clear current file indicator
            self._display_progress()  # Show final progress state
            sys.stderr.write('\n')  # Add newline for clean output separation
            sys.stderr.flush()