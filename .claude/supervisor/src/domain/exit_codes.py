"""Shared exit codes for supervisor v0.2 (matching v0.1 for backward compatibility).

These codes are used across CLI, domain logic, and error handling to communicate
execution outcomes to the shell or parent process.
"""

# Success codes
EXIT_SUCCESS = 0  # All tasks completed successfully

# Error codes
EXIT_ERROR = 1  # General error (Claude execution failed, unexpected exception)
EXIT_INVALID_ARGS = 2  # Invalid command-line arguments
EXIT_WORKTREE_NOT_FOUND = 3  # Worktree path doesn't exist or is invalid
EXIT_MAX_ITERATIONS = 4  # Maximum iterations reached without completion
EXIT_STUCK_LOOP = 4  # Stuck in loop (same task count for 3+ iterations)
EXIT_VERIFICATION_FAILURE = 5  # LLM verification failed after retry (future)

# Interrupt codes
EXIT_INTERRUPTED = 130  # User interrupted execution (SIGINT/Ctrl+C)
