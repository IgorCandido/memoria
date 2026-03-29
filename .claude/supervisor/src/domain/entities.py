"""Domain entities for Claude Supervisor.

All entities are immutable value objects following Domain-Driven Design principles.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskCounts:
    """Immutable snapshot of task completion state from tasks.md parsing.

    Attributes:
        checked: Number of completed tasks ([x])
        unchecked: Number of incomplete tasks ([ ])
        total: Total tasks detected
    """
    checked: int
    unchecked: int
    total: int

    @property
    def is_complete(self) -> bool:
        """Work complete if no unchecked tasks remain (and some exist).

        Returns:
            True if all tasks are checked and at least one task exists, False otherwise
        """
        return self.unchecked == 0 and self.total > 0

    def __post_init__(self):
        """Validate invariants."""
        if self.checked < 0:
            raise ValueError(f"checked must be >= 0, got {self.checked}")
        if self.unchecked < 0:
            raise ValueError(f"unchecked must be >= 0, got {self.unchecked}")
        if self.total < 0:
            raise ValueError(f"total must be >= 0, got {self.total}")
        if self.total != self.checked + self.unchecked:
            raise ValueError(
                f"total ({self.total}) must equal checked ({self.checked}) + "
                f"unchecked ({self.unchecked})"
            )


@dataclass(frozen=True)
class RunResult:
    """Immutable result from executing a Claude instance.

    Attributes:
        stdout: Standard output captured from Claude
        stderr: Standard error captured from Claude
        exit_code: Process exit code (0 = success, non-zero = error)
        duration: Execution time in seconds
    """
    stdout: str
    stderr: str
    exit_code: int
    duration: float

    def __post_init__(self):
        """Validate invariants."""
        if self.duration < 0.0:
            raise ValueError(f"duration must be >= 0.0, got {self.duration}")
        if self.stdout is None:
            raise ValueError("stdout cannot be None (use empty string)")
        if self.stderr is None:
            raise ValueError("stderr cannot be None (use empty string)")


@dataclass(frozen=True)
class SessionResult:
    """Final outcome of supervisor session.

    Attributes:
        success: Whether all work completed successfully
        iterations: Number of iterations executed
        exit_code: Supervisor exit code (0=success, non-zero=failure)
        completion_reason: Human-readable explanation of why session ended
    """
    success: bool
    iterations: int
    exit_code: int
    completion_reason: str

    def __post_init__(self):
        """Validate invariants."""
        if self.iterations <= 0:
            raise ValueError(f"iterations must be > 0, got {self.iterations}")
        if self.success and self.exit_code != 0:
            raise ValueError(
                f"success=True requires exit_code=0, got {self.exit_code}"
            )
        if not self.success and self.exit_code == 0:
            raise ValueError(
                f"success=False requires exit_code!=0, got {self.exit_code}"
            )
        if not self.completion_reason:
            raise ValueError("completion_reason cannot be empty")


@dataclass(frozen=True)
class PanelSession:
    """Represents an active pane in a window manager.

    Returned by PanelManager.create_pane(), used by close_pane().
    Immutable value object — once created, cannot be modified.

    Attributes:
        pane_id: Window manager-specific identifier (e.g., tmux '%42', zellij pane name)
        manager_type: Which manager created this session ('tmux', 'zellij', 'none')
        iteration: Supervisor iteration number this pane belongs to
        log_file_path: Path to the log file being tailed in this pane
    """
    pane_id: str
    manager_type: str
    iteration: int
    log_file_path: str


@dataclass
class PanelConfig:
    """Configuration for panel behavior, shared across all panel manager implementations.

    Attributes:
        pane_direction: Split direction (down, right, left, up)
        pane_name_template: Template for pane names, must contain {iteration}
        auto_close_panes: Whether to close panes after iteration completes
    """
    pane_direction: str = "down"
    pane_name_template: str = "Claude Worker {iteration}"
    auto_close_panes: bool = False

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
        """
        valid_directions = {"down", "right", "left", "up"}
        if self.pane_direction not in valid_directions:
            raise ValueError(
                f"pane_direction must be one of {valid_directions}, got: {self.pane_direction}"
            )
        if "{iteration}" not in self.pane_name_template:
            raise ValueError(
                f"pane_name_template must contain {{iteration}}, got: {self.pane_name_template}"
            )

    @classmethod
    def from_env(cls) -> "PanelConfig":
        """Create PanelConfig from environment variables.

        Reads SUPERVISOR_* environment variables:
        - SUPERVISOR_PANE_DIRECTION: Pane split direction (default: down)
        - SUPERVISOR_PANE_NAME_TEMPLATE: Pane name template (default: "Claude Worker {iteration}")
        - SUPERVISOR_AUTO_CLOSE_PANES: Auto-close panes flag (default: false)

        Returns:
            PanelConfig with values from environment or defaults
        """
        config = cls(
            pane_direction=os.environ.get("SUPERVISOR_PANE_DIRECTION", "down"),
            pane_name_template=os.environ.get(
                "SUPERVISOR_PANE_NAME_TEMPLATE", "Claude Worker {iteration}"
            ),
            auto_close_panes=os.environ.get("SUPERVISOR_AUTO_CLOSE_PANES", "").lower()
            in ("true", "1", "yes"),
        )
        config.validate()
        return config
