"""LLM-based completion verifier adapter."""
import os
import shutil
import subprocess
from typing import Tuple
from src.domain.entities import TaskCounts
from src.domain.prompts import VERIFICATION_PROMPT
from src.ports.user_feedback import UserFeedback


def _build_claude_env() -> dict[str, str]:
    """Build environment dictionary for Claude CLI execution (BR-010).

    SECURITY: Explicit allowlist approach - only inherit specific env vars needed for Claude.
    This prevents potential environment variable injection attacks from untrusted parent processes.

    We inherit:
    1. System essentials (PATH, HOME) - required for basic execution
    2. AWS Bedrock credentials - for Bedrock-backed Claude instances
    3. Anthropic API key - for API-backed Claude instances
    4. Shell disablement - prevent interactive shell exploits

    Empty values are filtered out to avoid passing undefined configuration to subprocess.

    Returns:
        Dictionary of environment variables for Claude subprocess (empty values removed)
    """
    env = {
        # Essential system paths
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
        # AWS Bedrock configuration (if using AWS)
        "CLAUDE_CODE_USE_BEDROCK": os.environ.get("CLAUDE_CODE_USE_BEDROCK", ""),
        "AWS_REGION": os.environ.get("AWS_REGION", ""),
        "AWS_PROFILE": os.environ.get("AWS_PROFILE", ""),
        "ANTHROPIC_BEDROCK_SONNET_MODEL_ID": os.environ.get("ANTHROPIC_BEDROCK_SONNET_MODEL_ID", ""),
        "ANTHROPIC_BEDROCK_HAIKU_MODEL_ID": os.environ.get("ANTHROPIC_BEDROCK_HAIKU_MODEL_ID", ""),
        "ANTHROPIC_SMALL_FAST_MODEL": os.environ.get("ANTHROPIC_SMALL_FAST_MODEL", ""),
        "ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION": os.environ.get("ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION", ""),
        # Anthropic API key (if using API)
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        # Disable interactive shell features to prevent injection attacks
        "ZDOTDIR": "/dev/null",
        "BASH_ENV": "",
        "ENV": "",
        "CLAUDE_SUPERVISOR": "1",
    }

    # Remove empty environment variables
    return {k: v for k, v in env.items() if v}


class LLMCompletionVerifier:
    """Verify work completion by asking an LLM to analyze Claude's output.

    Used as fallback when tasks.md is missing or task counts are ambiguous.
    """

    def __init__(self, timeout: int = 360, feedback: UserFeedback | None = None, claude_command: str = "claude"):
        """Initialize LLM verifier.

        Args:
            timeout: Timeout for LLM verification in seconds (default: 360 = 6 minutes)
            feedback: Optional UserFeedback port for warnings (e.g., ambiguous responses)
            claude_command: Claude CLI command to use (default: "claude", should match supervisor config)
        """
        self.timeout = timeout
        self._feedback = feedback
        self.claude_command = claude_command

    def _expand_alias(self, alias_name: str) -> Tuple[dict[str, str], str]:
        """Expand shell alias to environment variables and actual command.

        Args:
            alias_name: Name of the alias to expand

        Returns:
            (env_vars_dict, actual_command)

        Raises:
            ValueError: If alias not found or format unsupported
        """
        user_shell = os.environ.get('SHELL', '/bin/bash')

        try:
            result = subprocess.run(
                [user_shell, "-i", "-c", f"type {alias_name}"],
                capture_output=True,
                text=True,
                timeout=5
            )
        except subprocess.TimeoutExpired:
            raise ValueError(f"Timeout while checking alias '{alias_name}'")

        if result.returncode != 0:
            raise ValueError(f"Alias '{alias_name}' not found in shell")

        output = result.stdout.strip()

        if "is an alias for " in output:
            alias_content = output.split("is an alias for ", 1)[1]
        elif "is aliased to " in output:
            alias_content = output.split("is aliased to ", 1)[1]
            alias_content = alias_content.strip("`'\"")
        else:
            raise ValueError(f"Unexpected alias format: {output}")

        parts = alias_content.split()
        env_vars: dict[str, str] = {}
        command: str | None = None

        for part in parts:
            if '=' in part and not part.startswith('-'):
                key, value = part.split('=', 1)
                env_vars[key] = value
            else:
                command = part
                break

        if not command:
            raise ValueError(f"Could not extract command from alias: {alias_content}")

        return env_vars, command

    def verify_completion(
        self,
        output: str,
        task_counts: TaskCounts | None
    ) -> bool:
        """Verify if work is complete by analyzing Claude's output.

        Truncates output to first 10k + last 40k chars if > 50k total.
        This preserves both context (task list) and summary (completion status).

        Args:
            output: stdout from Claude execution
            task_counts: TaskCounts from tasks.md, or None if not available

        Returns:
            True if work is complete, False otherwise

        Raises:
            RuntimeError: If LLM verification fails or times out
        """
        # Truncate output intelligently to avoid overwhelming the LLM
        # Keep first 10k chars (context/task list) + last 40k chars (summary/completion)
        # Optimization: Only create new string if truncation needed
        output_length = len(output)
        if output_length > 50000:
            # Build truncated string without creating intermediate copies
            output_sample = (
                output[:10000] +
                "\n\n...[middle truncated]...\n\n" +
                output[-40000:]
            )
        else:
            output_sample = output

        # Format verification prompt with truncated output
        verification_prompt = VERIFICATION_PROMPT.format(output_sample)

        # FIX: Run through zsh shell like worker to get alias expansion
        # Use same claude_command as worker to ensure consistent credentials
        # Execute verification via Claude CLI
        try:
            # Prepare environment with alias expansion and model ID fix
            env = os.environ.copy()
            actual_command = self.claude_command

            try:
                if not shutil.which(actual_command):
                    alias_env_vars, actual_command = self._expand_alias(self.claude_command)
                    env.update(alias_env_vars)
            except Exception:
                pass  # Alias expansion failed - use original command

            # TODO: Remove this workaround when clauderock alias is updated to use cross-region inference profile
            # AWS Bedrock Opus 4.5 requires cross-region inference profile for on-demand throughput
            # See: https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html
            problematic_opus_model = "anthropic.claude-opus-4-5-20251101-v1:0"
            fixed_opus_model = "us.anthropic.claude-opus-4-5-20251101-v1:0"
            if env.get("ANTHROPIC_MODEL") == problematic_opus_model:
                env["ANTHROPIC_MODEL"] = fixed_opus_model

            result = subprocess.run(
                ["/bin/zsh", "-i", "-l", "-c", f"{actual_command} --print"],
                input=verification_prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,  # Use modified environment with model ID fix
                start_new_session=True  # Create process group for clean termination
            )

            # Parse YES/NO response with word boundary matching
            # Use regex to ensure we match whole words only, not substrings
            # This prevents false positives like "yesterday" matching "yes"
            import re
            output_lower = result.stdout.strip().lower()

            # Match whole word "yes" or "no" with word boundaries
            if re.search(r'\byes\b', output_lower):
                return True
            elif re.search(r'\bno\b', output_lower):
                return False
            else:
                # Ambiguous response - be conservative and say not complete
                if self._feedback:
                    self._feedback.warning(
                        f"Ambiguous verification response: {result.stdout[:200]}"
                    )
                return False

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"LLM verification timed out after {self.timeout}s"
            ) from e

        except FileNotFoundError as e:
            raise RuntimeError(
                "Claude CLI not found in PATH. Cannot perform LLM verification."
            ) from e

        except Exception as e:
            raise RuntimeError(
                f"LLM verification failed: {e}"
            ) from e
