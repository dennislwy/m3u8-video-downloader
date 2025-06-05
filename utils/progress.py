import sys
from datetime import datetime

class ProgressTracker:
    """
    A utility class for tracking and displaying progress of file downloads or processing tasks.
    
    This class provides real-time progress updates including completion percentage, failure count,
    processing rate, and estimated time to completion (ETA).
    
    Attributes:
        total (int): Total number of items to process
        completed (int): Number of successfully completed items
        failed (int): Number of failed items
        start_time (datetime): Timestamp when tracking started
    """
    
    def __init__(self, total: int):
        """
        Initialize the progress tracker.
        
        Args:
            total (int): Total number of items to be processed
            
        Raises:
            ValueError: If total is less than or equal to 0
        """
        if total < 1:
            raise ValueError("Total must be greater than 0")
        
        self.total = total
        self.completed = 0
        self.failed = 0
        self.start_time = datetime.now()
    
    def update(self, success: bool = True):
        """
        Update the progress tracker with the result of a processed item.
        
        This method increments either the completed or failed counter and displays
        an updated progress line including:
        - Current progress (completed/total and percentage)
        - Number of failed items
        - Processing rate (items per second)
        - Estimated time to completion
        
        Args:
            success (bool): Optional. Whether the item was processed successfully.
                            Defaults to True.
        """
        if success:
            self.completed += 1
        else:
            self.failed += 1
        
        progress = (self.completed + self.failed) / self.total * 100
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if elapsed > 0:
            rate = (self.completed + self.failed) / elapsed
            eta = (self.total - self.completed - self.failed) / rate if rate > 0 else 0
            
            # Display the progress line
            sys.stdout.write(f"\rProgress: {self.completed}/{self.total} "
                           f"({progress:.1f}%) | Failed: {self.failed} | "
                           f"Rate: {rate:.1f} files/s | ETA: {eta:.0f}s\r\n")
            # Ensure the output is flushed to the console
            sys.stdout.flush()