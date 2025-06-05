import sys
from datetime import datetime

class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.start_time = datetime.now()
    
    def update(self, success: bool = True):
        if success:
            self.completed += 1
        else:
            self.failed += 1
        
        progress = (self.completed + self.failed) / self.total * 100
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if elapsed > 0:
            rate = (self.completed + self.failed) / elapsed
            eta = (self.total - self.completed - self.failed) / rate if rate > 0 else 0
            
            sys.stdout.write(f"\rProgress: {self.completed}/{self.total} "
                           f"({progress:.1f}%) | Failed: {self.failed} | "
                           f"Rate: {rate:.1f} files/s | ETA: {eta:.0f}s\r\n")
            sys.stdout.flush()