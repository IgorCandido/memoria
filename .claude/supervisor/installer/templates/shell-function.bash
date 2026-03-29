#!/usr/bin/env bash
# Claude Supervisor Shell Function for Bash/Zsh
# This file is sourced by the user's shell configuration
# Provides the `claude-supervisor` command for executing project-local supervisor

claude-supervisor() {
    # Check if .claude/ directory exists in current directory
    if [[ ! -d ".claude" ]]; then
        echo "Error: No .claude/ directory found in current directory" >&2
        echo "Run 'claude-supervisor-install init .' to initialize this project" >&2
        return 1
    fi

    # Check if supervisor executable exists
    local supervisor_path=".claude/supervisor/claude_supervisor.py"
    if [[ ! -f "$supervisor_path" ]]; then
        echo "Error: Supervisor not found in .claude/supervisor/" >&2
        echo "Try running: claude-supervisor-install init ." >&2
        return 1
    fi

    # Check Python availability
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 not found" >&2
        echo "Install Python 3.11+ and try again" >&2
        return 1
    fi

    # Execute supervisor with all arguments passed through
    python3 "$supervisor_path" "$@"
}
