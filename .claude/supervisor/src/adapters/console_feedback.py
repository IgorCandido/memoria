"""Console feedback adapter for printing to stdout."""
import time
from typing import Optional


class ConsoleFeedback:
    """Adapter that prints feedback messages to stdout.

    Implements UserFeedback port by directly printing to console with
    appropriate formatting for info, warnings, and progress updates.
    """

    def __init__(self):
        """Initialize console feedback adapter."""
        self._last_progress_time: Optional[float] = None

    def info(self, message: str) -> None:
        """Print informational message to stdout.

        Args:
            message: Information to display
        """
        print(message)

    def warning(self, message: str) -> None:
        """Print warning message to stdout with warning prefix.

        Args:
            message: Warning to display
        """
        print(f"⚠️  {message}")

    def progress(self, message: str) -> None:
        """Print progress update to stdout.

        Args:
            message: Progress update to display
        """
        print(message)

    def progress_start(self, message: str) -> None:
        """Print start of progress update (without newline for dots).

        Args:
            message: Progress start message
        """
        print(message, end="", flush=True)
        self._last_progress_time = time.time()

    def progress_tick(self) -> None:
        """Print progress tick (dot) to show ongoing work."""
        if self._last_progress_time is None:
            self._last_progress_time = time.time()

        print(".", end="", flush=True)

    def progress_end(self, message: str = "") -> None:
        """Print end of progress update with newline.

        Args:
            message: Optional completion message
        """
        if message:
            print(f" {message}")
        else:
            print()  # Just newline
        self._last_progress_time = None

    def elapsed_time(self) -> float:
        """Get elapsed time since progress_start was called.

        Returns:
            Elapsed time in seconds, or 0.0 if no progress active
        """
        if self._last_progress_time is None:
            return 0.0
        return time.time() - self._last_progress_time
