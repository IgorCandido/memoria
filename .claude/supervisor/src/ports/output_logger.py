"""Port interface for logging supervisor iteration output."""
from typing import Protocol
from src.domain.entities import RunResult


class OutputLogger(Protocol):
    """Port interface for logging supervisor iteration output.

    Adapters implementing this protocol can use different logging strategies:
    - FileSystemOutputLogger: Writes logs to .claude_supervisor/ directory
    - NoOpLogger: Discards output (testing)
    - RemoteLogger: Sends logs to remote service (future)
    """

    def log_iteration(
        self,
        iteration: int,
        result: RunResult,
        working_dir: str,
        timestamp: str | None = None
    ) -> str:
        """Log the output from a supervisor iteration.

        Args:
            iteration: Iteration number (1-indexed)
            result: RunResult from Claude execution
            working_dir: Absolute path to directory containing the feature being supervised
            timestamp: Optional timestamp to reuse for consistent log file naming

        Returns:
            Absolute path string to created log file

        Raises:
            OSError: If log directory cannot be created or log file cannot be written
        """
        ...

    def log_outcome(
        self,
        iteration: int,
        outcome: str,
        working_dir: str
    ) -> str:
        """Log the final outcome/message from a supervisor iteration.

        Captures the worker's final response for debugging.
        Filename format: outcome-iterNNN.txt

        Args:
            iteration: Iteration number (1-indexed)
            outcome: Final outcome message from worker
            working_dir: Absolute path to directory containing the feature being supervised

        Returns:
            Absolute path string to created outcome file

        Raises:
            OSError: If log directory cannot be created or outcome file cannot be written
        """
        ...
