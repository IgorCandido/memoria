"""ZellijPanelManager adapter — manages zellij panes for live output display.

Extracted from ZellijClaudeRunner._create_zellij_pane() to separate
panel management from process execution.
"""
import logging
import os
import subprocess
import time
from typing import Optional

from src.domain.entities import PanelConfig, PanelSession
from src.adapters.zellij_runner import ZellijDetector

logger = logging.getLogger(__name__)

# BR-005/006: Named constants for timeouts
PANE_CREATE_TIMEOUT_SECONDS = 10
PANE_OPERATION_TIMEOUT_SECONDS = 5


class ZellijPanelManager:
    """Creates and manages zellij panes for live supervisor output.

    Uses `zellij action new-pane` to create panes running `tail -f <logfile>`.
    """

    def __init__(
        self,
        config: Optional[PanelConfig] = None,
        detector: Optional[ZellijDetector] = None,
    ):
        """Initialize ZellijPanelManager.

        Args:
            config: Panel configuration (defaults to PanelConfig.from_env())
            detector: Zellij availability detector (defaults to new ZellijDetector())
        """
        self.config = config or PanelConfig.from_env()
        self.detector = detector or ZellijDetector()

    def create_pane(self, iteration: int, log_file_path: str) -> PanelSession:
        """Create a zellij pane tailing the log file.

        Args:
            iteration: Current supervisor iteration number
            log_file_path: Absolute path to log file to tail

        Returns:
            PanelSession with manager_type="zellij"

        Raises:
            RuntimeError: If pane creation fails
        """
        # BR-008: Generate unique pane name
        pane_name = f"Claude Worker {os.getpid()}-{int(time.time())}-{iteration}"

        cmd = [
            "zellij",
            "action",
            "new-pane",
            "--name", pane_name,
            "--direction", self.config.pane_direction,
        ]

        if self.config.auto_close_panes:
            cmd.append("--close-on-exit")

        # BR-002: log_file_path passed as separate list element (safe from injection
        # since subprocess.run with list args doesn't invoke shell)
        cmd.extend(["--", "tail", "-f", log_file_path])

        try:
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                timeout=PANE_CREATE_TIMEOUT_SECONDS,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"Zellij pane creation failed (exit code {e.returncode})"
            if e.stderr:
                error_msg += f": {e.stderr.strip()}"
            raise RuntimeError(error_msg) from e

        return PanelSession(
            pane_id=pane_name,
            manager_type="zellij",
            iteration=iteration,
            log_file_path=log_file_path,
        )

    def close_pane(self, session: PanelSession) -> None:
        """Best-effort close of a zellij pane.

        Zellij doesn't have a direct kill-pane-by-id command like tmux.
        If --close-on-exit was set, the pane closes when tail exits.
        This method attempts `zellij action close-pane` as best-effort.

        Args:
            session: PanelSession to close
        """
        try:
            subprocess.run(
                ["zellij", "action", "close-pane"],
                capture_output=True,
                text=True,
                timeout=PANE_OPERATION_TIMEOUT_SECONDS,
            )
        except Exception as e:
            # BR-004: Log instead of silently swallowing
            logger.debug("Failed to close zellij pane: %s", e)

    def is_available(self) -> bool:
        """Check if zellij is available and we're in an active session.

        Returns:
            True if zellij binary in PATH and ZELLIJ_SESSION_NAME is set
        """
        return self.detector.is_available()
