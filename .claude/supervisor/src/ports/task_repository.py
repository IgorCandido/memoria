"""Port interface for reading and parsing tasks.md files."""
from typing import Protocol
from src.domain.entities import TaskCounts


class TaskRepository(Protocol):
    """Port interface for reading and parsing task completion state.

    Adapters implementing this protocol can use different storage mechanisms:
    - FileSystemTaskRepository: Reads from specs/*/tasks.md on disk
    - InMemoryTaskRepository: Reads from in-memory string (testing)
    - RemoteTaskRepository: Reads from remote API (future)

    Example usage:
        ```python
        # Production: Read from filesystem
        repo = FileSystemTaskRepository()
        content = repo.get_tasks_content("/path/to/worktree")
        counts = repo.parse_tasks(content)
        feedback.progress(f"{counts.checked}/{counts.total} tasks complete")

        # Testing: Use in-memory stub
        repo = InMemoryTaskRepository("- [x] T001 Done\\n- [ ] T002 Todo")
        counts = repo.parse_tasks(repo.get_tasks_content("/tmp"))
        assert counts.is_complete == False
        ```
    """

    def get_tasks_content(self, working_dir: str) -> str:
        """Read raw content of tasks.md file.

        Args:
            working_dir: Absolute path to directory containing specs/*/tasks.md

        Returns:
            Raw content of tasks.md file as string

        Raises:
            FileNotFoundError: If tasks.md not found in working_dir/specs/*/tasks.md
        """
        ...

    def parse_tasks(self, content: str) -> TaskCounts:
        """Parse task markers from tasks.md content.

        Args:
            content: Raw tasks.md content with task markers

        Returns:
            TaskCounts with checked, unchecked, and total counts

        Raises:
            ValueError: If content format is invalid or unparseable
        """
        ...
