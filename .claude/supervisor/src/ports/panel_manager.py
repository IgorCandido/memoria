"""PanelManager port — interface for window manager panel operations.

Adapters implementing this protocol handle pane lifecycle:
- TmuxPanelManager: Creates/closes tmux panes
- ZellijPanelManager: Creates/closes zellij panes
- NullPanelManager: No-op (for subprocess-only mode)
"""
from typing import Protocol

from src.domain.entities import PanelSession


class PanelManager(Protocol):
    """Port interface for window manager panel operations.

    The panel manager is responsible for:
    1. Creating a pane that displays live output (via tail -f on log file)
    2. Closing the pane when iteration completes (if auto-close enabled)
    3. Detecting availability (is the multiplexer running and accessible?)

    The panel manager does NOT:
    - Write output to panes directly (runners write to log files)
    - Control process execution (that's the runner's job)
    - Handle PTY/streaming (that's the runner's job)
    """

    def create_pane(self, iteration: int, log_file_path: str) -> PanelSession:
        """Create a pane displaying live output from the log file.

        Creates a split pane in the current window manager session
        that runs `tail -f <log_file_path>` to show real-time output.

        Args:
            iteration: Current supervisor iteration number (for pane naming)
            log_file_path: Absolute path to log file to tail

        Returns:
            PanelSession handle for later operations (e.g., close_pane)

        Raises:
            RuntimeError: If pane creation fails (non-fatal — caller should handle)
        """
        ...

    def close_pane(self, session: PanelSession) -> None:
        """Close a previously created pane.

        Args:
            session: PanelSession returned by create_pane()

        Note:
            Closing a pane that's already closed is a no-op (idempotent).
            Errors during close are logged but not raised (best-effort).
        """
        ...

    def is_available(self) -> bool:
        """Check if the window manager is available for pane operations.

        Checks:
        1. Multiplexer binary is in PATH
        2. We're running inside an active session of that multiplexer

        Returns:
            True if panes can be created, False otherwise

        Note:
            NullPanelManager always returns True (it's the universal fallback).
        """
        ...
