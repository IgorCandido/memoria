"""Zellij-integrated Claude runner with PTY streaming capture."""
import os
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.shell import expand_alias


@dataclass
class ZellijConfig:
    """Configuration for Zellij integration.

    Attributes:
        pane_direction: Direction to split pane (down, right, left, up)
        pane_name_template: Template for pane name (must contain {iteration})
        auto_close_panes: Whether to close panes automatically after completion
        disable_zellij: DEPRECATED — use manifest panel_manager field instead. Kept for backwards compat.
    """

    pane_direction: str = "down"
    pane_name_template: str = "Claude Worker {iteration}"
    auto_close_panes: bool = False
    disable_zellij: bool = False

    def __post_init__(self):
        """Validate configuration after initialization (BR-004 fix)."""
        self.validate()

    @classmethod
    def from_env(cls) -> "ZellijConfig":
        """Create ZellijConfig from environment variables.

        Reads SUPERVISOR_* environment variables:
        - SUPERVISOR_PANE_DIRECTION: Pane split direction (default: down)
        - SUPERVISOR_PANE_NAME_TEMPLATE: Pane name template (default: "Claude Worker {iteration}")
        - SUPERVISOR_AUTO_CLOSE_PANES: Auto-close panes flag (default: false)
        - SUPERVISOR_DISABLE_ZELLIJ: Explicit disable flag (default: false)

        Returns:
            ZellijConfig with values from environment or defaults

        Raises:
            ValueError: If configuration values are invalid

        Example:
            ```python
            # With env vars set
            os.environ["SUPERVISOR_PANE_DIRECTION"] = "right"
            config = ZellijConfig.from_env()
            assert config.pane_direction == "right"
            ```
        """
        return cls(
            pane_direction=os.environ.get("SUPERVISOR_PANE_DIRECTION", "down"),
            pane_name_template=os.environ.get(
                "SUPERVISOR_PANE_NAME_TEMPLATE", "Claude Worker {iteration}"
            ),
            auto_close_panes=os.environ.get("SUPERVISOR_AUTO_CLOSE_PANES", "").lower()
            in ("true", "1", "yes"),
            disable_zellij=os.environ.get("SUPERVISOR_DISABLE_ZELLIJ", "").lower()
            in ("true", "1", "yes"),
        )

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


class ZellijDetector:
    """Detector for Zellij availability with caching.

    Checks:
    1. SUPERVISOR_DISABLE_ZELLIJ environment variable (explicit disable)
    2. zellij executable in PATH
    3. ZELLIJ_SESSION_NAME environment variable (running in Zellij)
    """

    def __init__(self):
        """Initialize detector with empty cache."""
        self._cached_result: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if Zellij is available and supervisor is running in a Zellij session.

        Uses cached result if available to avoid repeated checks.

        Returns:
            True if Zellij is available and we're in a session, False otherwise

        Example:
            ```python
            detector = ZellijDetector()
            if detector.is_available():
                print("Zellij is available")
            ```
        """
        # Return cached result if available
        if self._cached_result is not None:
            return self._cached_result

        # Check 1: Explicit disable flag
        if os.environ.get("SUPERVISOR_DISABLE_ZELLIJ", "").lower() in (
            "true",
            "1",
            "yes",
        ):
            self._cached_result = False
            return False

        # Check 2: zellij executable in PATH
        if shutil.which("zellij") is None:
            self._cached_result = False
            return False

        # Check 3: Running in a Zellij session
        if not os.environ.get("ZELLIJ_SESSION_NAME"):
            self._cached_result = False
            return False

        # All checks passed
        self._cached_result = True
        return True

    def reset_cache(self) -> None:
        """Reset cached detection result.

        Useful for testing or when environment changes during runtime.
        """
        self._cached_result = None


class StreamingBuffer:
    """Memory-efficient buffer with automatic disk overflow.

    Stores streaming output in memory until it exceeds MEMORY_THRESHOLD_BYTES,
    then switches to disk-based storage to prevent OOM errors with large outputs.
    """

    MEMORY_THRESHOLD_BYTES = 100 * 1024 * 1024  # 100 MB

    def __init__(self):
        """Initialize empty buffer."""
        self._memory_buffer: list[str] = []
        self._memory_bytes = 0
        self._disk_file: Optional[tempfile.NamedTemporaryFile] = None
        self._using_disk = False

    def append(self, data: str) -> None:
        """Append data to buffer (memory or disk).

        Automatically switches to disk if memory threshold exceeded.

        Args:
            data: String data to append
        """
        data_bytes = len(data.encode("utf-8"))

        # Check if we need to switch to disk
        if not self._using_disk and (
            self._memory_bytes + data_bytes > self.MEMORY_THRESHOLD_BYTES
        ):
            self._switch_to_disk()

        # Append to appropriate storage
        if self._using_disk:
            assert self._disk_file is not None
            self._disk_file.write(data.encode("utf-8"))
            self._disk_file.flush()
        else:
            self._memory_buffer.append(data)
            self._memory_bytes += data_bytes

    def _switch_to_disk(self) -> None:
        """Switch from memory to disk storage.

        Creates temporary file and writes existing memory buffer to it.
        """
        # Create temporary file
        self._disk_file = tempfile.NamedTemporaryFile(
            mode="w+b", delete=False, suffix=".streaming_buffer"
        )

        # Write existing memory buffer to disk
        for chunk in self._memory_buffer:
            self._disk_file.write(chunk.encode("utf-8"))
        self._disk_file.flush()

        # Clear memory buffer
        self._memory_buffer.clear()
        self._memory_bytes = 0
        self._using_disk = True

    def get_content(self) -> str:
        """Get complete buffer content as string.

        Returns:
            Complete buffer content

        Raises:
            OSError: If disk read fails
        """
        if self._using_disk:
            assert self._disk_file is not None
            # Read entire file
            self._disk_file.seek(0)
            content_bytes = self._disk_file.read()
            return content_bytes.decode("utf-8")
        else:
            return "".join(self._memory_buffer)

    def cleanup(self) -> None:
        """Clean up resources (close and delete disk file if exists)."""
        if self._disk_file is not None:
            try:
                filename = self._disk_file.name
                self._disk_file.close()
                # Check if os module still exists (interpreter shutdown safety)
                # During shutdown, modules may be None - prevent AttributeError
                if os is not None:
                    os.unlink(filename)
            except Exception:
                pass  # Best effort cleanup

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()


class ZellijClaudeRunner:
    """Execute Claude with PTY streaming capture and optional Zellij pane integration.

    This adapter implements the ClaudeRunner port with enhanced features:
    - PTY (pseudo-terminal) for full streaming output capture
    - Dual logging: streaming log (with ANSI) + stdout-only log (clean)
    - Optional Zellij live pane display
    - Graceful degradation when Zellij unavailable

    Unlike SubprocessClaudeRunner which uses subprocess.PIPE (buffers only final output),
    ZellijClaudeRunner uses PTY to capture all streaming output including:
    - Tool calls with arguments
    - Thinking blocks
    - Progress indicators
    - Real-time file operations

    Usage:
        ```python
        runner = ZellijClaudeRunner(config=ZellijConfig.from_env())
        result = runner.run(
            prompt="Complete all tasks",
            working_dir="/path/to/worktree",
            timeout=3600
        )
        ```
    """

    def __init__(
        self,
        config: Optional[ZellijConfig] = None,
        detector: Optional[ZellijDetector] = None,
        claude_command: str = "clauderock",
        feedback: Optional[object] = None,
        panel_manager: Optional[object] = None,
    ):
        """Initialize Zellij Claude runner.

        Args:
            config: Zellij configuration (defaults to ZellijConfig.from_env())
            detector: Zellij detector (defaults to new ZellijDetector())
            claude_command: Claude CLI command to use (default: clauderock)
            feedback: Optional feedback adapter for user messaging
            panel_manager: Optional PanelManager for pane lifecycle (if None, uses embedded _create_zellij_pane fallback)

        Raises:
            ValueError: If claude_command contains shell metacharacters (BR-012 security fix)
        """
        self.config = config or ZellijConfig.from_env()
        self.detector = detector or ZellijDetector()
        self.panel_manager = panel_manager

        # BR-012: Validate claude_command to prevent command injection
        # Allow only alphanumeric, underscore, hyphen, slash (for paths), and dot
        # Reject shell metacharacters: |;&$`()<>{}[]!*?#~'"\ and whitespace
        if not claude_command or not claude_command.strip():
            raise ValueError("claude_command cannot be empty")

        # Check for shell metacharacters that could enable injection
        dangerous_chars = set("|;&$`()<>{}[]!*?#~'\"\\")
        if any(char in claude_command for char in dangerous_chars):
            raise ValueError(
                f"claude_command contains dangerous shell metacharacters: {claude_command}. "
                "Only alphanumeric characters, underscores, hyphens, slashes, and dots are allowed."
            )

        # Check for whitespace (command should be single executable, not a shell pipeline)
        if " " in claude_command or "\t" in claude_command or "\n" in claude_command:
            raise ValueError(
                f"claude_command cannot contain whitespace: {claude_command}. "
                "Specify only the executable name or path, not arguments."
            )

        self.claude_command = claude_command
        self.feedback = feedback
        self.config.validate()

    def _expand_alias(self, alias_name: str) -> tuple[dict[str, str], str]:
        """Delegate to shared utility. See src/utils/shell.expand_alias."""
        return expand_alias(alias_name)

    def run(
        self,
        prompt: str,
        working_dir: str,
        timeout: int = 3600,
        iteration: int | None = None,
        timestamp: str | None = None
    ) -> "RunResult":  # type: ignore
        """Execute Claude with PTY streaming capture.

        Args:
            prompt: Text prompt to send to Claude
            working_dir: Absolute path to working directory
            timeout: Max execution time in seconds
            iteration: Optional iteration number for Zellij pane naming
            timestamp: Optional timestamp string for consistent log file naming

        Returns:
            RunResult with full streaming output

        Raises:
            FileNotFoundError: If working_dir doesn't exist
            RuntimeError: If execution fails
        """
        # Import here to avoid circular dependency
        from src.domain.entities import RunResult

        # Validate working directory
        if not os.path.exists(working_dir):
            raise FileNotFoundError(f"Working directory does not exist: {working_dir}")
        if not os.path.isdir(working_dir):
            raise FileNotFoundError(f"Working directory is not a directory: {working_dir}")

        # Validate prompt
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        # Validate timeout
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")

        # Check Zellij availability and provide user feedback (T044-T046)
        zellij_available = self.detector.is_available()

        if zellij_available:
            # INFO: Zellij is available - live pane display possible (future enhancement)
            # For now, just log that Zellij is detected
            pass  # Future: Create Zellij pane for live display
        else:
            # INFO: Zellij unavailable - graceful degradation mode
            # Determine reason for unavailability to provide helpful instructions
            if self.config.disable_zellij:
                # User explicitly disabled Zellij
                pass  # Silent: user knows what they're doing
            elif not shutil.which("zellij"):
                # Zellij not in PATH
                # INFO: Could print hint about installing Zellij, but this is optional
                pass  # Silent: not everyone needs Zellij
            elif not os.environ.get("ZELLIJ_SESSION_NAME"):
                # Not running in a Zellij session
                # INFO: Could print hint about starting Zellij, but this is optional
                pass  # Silent: user might be in CI/CD

        # Track execution time
        start_time = time.time()

        # Initialize streaming buffer
        buffer = StreamingBuffer()

        # Generate log file path for real-time logging (if iteration provided)
        log_file_path = None
        log_file = None
        panel_session = None
        if iteration is not None:
            # Generate log file path (same pattern as FileSystemOutputLogger)
            from src.utils.repo import find_repo_root
            repo_root = find_repo_root(Path(working_dir))
            log_dir = repo_root / ".claude_supervisor"
            log_dir.mkdir(exist_ok=True)

            # Use provided timestamp or generate one (for consistency with FileSystemOutputLogger)
            if timestamp is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = str(log_dir / f"{timestamp}-iter{iteration:03d}.log")

            # Open log file for real-time writing (binary mode for unbuffered I/O)
            # Binary mode with buffering=0 ensures immediate writes that tail -f can see
            log_file = open(log_file_path, 'wb', buffering=0)  # Unbuffered binary mode

            # Create pane for live monitoring via PanelManager (if injected)
            # or fall back to embedded _create_zellij_pane (backwards compat)
            if self.panel_manager is not None:
                try:
                    # BR-010: Trust Protocol guarantees, no hasattr check
                    if self.panel_manager.is_available():
                        panel_session = self.panel_manager.create_pane(iteration, log_file_path)
                except Exception as e:
                    if self.feedback and hasattr(self.feedback, 'warning'):
                        self.feedback.warning(f"Failed to create pane: {e}")
            elif self.detector.is_available() and not self.config.disable_zellij:
                try:
                    self._create_zellij_pane(iteration, log_file_path)
                except Exception as e:
                    if self.feedback and hasattr(self.feedback, 'warning'):
                        self.feedback.warning(f"Failed to create Zellij pane: {e}")

        # Spawn subprocess with PIPE for all streams (stdin, stdout, stderr)
        # No PTY needed - PIPE is simpler and more reliable for claude --print
        try:
            process = self._spawn_process(working_dir)

            # Write prompt to stdin PIPE and close it (signals EOF)
            try:
                if process.stdin:
                    process.stdin.write(prompt)
                    process.stdin.close()
            except Exception as e:
                process.kill()
                raise RuntimeError(f"Failed to write prompt to stdin: {e}") from e

            try:
                # Capture streaming output from PIPE with timeout
                self._capture_streaming_output_pipe(buffer, process, timeout, start_time, log_file)

                # Drain any remaining output from PIPE
                self._drain_final_output_pipe(buffer, process, log_file)

                # Get exit code
                exit_code = process.returncode if process.returncode is not None else 0

            except KeyboardInterrupt:
                # Handle user interrupt gracefully
                self._handle_keyboard_interrupt(process)
                raise

            finally:
                # Always clean up resources
                buffer.cleanup()
                if log_file is not None:
                    try:
                        log_file.close()
                    except Exception:
                        pass  # Best effort cleanup

                # T018: Close panel pane if auto_close is enabled
                if panel_session is not None and self.panel_manager is not None:
                    if hasattr(self.config, 'auto_close_panes') and self.config.auto_close_panes:
                        try:
                            self.panel_manager.close_pane(panel_session)
                        except Exception:
                            pass  # Best effort cleanup

            # Calculate duration
            duration = time.time() - start_time

            # Get complete output
            complete_output = buffer.get_content()

            return RunResult(
                stdout=complete_output,
                stderr="",  # PTY combines stdout and stderr
                exit_code=exit_code,
                duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            raise RuntimeError(f"PTY execution failed after {duration:.1f}s: {e}") from e

    def _create_pty(self) -> tuple[int, int]:
        """Create PTY pair for subprocess communication.

        Returns:
            tuple of (master_fd, slave_fd)
        """
        master_fd, slave_fd = pty.openpty()

        # Set non-blocking mode for master FD
        import fcntl
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        return master_fd, slave_fd

    def _spawn_process(
        self,
        working_dir: str
    ) -> subprocess.Popen:  # type: ignore
        """Spawn Claude subprocess with PIPE for all streams.

        Args:
            working_dir: Working directory

        Returns:
            Running subprocess.Popen instance

        Note:
            - stdin, stdout, stderr: all PIPE (simpler and more reliable than PTY)
            - Prompt is written to stdin PIPE by parent after spawn
            - Output is read from stdout/stderr PIPE with select.select()
        """
        # BR-013: Check for sensitive environment variables and log warning
        env = os.environ.copy()
        sensitive_vars = [
            "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
            "GITHUB_TOKEN", "GH_TOKEN",
            "SSH_PRIVATE_KEY", "SSH_AUTH_SOCK",
        ]
        detected_sensitive = [var for var in sensitive_vars if var in env]

        if detected_sensitive and self.feedback:
            # Warn user that sensitive env vars will be inherited
            # This is intentional for Claude CLI to work, but user should be aware
            try:
                # Try to call feedback.info() if it exists
                if hasattr(self.feedback, "info"):
                    self.feedback.info(
                        f"⚠️  Sensitive environment variables detected: {', '.join(detected_sensitive)}. "
                        "These will be inherited by Claude subprocess for authentication. "
                        "Streaming logs may contain traces - review logs before sharing externally."
                    )
            except Exception:
                pass  # Best effort - don't fail if feedback is incompatible

        # Resolve command - expand alias if needed
        actual_command = self.claude_command
        alias_env_vars: dict[str, str] = {}

        # Try to expand alias (handles clauderock and similar patterns)
        # If expansion fails, use command as-is and let it fail naturally
        try:
            # Check if command is in PATH (not an alias)
            if not shutil.which(actual_command):
                # Not in PATH - might be an alias, try expanding
                alias_env_vars, actual_command = self._expand_alias(self.claude_command)
                # Merge alias env vars into subprocess environment
                env.update(alias_env_vars)
        except Exception:
            # Alias expansion failed - use original command
            # This allows both aliases and direct commands to work
            pass

        # TODO: Remove this workaround when clauderock alias is updated to use cross-region inference profile
        # AWS Bedrock Opus 4.5 requires cross-region inference profile for on-demand throughput
        # See: https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html
        # The model ID without 'us.' prefix fails with:
        #   "Invocation of model ID anthropic.claude-opus-4-5-20251101-v1:0 with on-demand throughput isn't supported"
        problematic_opus_model = "anthropic.claude-opus-4-5-20251101-v1:0"
        fixed_opus_model = "us.anthropic.claude-opus-4-5-20251101-v1:0"
        if env.get("ANTHROPIC_MODEL") == problematic_opus_model:
            env["ANTHROPIC_MODEL"] = fixed_opus_model

        # Use PIPE for ALL streams (same as subprocess_runner)
        # We'll read from stdout/stderr in real-time using select()
        # This is simpler and more reliable than PTY for claude --print
        user_shell = os.environ.get('SHELL', '/bin/bash')

        # Try to force unbuffered output using stdbuf if available
        # This helps Claude Code stream output incrementally
        stdbuf_command = "stdbuf -o0" if shutil.which("stdbuf") else ""
        full_command = f"{stdbuf_command} {actual_command} --print" if stdbuf_command else f"{actual_command} --print"

        process = subprocess.Popen(
            [user_shell, "-i", "-l", "-c", full_command],
            cwd=working_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )

        return process

    def _capture_streaming_output(
        self,
        master_fd: int,
        buffer: StreamingBuffer,
        process: subprocess.Popen,  # type: ignore
        timeout: int,
        start_time: float,
        log_file = None  # type: ignore
    ) -> None:
        """Capture streaming output using select.select() for non-blocking reads.

        Args:
            master_fd: Master end of PTY
            buffer: StreamingBuffer to accumulate output
            process: Running subprocess
            timeout: Max execution time in seconds
            start_time: Execution start timestamp
            log_file: Optional file handle for real-time logging

        Raises:
            TimeoutError: If execution exceeds timeout
        """
        while True:
            # Check if process has exited
            exit_code = process.poll()
            if exit_code is not None:
                break

            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                # Kill process and raise timeout
                self._handle_timeout(process, buffer, elapsed, timeout)
                return

            # Wait for data with 0.1s timeout
            ready, _, _ = select.select([master_fd], [], [], 0.1)

            if ready:
                try:
                    # Read data in 4KB chunks
                    data = os.read(master_fd, 4096)
                    if data:
                        decoded_data = data.decode('utf-8', errors='replace')
                        buffer.append(decoded_data)
                        # Write to log file for real-time monitoring (Zellij pane tails this)
                        # Binary unbuffered mode - writes are immediate, no flush needed
                        if log_file is not None:
                            log_file.write(data)  # Write raw bytes for immediate tail -f visibility
                except OSError:
                    # No data available (non-blocking read)
                    pass

    def _drain_final_output(
        self,
        master_fd: int,
        buffer: StreamingBuffer,
        log_file = None  # type: ignore
    ) -> None:
        """Drain any remaining output from PTY after process exits.

        Critical for completeness - ensures we capture all output.

        Args:
            master_fd: Master end of PTY
            buffer: StreamingBuffer to accumulate output
            log_file: Optional file handle for real-time logging
        """
        while True:
            try:
                data = os.read(master_fd, 4096)
                if not data:
                    break
                decoded_data = data.decode('utf-8', errors='replace')
                buffer.append(decoded_data)
                # Write to log file for completeness (binary mode, no flush needed)
                if log_file is not None:
                    log_file.write(data)  # Write raw bytes
            except OSError:
                # No more data available
                break

    def _capture_streaming_output_pipe(
        self,
        buffer: StreamingBuffer,
        process: subprocess.Popen,  # type: ignore
        timeout: int,
        start_time: float,
        log_file = None  # type: ignore
    ) -> None:
        """Capture streaming output from PIPE using select.select().

        Args:
            buffer: StreamingBuffer to accumulate output
            process: Running subprocess
            timeout: Max execution time in seconds
            start_time: Execution start timestamp
            log_file: Optional file handle for real-time logging

        Raises:
            TimeoutError: If execution exceeds timeout
        """
        # Get file descriptors for stdout and stderr
        stdout_fd = process.stdout.fileno() if process.stdout else None
        stderr_fd = process.stderr.fileno() if process.stderr else None

        fds = [fd for fd in [stdout_fd, stderr_fd] if fd is not None]

        while True:
            # Check if process has exited
            exit_code = process.poll()
            if exit_code is not None:
                break

            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                # Kill process and raise timeout
                self._handle_timeout(process, buffer, elapsed, timeout)
                return

            if not fds:
                # No file descriptors to read from
                break

            # Wait for data with 0.1s timeout
            ready, _, _ = select.select(fds, [], [], 0.1)

            for fd in ready:
                try:
                    # Read data in 4KB chunks
                    data = os.read(fd, 4096)
                    if data:
                        decoded_data = data.decode('utf-8', errors='replace')
                        buffer.append(decoded_data)
                        # Write to log file for real-time monitoring
                        if log_file is not None:
                            log_file.write(data)
                except OSError:
                    # No data available (non-blocking read)
                    pass

    def _drain_final_output_pipe(
        self,
        buffer: StreamingBuffer,
        process: subprocess.Popen,  # type: ignore
        log_file = None  # type: ignore
    ) -> None:
        """Drain any remaining output from PIPE after process exits.

        Critical for completeness - ensures we capture all output.

        Args:
            buffer: StreamingBuffer to accumulate output
            process: Completed subprocess
            log_file: Optional file handle for real-time logging
        """
        # Read remaining stdout
        if process.stdout:
            try:
                remaining_stdout = process.stdout.read()
                if remaining_stdout:
                    buffer.append(remaining_stdout)
                    if log_file is not None:
                        log_file.write(remaining_stdout.encode('utf-8'))
            except Exception:
                pass

        # Read remaining stderr
        if process.stderr:
            try:
                remaining_stderr = process.stderr.read()
                if remaining_stderr:
                    buffer.append(remaining_stderr)
                    if log_file is not None:
                        log_file.write(remaining_stderr.encode('utf-8'))
            except Exception:
                pass

    def _handle_timeout(
        self,
        process: subprocess.Popen,  # type: ignore
        buffer: StreamingBuffer,
        elapsed: float,
        timeout: int
    ) -> None:
        """Handle execution timeout with SIGTERM -> SIGKILL escalation.

        Args:
            process: Running subprocess
            buffer: StreamingBuffer with partial output
            elapsed: Elapsed time in seconds
            timeout: Timeout threshold (unused, kept for compatibility)
        """
        # Append timeout marker
        buffer.append(f"\n\n[TIMEOUT after {elapsed:.1f}s]")

        # Try graceful termination (SIGTERM)
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
            # BR-009: Process terminated gracefully, no need for SIGKILL
        except subprocess.TimeoutExpired:
            # BR-009 fix: Process didn't terminate after SIGTERM, escalate to SIGKILL
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=1)  # SIGKILL should be immediate
            except Exception:
                pass  # Best effort
        except Exception:
            # Other error (e.g., process already dead, pgid doesn't exist)
            pass  # Best effort

        # Set exit code to 124 (standard timeout code)
        process.returncode = 124

    def _handle_keyboard_interrupt(
        self,
        process: subprocess.Popen  # type: ignore
    ) -> None:
        """Handle user interrupt (Ctrl+C) with graceful cleanup.

        Args:
            process: Running subprocess
        """
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    pass  # Best effort

    def _create_zellij_pane(
        self,
        iteration: int,
        log_file_path: str
    ) -> None:
        """Create Zellij pane for live streaming display.

        Creates a new Zellij pane that tails the streaming log file.
        Handles pane naming, direction configuration, and auto-close behavior.

        Args:
            iteration: Current iteration number (for unique pane names)
            log_file_path: Path to streaming log file to tail

        Raises:
            subprocess.CalledProcessError: If pane creation fails
            RuntimeError: If Zellij command construction fails

        Example:
            ```python
            # Create pane showing iteration 3 logs
            runner._create_zellij_pane(iteration=3, log_file_path="/tmp/iter003.log")
            # Result: New pane named "Claude Worker PID-TIMESTAMP-3" tailing the log file
            ```
        """
        # T057: Generate unique pane name using PID and timestamp
        # Format: "Claude Worker {pid}-{timestamp}-{iteration}"
        # This ensures uniqueness even with concurrent supervisors
        pid = os.getpid()
        timestamp = int(time.time())

        # Use configured template with iteration placeholder
        # Default template: "Claude Worker {iteration}"
        # Enhanced for uniqueness: include PID and timestamp
        pane_name = f"Claude Worker {pid}-{timestamp}-{iteration}"

        # T060: Build Zellij command with pane direction configuration
        cmd = [
            "zellij",
            "action",
            "new-pane",
            "--name", pane_name,
            "--direction", self.config.pane_direction,  # down/right/left/up
        ]

        # T058: Add --close-on-exit flag if configured
        if self.config.auto_close_panes:
            cmd.append("--close-on-exit")

        # Launch tail command in the pane to follow streaming log
        # Note: Zellij can't write to panes after creation, so we launch
        # a full command that will continuously display the log content
        cmd.extend(["--", "tail", "-f", log_file_path])

        # T059: Execute with error handling
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # Re-raise with enhanced error message including stderr
            error_msg = f"Zellij pane creation failed (exit code {e.returncode})"
            if e.stderr:
                error_msg += f": {e.stderr.strip()}"
            raise RuntimeError(error_msg) from e

    def _cleanup_pty(
        self,
        master_fd: int,
        slave_fd: int
    ) -> None:
        """Clean up PTY file descriptors.

        Args:
            master_fd: Master end of PTY
            slave_fd: Slave end of PTY
        """
        try:
            os.close(master_fd)
        except Exception:
            pass  # Best effort

        try:
            os.close(slave_fd)
        except Exception:
            pass  # Best effort
