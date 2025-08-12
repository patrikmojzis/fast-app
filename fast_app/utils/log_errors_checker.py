import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, TypedDict

# Shared helpers for jobs
DEFAULT_LOG_ERRORS_CHECK_MINUTES: int = 5

class LogErrorEntry(TypedDict):
    """Typed dictionary for log error entries returned by get_error_entries"""
    timestamp: str
    logger: str
    level: str
    message: str
    traceback: List[str]


class LogErrorsChecker:
    def __init__(self, *, check_minutes: int = 5, log_file_path: Path = None):
        self.check_minutes = check_minutes
        self.log_file_path = log_file_path

        if not self.log_file_path:
            self.log_file_path = Path(__file__).parent.parent.parent.parent.parent / "log" / "app.log"

    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp from log entry"""
        try:
            # Format: "2025-07-19 07:32:26,112"
            # Remove milliseconds and parse
            timestamp_clean = timestamp_str.split(',')[0]
            return datetime.strptime(timestamp_clean, "%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError) as e:
            logging.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
            return None
    
    def is_recent_entry(self, timestamp_str: str) -> bool:
        """Check if log entry is from the last 5 minutes"""
        entry_time = self.parse_timestamp(timestamp_str)
        if entry_time is None:
            return False
            
        cutoff_time = datetime.now() - timedelta(minutes=self.check_minutes)
        return entry_time >= cutoff_time
    
    def get_error_entries(self) -> List[LogErrorEntry]:
        """Parse log content and extract ERROR/CRITICAL entries from last `self.check_minutes` minutes"""
        if not self.log_file_path.exists():
                logging.warning(f"Log file not found: {self.log_file_path}")
                return []
            
        # Read the entire log file
        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if not content.strip():
            return []

        lines = content.split('\n')
        errors = []
        current_error = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a log entry start (has timestamp)
            if ' - ' in line and any(level in line for level in [' - ERROR - ', ' - CRITICAL - ']):
                # Save previous error if exists and it's recent
                if current_error and self.is_recent_entry(current_error['timestamp']):
                    errors.append(current_error)
                
                # Start new error
                parts = line.split(' - ', 3)
                if len(parts) >= 4:
                    timestamp, logger_name, level, message = parts
                    current_error = {
                        'timestamp': timestamp,
                        'logger': logger_name,
                        'level': level,
                        'message': message,
                        'traceback': []
                    }
                else:
                    current_error = None
            elif current_error and line.startswith('Traceback'):
                # Start of traceback
                current_error['traceback'].append(line)
            elif current_error and (line.startswith('  ') or line.startswith('    ') or 
                                   'File "' in line or 'Error:' in line or 'Exception:' in line):
                # Continuation of traceback
                current_error['traceback'].append(line)
            elif current_error and line and not any(level in line for level in [' - INFO - ', ' - DEBUG - ', ' - WARNING - ']):
                # Possible continuation of error message
                current_error['traceback'].append(line)
            elif ' - ' in line and any(level in line for level in [' - INFO - ', ' - DEBUG - ', ' - WARNING - ']):
                # New log entry that's not an error - save current error if recent
                if current_error and self.is_recent_entry(current_error['timestamp']):
                    errors.append(current_error)
                current_error = None
        
        # Don't forget the last error
        if current_error and self.is_recent_entry(current_error['timestamp']):
            errors.append(current_error)
            
        return errors


def process_traceback(traceback_lines: List[str]) -> List[str]:
    """Truncate long tracebacks to the first and last 10 lines."""
    if len(traceback_lines) > 20:
        first_10 = traceback_lines[:10]
        last_10 = traceback_lines[-10:]
        return first_10 + ["... (middle of traceback omitted) ..."] + last_10
    return traceback_lines