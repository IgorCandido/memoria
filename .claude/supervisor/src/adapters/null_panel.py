"""NullPanelManager adapter — no-op panel management for subprocess-only mode.

Implements the Null Object pattern: satisfies the PanelManager protocol
with no-op methods, avoiding conditional checks throughout the codebase.
"""
from src.domain.entities import PanelSession


class NullPanelManager:
    """No-op panel manager for when no window manager is configured.

    Always "available" — it's the universal fallback.
    create_pane returns a dummy PanelSession, close_pane is a no-op.
    """

    def create_pane(self, iteration: int, log_file_path: str) -> PanelSession:
        """Return a dummy PanelSession (no actual pane created).

        Args:
            iteration: Current supervisor iteration number
            log_file_path: Path to log file (unused)

        Returns:
            PanelSession with pane_id="null" and manager_type="none"
        """
        return PanelSession(
            pane_id="null",
            manager_type="none",
            iteration=iteration,
            log_file_path=log_file_path,
        )

    def close_pane(self, session: PanelSession) -> None:
        """No-op — nothing to close."""
        pass

    def is_available(self) -> bool:
        """Always returns True — NullPanelManager is the universal fallback."""
        return True
