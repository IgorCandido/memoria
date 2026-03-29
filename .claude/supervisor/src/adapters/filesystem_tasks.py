"""Filesystem-based task repository adapter."""
import os
import re
from glob import glob
from src.domain.entities import TaskCounts
from src.ports.user_feedback import UserFeedback


# Pre-compiled regex patterns for task parsing (BR-014)
# Pattern: - [x] or - [X] followed by task ID (with optional bold markers)
# Matches: T001, BR001, BR4-001, LR-003, HR-001, etc.
try:
    CHECKED_PATTERN = re.compile(r'- \[x\] (?:\*\*)?[A-Z]+\d*-?\d+(?:\*\*)?', re.IGNORECASE)
    UNCHECKED_PATTERN = re.compile(r'- \[ \] (?:\*\*)?[A-Z]+\d*-?\d+(?:\*\*)?')
except re.error as e:
    raise RuntimeError(f"Invalid task pattern regex: {e}") from e


class FileSystemTaskRepository:
    """Read and parse tasks.md from filesystem (specs/*/tasks.md).

    Auto-detects tasks.md location within specs/ directory structure.
    Caches the tasks.md path after first discovery for performance (BR-024).
    """

    def __init__(self, feedback: UserFeedback | None = None):
        """Initialize repository with empty cache.

        Args:
            feedback: Optional UserFeedback port for warnings (e.g., multiple tasks.md files)
        """
        self._cached_tasks_path: str | None = None
        self._feedback = feedback

    def get_tasks_content(self, working_dir: str) -> str:
        """Read raw content of tasks.md file.

        Args:
            working_dir: Absolute path to directory containing specs/*/tasks.md

        Returns:
            Raw content of tasks.md file as string

        Raises:
            FileNotFoundError: If tasks.md not found in working_dir/specs/*/tasks.md
        """
        # BR-024: Use cached path if available (avoids glob/stat on every iteration)
        if self._cached_tasks_path and os.path.exists(self._cached_tasks_path):
            tasks_file = self._cached_tasks_path
        else:
            # Auto-detect tasks.md from specs/*/tasks.md pattern
            specs_dir = os.path.join(working_dir, "specs")

            if not os.path.exists(specs_dir):
                raise FileNotFoundError(
                    f"specs/ directory not found in {working_dir}. "
                    f"Expected structure: {working_dir}/specs/NNN-feature-name/tasks.md"
                )

            # Search for tasks.md in all spec subdirectories
            # Filter out hidden directories (starting with .) to avoid noise
            tasks_pattern = os.path.join(specs_dir, "*/tasks.md")
            all_tasks_files = glob(tasks_pattern)

            # Filter out hidden directories (e.g., .specify/, .git/)
            tasks_files = [
                f for f in all_tasks_files
                if not any(part.startswith('.') for part in f.split(os.sep))
            ]

            if not tasks_files:
                raise FileNotFoundError(
                    f"No tasks.md found in {specs_dir}/*/tasks.md (hidden dirs filtered). "
                    f"Create a spec directory with tasks.md first."
                )

            if len(tasks_files) > 1:
                # Multiple tasks.md files found - use the most recently modified
                tasks_file = max(tasks_files, key=lambda p: os.path.getmtime(p))
                spec_name = os.path.basename(os.path.dirname(tasks_file))
                if self._feedback:
                    self._feedback.warning(
                        f"Multiple tasks.md files found, using most recent: {spec_name}/tasks.md"
                    )
            else:
                tasks_file = tasks_files[0]

            # Cache for subsequent calls
            self._cached_tasks_path = tasks_file

        # Read and return content
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Validate tasks.md is not empty (BR-017)
            if not content.strip():
                raise ValueError(
                    f"tasks.md is empty: {tasks_file}. "
                    f"Expected at least one task marker (- [ ] or - [x])."
                )
            return content
        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to read {tasks_file}: {e}"
            ) from e

    def parse_tasks(self, content: str) -> TaskCounts:
        """Parse task markers from tasks.md content.

        Recognizes task formats:
        - [ ] T001 Task description (unchecked)
        - [x] T001 Task description (checked)
        - [ ] **T001** Task description (bold, unchecked)
        - [x] **BR-001** Task description (bold checked)

        Supports task prefixes: T, BR, HR, MR, LR, etc.

        Args:
            content: Raw tasks.md content with task markers

        Returns:
            TaskCounts with checked, unchecked, and total counts

        Raises:
            ValueError: If content format is invalid or unparseable
        """
        if not isinstance(content, str):
            raise ValueError(f"content must be string, got {type(content)}")

        # Use pre-compiled patterns (BR-014)
        checked_matches = CHECKED_PATTERN.findall(content)
        unchecked_matches = UNCHECKED_PATTERN.findall(content)

        checked = len(checked_matches)
        unchecked = len(unchecked_matches)
        total = checked + unchecked

        return TaskCounts(
            checked=checked,
            unchecked=unchecked,
            total=total
        )
