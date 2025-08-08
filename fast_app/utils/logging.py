import logging
import os
import sys
from pathlib import Path

_logging_configured = False

def setup_logging():
    """
    Setup logging for the application.

    Log levels:
    - CRITICAL
    - ERROR
    - WARNING
    - INFO
    - DEBUG
    - NOTSET
    """
    global _logging_configured
    
    # Prevent multiple configuration
    if _logging_configured:
        return
    
    # Get the project root directory (where this script's parent's parent is)
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / "log"
    log_file = log_dir / "app.log"
    
    # Ensure log directory exists
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())
    
    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Create file handler
    file_handler = logging.FileHandler(str(log_file), mode='a')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Add console handler for debug environment
    if os.getenv('ENV') == 'debug':
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Set up global exception handler to catch uncaught exceptions
    def log_uncaught_exception(exc_type, exc_value, exc_traceback):
        # Don't log KeyboardInterrupt (Ctrl+C)
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Log all other uncaught exceptions
        logging.critical(
            "Uncaught exception crashed the application", 
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    # Install the global exception handler
    sys.excepthook = log_uncaught_exception
    
    _logging_configured = True
    logging.info("Logging configured successfully with global exception handling")
