import logging
import time


class Stopwatch:
    """
    A simple stopwatch utility for timing code execution.
    Can be used as a context manager with the 'with' statement.

    Example usage:
        # Basic usage
        sw = Stopwatch()
        # Some code to time
        sw.stop()

        # Or as a context manager
        with Stopwatch() as sw:
            # Code to time
            time.sleep(1)
    """

    def __init__(self, log=True):
        self.start_time = time.time()
        self.end_time = None
        self.log = log

    def stop(self):
        self.end_time = time.time()
        elapsed = self.end_time - self.start_time
        print(f"Time taken: {elapsed:.2f}s")

        if self.log:
            logging.info(f"Time taken: {elapsed:.2f}s")

        return elapsed

    def __enter__(self):
        # Reset timer when entering context
        self.start_time = time.time()
        self.end_time = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Call stop when exiting the context
        self.stop()
