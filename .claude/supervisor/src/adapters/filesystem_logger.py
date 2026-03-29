"""Filesystem-based output logger adapter."""
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from src.domain.entities import RunResult
from src.adapters.ansi_handler import ANSIHandler

# MEDIUM-006: Use shared utility
from src.utils.repo import find_repo_root

# LOW-004: Disk space check constant (100MB minimum)
MIN_DISK_SPACE_MB = 100


@dataclass
class LogFilePair:
    """Pair of log file paths for dual logging.

    Attributes:
        streaming_log_path: Path to streaming log (with ANSI codes)
        stdout_log_path: Path to stdout-only log (without ANSI codes)
    """

    streaming_log_path: str
    stdout_log_path: str

    @classmethod
    def from_iteration(
        cls, log_dir: str, iteration: int, timestamp: str
    ) -> "LogFilePair":
        """Generate both log file paths from iteration info.

        Args:
            log_dir: Directory containing logs
            iteration: Iteration number (1-indexed)
            timestamp: Timestamp string (YYYYMMDD_HHMMSS format)

        Returns:
            LogFilePair with both log file paths

        Example:
            >>> pair = LogFilePair.from_iteration("/tmp/.claude_supervisor", 1, "20260124_153045")
            >>> pair.streaming_log_path
            '/tmp/.claude_supervisor/20260124_153045-iter001.log'
            >>> pair.stdout_log_path
            '/tmp/.claude_supervisor/20260124_153045-iter001_stdout.log'
        """
        base_filename = f"{timestamp}-iter{iteration:03d}"
        streaming_log_path = os.path.join(log_dir, f"{base_filename}.log")
        stdout_log_path = os.path.join(log_dir, f"{base_filename}_stdout.log")

        return cls(
            streaming_log_path=streaming_log_path,
            stdout_log_path=stdout_log_path
        )


class FileSystemOutputLogger:
    """Log supervisor iteration output to filesystem (.claude_supervisor/ directory).

    Generates dual logs per iteration:
    - Streaming log: Full output with ANSI codes preserved (for terminal display)
    - Stdout-only log: Clean output without ANSI codes (for automation/parsing)
    """

    def __init__(self, log_subdir: str = ".claude_supervisor"):
        """Initialize filesystem logger.

        Args:
            log_subdir: Subdirectory name for logs (default: .claude_supervisor)
        """
        self.log_subdir = log_subdir
        self.ansi_handler = ANSIHandler()

    def _check_disk_space(self, directory: str) -> None:
        """Check if sufficient disk space is available for logging.

        Args:
            directory: Directory path to check

        Raises:
            OSError: If less than MIN_DISK_SPACE_MB (100MB) available
        """
        stat = shutil.disk_usage(directory)
        available_mb = stat.free / (1024 * 1024)  # Convert bytes to MB

        if available_mb < MIN_DISK_SPACE_MB:
            raise OSError(
                f"Insufficient disk space: {available_mb:.1f}MB available, "
                f"{MIN_DISK_SPACE_MB}MB required for logging"
            )

    def log_iteration(
        self,
        iteration: int,
        result: RunResult,
        working_dir: str,
        timestamp: str | None = None
    ) -> str:
        """Log the output from a supervisor iteration (dual logging).

        Creates TWO log files per iteration:
        1. Streaming log (with ANSI codes): YYYYMMDD_HHMMSS-iterNNN.log
        2. Stdout-only log (without ANSI codes): YYYYMMDD_HHMMSS-iterNNN_stdout.log

        Creates log directory if it doesn't exist.

        Args:
            iteration: Iteration number (1-indexed)
            result: RunResult from Claude execution
            working_dir: Absolute path to directory containing the feature being supervised
            timestamp: Optional timestamp string to reuse (for consistency with real-time logs)

        Returns:
            Absolute path string to streaming log file (primary log)

        Raises:
            OSError: If log directory cannot be created or log files cannot be written
        """
        # Validate iteration
        if iteration <= 0:
            raise ValueError(f"iteration must be > 0, got {iteration}")

        # Resolve to repository root for logs (T074c)
        # MEDIUM-006: Use shared utility instead of duplicate method
        try:
            repo_root = str(find_repo_root(Path(working_dir)))
        except ValueError:
            # Fallback to working_dir if not in git repo
            repo_root = working_dir

        # Create log directory at repository root
        log_dir = os.path.join(repo_root, self.log_subdir)

        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            raise OSError(
                f"Failed to create log directory {log_dir}: {e}"
            ) from e

        # LOW-004: Check disk space before writing (requires 100MB free)
        self._check_disk_space(log_dir)

        # Generate both log file paths with timestamp (reuse provided timestamp if available)
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_pair = LogFilePair.from_iteration(log_dir, iteration, timestamp)

        # Check if streaming log already exists (from real-time logging)
        # If so, skip writing it (real-time log is the final log)
        streaming_log_exists = os.path.exists(log_pair.streaming_log_path)

        if not streaming_log_exists:
            # Write streaming log (with ANSI codes)
            self._write_streaming_log(log_pair.streaming_log_path, iteration, result)

        # Always write stdout-only log (without ANSI codes)
        self._write_stdout_log(log_pair.stdout_log_path, result)

        # Return primary (streaming) log path for backward compatibility
        return log_pair.streaming_log_path

    def _write_streaming_log(
        self,
        log_path: str,
        iteration: int,
        result: RunResult
    ) -> None:
        """Write streaming log with ANSI codes preserved.

        Args:
            log_path: Path to streaming log file
            iteration: Iteration number
            result: RunResult with full streaming output

        Raises:
            OSError: If file write fails
        """
        # Format log content with ANSI codes preserved
        log_content = self._format_streaming_log(iteration, result)

        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(log_content)
        except Exception as e:
            raise OSError(f"Failed to write streaming log {log_path}: {e}") from e

    def _write_stdout_log(
        self,
        log_path: str,
        result: RunResult
    ) -> None:
        """Write stdout-only log with ANSI codes stripped.

        Args:
            log_path: Path to stdout-only log file
            result: RunResult with streaming output

        Raises:
            OSError: If file write fails
        """
        # Strip ANSI codes for clean parsing
        clean_stdout = self.ansi_handler.strip(result.stdout)

        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                # Backward compatibility: Only write stdout content (no headers, no formatting)
                f.write(clean_stdout)
        except Exception as e:
            raise OSError(f"Failed to write stdout log {log_path}: {e}") from e

    def _format_streaming_log(self, iteration: int, result: RunResult) -> str:
        """Format streaming log content with human-readable headers and ANSI codes preserved.

        Args:
            iteration: Iteration number
            result: RunResult from Claude execution

        Returns:
            Formatted log content as string with ANSI codes preserved
        """
        separator = "=" * 80

        # Calculate size information
        total_bytes, visible_bytes, ansi_bytes, overhead_percent = (
            self.ansi_handler.calculate_sizes(result.stdout)
        )

        log_lines = [
            separator,
            f"Claude Supervisor - Iteration {iteration} (Streaming Log)",
            f"Timestamp: {datetime.now().isoformat()}",
            f"Duration: {result.duration:.2f}s",
            f"Exit Code: {result.exit_code}",
            f"Output Size: {total_bytes:,} bytes total, {visible_bytes:,} visible ({ansi_bytes:,} ANSI codes = {overhead_percent:.1f}% overhead)",
            separator,
            "",
            "STREAMING OUTPUT (WITH ANSI CODES):",
            separator,
            result.stdout,  # Preserve ANSI codes
            "",
            separator,
            "STDERR:",
            separator,
            result.stderr if result.stderr else "(empty)",
            "",
            separator,
            "",
            f"NOTE: A clean stdout-only log (without ANSI codes) is also available at *_stdout.log",
            "",
        ]

        return "\n".join(log_lines)

    def log_outcome(
        self,
        iteration: int,
        outcome: str,
        working_dir: str
    ) -> str:
        """Log the final outcome from a supervisor iteration.

        Args:
            iteration: Iteration number (1-indexed)
            outcome: Final outcome message from worker
            working_dir: Absolute path to directory containing the feature being supervised

        Returns:
            Absolute path string to created outcome file

        Raises:
            OSError: If log directory cannot be created or outcome file cannot be written
        """
        # Validate iteration
        if iteration <= 0:
            raise ValueError(f"iteration must be > 0, got {iteration}")

        # Resolve to repository root for logs (same as log_iteration)
        # MEDIUM-006: Use shared utility instead of duplicate method
        try:
            repo_root = str(find_repo_root(Path(working_dir)))
        except ValueError:
            repo_root = working_dir

        # Create log directory at repository root
        log_dir = os.path.join(repo_root, self.log_subdir)

        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            raise OSError(
                f"Failed to create log directory {log_dir}: {e}"
            ) from e

        # LOW-004: Check disk space before writing (requires 100MB free)
        self._check_disk_space(log_dir)

        # Generate outcome filename
        outcome_filename = f"outcome-iter{iteration:03d}.txt"
        outcome_path = os.path.join(log_dir, outcome_filename)

        # Write outcome file
        try:
            with open(outcome_path, 'w', encoding='utf-8') as f:
                f.write(outcome)
        except Exception as e:
            raise OSError(
                f"Failed to write outcome file {outcome_path}: {e}"
            ) from e

        return outcome_path
