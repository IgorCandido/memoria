"""TmuxPanelManager adapter — manages tmux panes for live output display."""
import logging
import os
import re
import shlex
import shutil
import subprocess
import time
from typing import Optional

from src.domain.entities import PanelConfig, PanelSession

logger = logging.getLogger(__name__)

# BR-005: Named constants for magic numbers
TMUX_PANE_HEIGHT_LINES = 20
PANE_CREATE_TIMEOUT_SECONDS = 10
PANE_OPERATION_TIMEOUT_SECONDS = 5

# Direction mapping: PanelConfig direction -> tmux split-window flags
_TMUX_DIRECTION_FLAGS = {
    "down": ["-v"],
    "right": ["-h"],
    "up": ["-v", "-b"],
    "left": ["-h", "-b"],
}

# BR-003: Whitelist for pane name sanitization
_PANE_NAME_RE = re.compile(r"[^a-zA-Z0-9 _\-.]")


def _sanitize_pane_name(name: str) -> str:
    """Sanitize pane name to prevent injection via select-pane -T."""
    return _PANE_NAME_RE.sub("", name)[:80]


class TmuxPanelManager:
    """Creates and manages tmux panes for live supervisor output.

    Uses `tmux split-window` to create panes running `tail -f <logfile>`.
    """

    def __init__(self, config: Optional[PanelConfig] = None):
        """Initialize TmuxPanelManager.

        Args:
            config: Panel configuration (defaults to PanelConfig.from_env())
        """
        self.config = config or PanelConfig.from_env()

    def create_pane(self, iteration: int, log_file_path: str) -> PanelSession:
        """Create a tmux pane tailing the log file.

        Args:
            iteration: Current supervisor iteration number
            log_file_path: Absolute path to log file to tail

        Returns:
            PanelSession with manager_type="tmux" and pane_id from tmux

        Raises:
            RuntimeError: If pane creation fails
        """
        # BR-008: Generate unique pane name
        pane_name = _sanitize_pane_name(
            f"Claude Worker {os.getpid()}-{int(time.time())}-{iteration}"
        )

        direction_flags = _TMUX_DIRECTION_FLAGS.get(
            self.config.pane_direction, ["-v"]
        )

        # BR-001: Use shlex.quote to prevent shell injection in log_file_path
        cmd = [
            "tmux", "split-window",
            *direction_flags,
            "-l", str(TMUX_PANE_HEIGHT_LINES),
            "-P", "-F", "#{pane_id}",
            f"tail -f {shlex.quote(log_file_path)}",
        ]

        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                timeout=PANE_CREATE_TIMEOUT_SECONDS,
            )
            pane_id = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"tmux pane creation failed (exit code {e.returncode})"
            if e.stderr:
                error_msg += f": {e.stderr.strip()}"
            raise RuntimeError(error_msg) from e
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"tmux split-window timed out after {PANE_CREATE_TIMEOUT_SECONDS}s"
            )

        # Set pane title for identification (BR-003: sanitized pane_name)
        try:
            subprocess.run(
                ["tmux", "select-pane", "-t", pane_id, "-T", pane_name],
                capture_output=True,
                text=True,
                timeout=PANE_OPERATION_TIMEOUT_SECONDS,
            )
        except Exception as e:
            # BR-004: Log instead of silently swallowing
            logger.debug("Failed to set pane title for %s: %s", pane_id, e)

        return PanelSession(
            pane_id=pane_id,
            manager_type="tmux",
            iteration=iteration,
            log_file_path=log_file_path,
        )

    def close_pane(self, session: PanelSession) -> None:
        """Close a tmux pane by its pane_id.

        Idempotent — closing an already-closed pane is a no-op.

        Args:
            session: PanelSession returned by create_pane()
        """
        try:
            subprocess.run(
                ["tmux", "kill-pane", "-t", session.pane_id],
                capture_output=True,
                text=True,
                timeout=PANE_OPERATION_TIMEOUT_SECONDS,
            )
        except Exception as e:
            # BR-004: Log instead of silently swallowing
            logger.debug("Failed to close pane %s: %s", session.pane_id, e)

    def is_available(self) -> bool:
        """Check if tmux is available and we're inside a tmux session.

        Returns:
            True if tmux binary in PATH and $TMUX env var is set
        """
        if shutil.which("tmux") is None:
            return False
        if not os.environ.get("TMUX"):
            return False
        return True
