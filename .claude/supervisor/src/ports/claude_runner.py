"""Port interface for executing Claude instances."""
from typing import Protocol
from src.domain.entities import RunResult


class ClaudeRunner(Protocol):
    """Port interface for executing Claude instances.

    Adapters implementing this protocol can use different execution strategies:
    - SubprocessClaudeRunner: Executes real Claude via subprocess
    - TestStubClaudeRunner: Returns predefined responses for testing
    - RemoteClaudeRunner: Executes Claude on remote machine (future)

    Example usage:
        ```python
        # Production: Execute real Claude instance
        runner = SubprocessClaudeRunner()
        result = runner.run(
            prompt="Complete all tasks in tasks.md",
            working_dir="/path/to/worktree",
            timeout=3600
        )
        feedback.completion(f"Exit code: {result.exit_code}, Duration: {result.duration}s")

        # Testing: Use test stub for fast unit tests
        stub = TestStubClaudeRunner(exit_code=0, stdout="All tasks complete")
        result = stub.run(prompt="test", working_dir="/tmp", timeout=60)
        ```
    """

    def run(
        self,
        prompt: str,
        working_dir: str,
        timeout: int = 3600,
        iteration: int | None = None,
        timestamp: str | None = None
    ) -> RunResult:
        """Execute Claude with prompt in working directory.

        Args:
            prompt: Text prompt to send to Claude (can be multi-line)
            working_dir: Absolute path to directory to execute in (must exist)
            timeout: Max execution time in seconds (default: 3600 = 1 hour)
            iteration: Optional iteration number for live monitoring features (e.g., Zellij pane naming)
            timestamp: Optional timestamp string (YYYYMMDD_HHMMSS) for consistent log file naming

        Returns:
            RunResult with stdout, stderr, exit_code, duration

        Raises:
            TimeoutError: If execution exceeds timeout
            FileNotFoundError: If working_dir doesn't exist
            RuntimeError: If Claude CLI not available or execution fails
        """
        ...
