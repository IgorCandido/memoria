"""Port interface for user feedback and progress reporting."""
from typing import Protocol


class UserFeedback(Protocol):
    """Port for providing feedback to the user during supervision.

    Enables domain logic to communicate progress, warnings, and status updates
    without directly depending on I/O (print, logging, UI frameworks).

    Example usage:
        feedback.info("Starting supervision session")
        feedback.warning("tasks.md not found, falling back to LLM")
        feedback.progress(f"Task {i}/{total} complete")
    """

    def info(self, message: str) -> None:
        """Display informational message to user.

        Args:
            message: Information to display (e.g., "Starting iteration 5")
        """
        ...

    def warning(self, message: str) -> None:
        """Display warning message to user.

        Args:
            message: Warning to display (e.g., "Failed to parse tasks.md")
        """
        ...

    def progress(self, message: str) -> None:
        """Display progress update to user.

        Args:
            message: Progress update (e.g., "5/10 tasks complete")
        """
        ...

    def progress_start(self, message: str) -> None:
        """Start progress indication (for long-running operations).

        Args:
            message: Start message (e.g., "Spawning Claude worker...")
        """
        ...

    def progress_tick(self) -> None:
        """Show ongoing progress (e.g., print a dot)."""
        ...

    def progress_end(self, message: str = "") -> None:
        """End progress indication.

        Args:
            message: Optional completion message (e.g., "Done (5.2s)")
        """
        ...

    def elapsed_time(self) -> float:
        """Get elapsed time since progress_start.

        Returns:
            Elapsed time in seconds, or 0.0 if no progress active
        """
        ...
