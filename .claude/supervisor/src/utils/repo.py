"""Repository utilities for finding git roots.

MEDIUM-006: Shared utility to avoid duplication between cli.py and filesystem_logger.py
"""

from pathlib import Path


def find_repo_root(path: Path) -> Path:
    """Find repository root by searching for .git directory.

    Args:
        path: Starting path (usually worktree path)

    Returns:
        Path to repository root

    Raises:
        ValueError: If not inside a git repository or path is unsafe
    """
    current = path.resolve()

    # HIGH-005: Validate starting path is under home directory
    home = Path.home().resolve()
    try:
        current.relative_to(home)
    except ValueError:
        raise ValueError(
            f"Security: Working directory must be under home directory. "
            f"Path {current} is outside {home}"
        )

    while current != current.parent:
        if (current / ".git").exists():
            repo_root = current.resolve()

            # Validate repo_root is under home directory (symlink attack prevention)
            try:
                repo_root.relative_to(home)
            except ValueError:
                raise ValueError(
                    f"Security: Repository root must be under home directory. "
                    f"Found repo at {repo_root} which is outside {home}"
                )

            return repo_root
        current = current.parent
    raise ValueError(
        f"Not inside a git repository. Could not find .git directory starting from {path}"
    )
