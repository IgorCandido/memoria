"""Subprocess-based Claude runner adapter."""
import os
import re
import shlex
import subprocess
import time
import shutil
from typing import Optional
from src.domain.entities import RunResult
from src.utils.shell import expand_alias


# MEDIUM-004: Extract magic numbers to constants
PROGRESS_TICK_INTERVAL_SECONDS = 5.0  # Show progress dot every 5 seconds
POLL_INTERVAL_SECONDS = 0.5  # LOW-003: Check process status every 500ms (reduced from 100ms for lower CPU usage)


class SubprocessClaudeRunner:
    """Execute Claude via subprocess, inheriting all environment variables.

    This adapter is configuration-agnostic: it works with ANY Claude CLI setup
    (AWS Bedrock, API keys, local LLMs) by inheriting os.environ from the parent process.
    """

    def __init__(
        self,
        claude_command: str = "claude",
        feedback: Optional[object] = None,
        panel_manager: Optional[object] = None,
    ):
        """Initialize Claude runner with configurable command.

        Args:
            claude_command: Claude CLI command to use (default: "claude")
                           Can be "clauderock" for company account, or any alias.
                           BR-027: Supports aliases by running through shell.
            feedback: Optional UserFeedback port for progress updates
            panel_manager: Optional PanelManager for pane lifecycle

        Raises:
            ValueError: If claude_command contains invalid characters (security check)
        """
        # BR-027: Validate claude_command format to prevent shell injection
        # Only allow alphanumeric, underscore, hyphen (safe for shell commands/aliases)
        # NOTE: We don't use shutil.which() because clauderock is an ALIAS, not a binary
        # Aliases are expanded by zsh -i -l, so we can't validate their existence beforehand
        if not re.match(r'^[a-zA-Z0-9_-]+$', claude_command):
            raise ValueError(
                f"Invalid claude_command format: '{claude_command}'. "
                f"Only alphanumeric characters, underscore, and hyphen are allowed. "
                f"This prevents shell injection attacks."
            )

        self.claude_command = claude_command
        self._feedback = feedback
        self.panel_manager = panel_manager

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
    ) -> RunResult:
        """Execute Claude with prompt in working directory.

        Args:
            prompt: Text prompt to send to Claude (can be multi-line)
            working_dir: Absolute path to directory to execute in (must exist)
            timeout: Max execution time in seconds (default: 3600 = 1 hour)

        Returns:
            RunResult with stdout, stderr, exit_code, duration

        Raises:
            TimeoutError: If execution exceeds timeout
            FileNotFoundError: If working_dir doesn't exist
            RuntimeError: If Claude CLI not available or execution fails
        """
        # Validate working directory exists
        if not os.path.exists(working_dir):
            raise FileNotFoundError(
                f"Working directory does not exist: {working_dir}"
            )

        if not os.path.isdir(working_dir):
            raise FileNotFoundError(
                f"Working directory is not a directory: {working_dir}"
            )

        # Validate prompt
        if not prompt:
            raise ValueError("prompt cannot be empty")

        # Validate timeout
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")

        # Measure execution duration
        start_time = time.time()

        # T020: Create log file and panel pane when iteration is provided
        panel_session = None
        if iteration is not None and self.panel_manager is not None:
            try:
                from pathlib import Path
                from datetime import datetime
                from src.utils.repo import find_repo_root
                repo_root = find_repo_root(Path(working_dir))
                log_dir = repo_root / ".claude_supervisor"
                log_dir.mkdir(exist_ok=True)
                if timestamp is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file_path = str(log_dir / f"{timestamp}-iter{iteration:03d}.log")
                Path(log_file_path).touch()
                # BR-010: Trust Protocol guarantees, no hasattr check needed
                if self.panel_manager.is_available():
                    panel_session = self.panel_manager.create_pane(iteration, log_file_path)
            except Exception:
                # BR-009: Cleanup log file if pane creation failed
                try:
                    Path(log_file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                # Panel creation failure is non-fatal

        # Track process for cleanup on KeyboardInterrupt (BR-026)
        process = None

        try:
            # Show spawning message
            if self._feedback:
                self._feedback.progress_start(f"⚡ Spawning Claude worker (command: {self.claude_command})...")

            # Execute Claude via subprocess
            # CRITICAL: Inherit os.environ for configuration agnosticism!
            # WHY SAFE: We inherit the full os.environ from the PARENT supervisor process,
            # which was launched by a trusted user. This enables ANY Claude configuration
            # (AWS Bedrock, API keys, local LLM) to work without code changes.
            # The worker Claude instance is sandboxed by:
            # 1. cwd restriction (can only affect working_dir files)
            # 2. timeout enforcement (killed after timeout)
            # 3. capture_output (no direct terminal access)
            # This is fundamentally different from web servers accepting env vars from
            # untrusted HTTP requests - here the env comes from our own trusted process.
            #
            # BR-026: Use Popen for explicit process cleanup on interrupts
            # subprocess.run() doesn't guarantee cleanup on KeyboardInterrupt
            #
            # HIGH-003: Use user's shell from $SHELL environment variable
            # BR-027: Run through interactive login shell to source rc files and get aliases
            # -i: interactive shell (enables aliases)
            # -l: login shell (sources profile/rc files)
            # Pass prompt via stdin to avoid shell escaping issues
            user_shell = os.environ.get('SHELL', '/bin/bash')  # Fallback to bash

            # Prepare environment - copy and potentially modify
            env = os.environ.copy()
            actual_command = self.claude_command

            # Try to expand alias (handles clauderock and similar patterns)
            try:
                if not shutil.which(actual_command):
                    alias_env_vars, actual_command = self._expand_alias(self.claude_command)
                    env.update(alias_env_vars)
            except Exception:
                # Alias expansion failed - use original command through shell
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

            # CRITICAL-002: Use shlex.quote() for additional safety (defense in depth)
            # Even though we validate format above, quote for extra protection
            safe_command = shlex.quote(actual_command)

            process = subprocess.Popen(
                [user_shell, "-i", "-l", "-c", f"{safe_command} --print"],
                cwd=working_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,  # Safe: copied from trusted parent process with model ID fix
                start_new_session=True  # Create process group for clean termination
            )

            # Show worker running with PID
            if self._feedback:
                self._feedback.progress_end(f" Worker running (PID: {process.pid})")
                self._feedback.progress_start("⏳ Working")

            # Wait for completion with timeout
            # BR-027: Send prompt via stdin to avoid shell escaping issues
            # Show progress dots periodically
            last_tick = time.time()

            # Send prompt to stdin
            if process.stdin:
                process.stdin.write(prompt)
                process.stdin.close()

            # MEDIUM-008: Track timeout warning to show only once
            timeout_warning_shown = False
            timeout_threshold = timeout * 0.9  # 90% of timeout

            # Poll for completion with periodic progress ticks
            while True:
                exit_code = process.poll()
                if exit_code is not None:
                    # Process completed
                    stdout = process.stdout.read() if process.stdout else ""
                    stderr = process.stderr.read() if process.stderr else ""
                    duration = time.time() - start_time

                    if self._feedback:
                        self._feedback.progress_end(f" ✅ Complete ({duration:.1f}s)")

                    return RunResult(
                        stdout=stdout,
                        stderr=stderr,
                        exit_code=exit_code,
                        duration=duration
                    )

                # MEDIUM-008: Warn when approaching timeout (90%)
                elapsed = time.time() - start_time
                if not timeout_warning_shown and elapsed >= timeout_threshold:
                    if self._feedback:
                        remaining = timeout - elapsed
                        self._feedback.warning(
                            f"⚠️  Approaching timeout: {remaining:.0f}s remaining "
                            f"({elapsed:.0f}s elapsed of {timeout}s timeout)"
                        )
                    timeout_warning_shown = True

                # Check timeout
                if elapsed > timeout:
                    raise subprocess.TimeoutExpired(
                        process.args,
                        timeout,
                        output=process.stdout.read() if process.stdout else None,
                        stderr=process.stderr.read() if process.stderr else None
                    )

                # Show progress tick periodically
                if self._feedback and time.time() - last_tick >= PROGRESS_TICK_INTERVAL_SECONDS:
                    self._feedback.progress_tick()
                    last_tick = time.time()

                # Sleep before next poll
                time.sleep(POLL_INTERVAL_SECONDS)

        except subprocess.TimeoutExpired as e:
            # BR-018: Capture partial output on timeout
            duration = time.time() - start_time

            if self._feedback:
                self._feedback.progress_end(f" ⏱️ Timeout ({duration:.1f}s)")

            # Kill process group (process must exist if timeout raised)
            if process is not None:
                import signal
                try:
                    # Graceful termination first (SIGTERM)
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=5)
                except Exception:
                    # Force kill if graceful termination fails (SIGKILL)
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:
                        pass  # Best effort cleanup

            # Capture partial output
            partial_stdout = ""
            partial_stderr = ""

            if hasattr(e, 'stdout') and e.stdout:
                partial_stdout = e.stdout.decode('utf-8') if isinstance(e.stdout, bytes) else e.stdout

            if hasattr(e, 'stderr') and e.stderr:
                partial_stderr = e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else e.stderr

            # Return RunResult with partial output and error indication
            return RunResult(
                stdout=partial_stdout + f"\n\n[TIMEOUT after {duration:.1f}s]",
                stderr=partial_stderr + f"\n[Process killed due to {timeout}s timeout]",
                exit_code=124,  # Standard timeout exit code
                duration=duration
            )

        except KeyboardInterrupt:
            # BR-026: Clean up subprocess on user interrupt
            if process and process.poll() is None:
                import signal
                try:
                    # Kill entire process group to catch any child processes
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=5)
                except Exception:
                    # Force kill if graceful termination fails
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:
                        pass  # Best effort cleanup
            # Re-raise to let CLI handle graceful shutdown
            raise

        except FileNotFoundError as e:
            # Claude CLI not found in PATH
            raise RuntimeError(
                "Claude CLI not found in PATH. Ensure 'claude' command is available. "
                "Install from: https://claude.ai/download"
            ) from e

        except Exception as e:
            # Unexpected error during execution - preserve original exception type
            duration = time.time() - start_time
            # Add execution context and re-raise with original type preserved
            raise type(e)(
                f"Claude execution failed after {duration:.1f}s: {e}"
            ) from e
