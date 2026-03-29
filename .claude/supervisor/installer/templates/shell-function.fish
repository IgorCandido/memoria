# Claude Supervisor Shell Function for Fish
# This file is sourced by the user's fish configuration
# Provides the `claude-supervisor` command for executing project-local supervisor

function claude-supervisor --description "Execute Claude Supervisor in current project"
    # Check if .claude/ directory exists in current directory
    if not test -d ".claude"
        echo "Error: No .claude/ directory found in current directory" >&2
        echo "Run 'claude-supervisor-install init .' to initialize this project" >&2
        return 1
    end

    # Check if supervisor executable exists
    set -l supervisor_path ".claude/supervisor/claude_supervisor.py"
    if not test -f "$supervisor_path"
        echo "Error: Supervisor not found in .claude/supervisor/" >&2
        echo "Try running: claude-supervisor-install init ." >&2
        return 1
    end

    # Check Python availability
    if not command -v python3 &> /dev/null
        echo "Error: Python 3 not found" >&2
        echo "Install Python 3.11+ and try again" >&2
        return 1
    end

    # Execute supervisor with all arguments passed through
    python3 $supervisor_path $argv
end
