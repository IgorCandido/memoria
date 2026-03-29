"""Shell utilities for alias expansion.

Shared by SubprocessClaudeRunner and ZellijClaudeRunner to avoid duplication.
"""
import os
import subprocess
from typing import Tuple


def expand_alias(alias_name: str) -> Tuple[dict[str, str], str]:
    """Expand shell alias to environment variables and actual command.

    Handles simple aliases of the form: VAR1=val1 VAR2=val2 ... command

    Args:
        alias_name: Name of the alias to expand

    Returns:
        (env_vars_dict, actual_command)

    Raises:
        ValueError: If alias not found or format unsupported
        subprocess.TimeoutExpired: If shell command times out

    Example:
        >>> env, cmd = expand_alias("clauderock")
        >>> env
        {'CLAUDE_CODE_USE_BEDROCK': '1', 'AWS_REGION': 'us-west-2', ...}
        >>> cmd
        'claude'
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

    # Parse output
    # Zsh: "clauderock is an alias for ..."
    # Bash: "clauderock is aliased to `...'"
    output = result.stdout.strip()

    if "is an alias for " in output:
        alias_content = output.split("is an alias for ", 1)[1]
    elif "is aliased to " in output:
        alias_content = output.split("is aliased to ", 1)[1]
        alias_content = alias_content.strip("`'\"")
    else:
        raise ValueError(f"Unexpected alias format: {output}")

    # Parse: VAR1=val1 VAR2=val2 ... COMMAND
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
