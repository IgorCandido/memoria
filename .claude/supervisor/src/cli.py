"""CLI entry point for Claude Supervisor v0.2."""
import json
import sys
import os
import argparse
from pathlib import Path
from typing import Optional

# Import domain
from src.domain.supervisor_session import SupervisorSession
from src.domain.entities import PanelConfig
from src.domain.exit_codes import (
    EXIT_SUCCESS,
    EXIT_INVALID_ARGS,
    EXIT_WORKTREE_NOT_FOUND,
    EXIT_INTERRUPTED
)

# Import production adapters
from src.adapters.subprocess_runner import SubprocessClaudeRunner
from src.adapters.zellij_runner import ZellijClaudeRunner, ZellijDetector, ZellijConfig
from src.adapters.null_panel import NullPanelManager
from src.adapters.tmux_panel import TmuxPanelManager
from src.adapters.zellij_panel import ZellijPanelManager
from src.adapters.filesystem_tasks import FileSystemTaskRepository
from src.adapters.filesystem_logger import FileSystemOutputLogger
from src.adapters.llm_verifier import LLMCompletionVerifier
from src.adapters.console_feedback import ConsoleFeedback

# MEDIUM-006: Import shared utilities
from src.utils.repo import find_repo_root


def load_prompt_from_file(prompt_file: Path) -> str:
    """Load worker prompt from file.

    Args:
        prompt_file: Path to prompt.md file

    Returns:
        Prompt content as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If prompt content is invalid
    """
    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_file}. "
            f"Create prompt.md in repository root with worker prompt."
        )

    try:
        content = prompt_file.read_text(encoding="utf-8")

        # Validate prompt content (BR-023)
        if not content.strip():
            raise ValueError(f"Prompt file is empty: {prompt_file}")

        # Check size (max 100KB for reasonable prompt length)
        MAX_PROMPT_SIZE = 100 * 1024  # 100KB
        if len(content) > MAX_PROMPT_SIZE:
            raise ValueError(
                f"Prompt file too large: {len(content)} bytes (max {MAX_PROMPT_SIZE}). "
                f"Consider splitting into multiple files or reducing verbosity."
            )

        # Check for problematic control characters (except newlines, tabs, carriage returns)
        import string
        allowed_chars = set(string.printable) | {'\n', '\r', '\t'}
        problematic_chars = [c for c in content if c not in allowed_chars]
        if problematic_chars:
            raise ValueError(
                f"Prompt contains {len(problematic_chars)} non-printable control characters. "
                f"Remove binary data or invalid Unicode."
            )

        # HIGH-006: Check for dangerous command patterns
        # Note: This is defense-in-depth - Claude is instructed NOT to run destructive commands,
        # but we validate prompt content to prevent injection attempts
        dangerous_patterns = [
            ('rm -rf /', 'recursive deletion from root'),
            ('rm -rf ~', 'recursive deletion from home'),
            ('sudo rm', 'elevated deletion'),
            ('curl | bash', 'piped execution'),
            ('curl | sh', 'piped execution'),
            ('wget | bash', 'piped execution'),
            ('dd if=', 'disk operations'),
            ('mkfs.', 'filesystem formatting'),
            (':(){ :|:& };:', 'fork bomb'),
        ]

        content_lower = content.lower()
        for pattern, description in dangerous_patterns:
            if pattern in content_lower:
                raise ValueError(
                    f"Prompt contains dangerous pattern '{pattern}' ({description}). "
                    f"Review prompt.md for malicious content or remove this pattern."
                )

        return content
    except Exception as e:
        raise RuntimeError(f"Failed to read prompt file: {e}") from e


# MEDIUM-006: find_repo_root moved to src/utils/repo.py to avoid duplication


def validate_working_dir(raw_path: Path) -> Path:
    """Validate and resolve working directory path.

    Args:
        raw_path: User-provided working directory path

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is invalid or unsafe
    """
    # Check for path traversal attempts
    if ".." in raw_path.parts:
        raise ValueError(
            f"Invalid path: Path traversal detected ('..') in {raw_path}. "
            f"Use absolute paths or paths without '..' components."
        )

    working_dir = raw_path.resolve()

    if not working_dir.exists():
        raise FileNotFoundError(f"Working directory does not exist: {working_dir}")

    if not working_dir.is_dir():
        raise ValueError(f"Path is not a directory: {working_dir}")

    # Expanded sensitive directory list (system dirs + home directory root)
    import os
    home_dir = Path.home()
    sensitive_dirs = [
        "/etc", "/var", "/System", "/usr", "/bin", "/sbin", "/", "/root", "/boot",
        "/dev", "/proc", "/sys", "/tmp",  # Additional system directories
        str(home_dir)  # Home directory root (e.g., /Users/username)
    ]

    # Check if working_dir is directly in a sensitive directory (not subdirectories)
    working_dir_str = str(working_dir)
    for sensitive in sensitive_dirs:
        if working_dir_str == sensitive:
            raise ValueError(
                f"Security risk: Cannot run supervisor directly in sensitive directory: {working_dir}. "
                f"Create a subdirectory for your project instead."
            )

    # Check for symlinks to sensitive system directories
    if working_dir.is_symlink():
        target = working_dir.readlink()
        for sensitive in sensitive_dirs:
            if str(target).startswith(sensitive + "/") or str(target) == sensitive:
                raise ValueError(
                    f"Security risk: Working directory is a symlink to sensitive directory: {target}. "
                    f"Supervisor cannot run in system directories."
                )

    return working_dir


def read_manifest_panel_manager(repo_root: Path) -> Optional[str]:
    """Read panel_manager field from .claude/manifest.json.

    Args:
        repo_root: Repository root directory

    Returns:
        panel_manager string ("tmux", "zellij", "none") or None if field absent or file missing
    """
    manifest_path = repo_root / ".claude" / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        content = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(content)
        return manifest.get("panel_manager")
    except (json.JSONDecodeError, OSError):
        return None


def create_panel_manager(
    manifest_value: Optional[str],
    panel_config: PanelConfig,
) -> tuple[object, str]:
    """Create the appropriate PanelManager based on manifest and availability.

    Selection priority chain:
    1. Manifest panel_manager field (explicit user choice)
    2. ZellijDetector auto-detection (backwards compat for old manifests)
    3. NullPanelManager (universal fallback)

    Within step 1, if the configured manager is unavailable at runtime,
    falls back to NullPanelManager with a warning.

    Args:
        manifest_value: Value from manifest.json panel_manager field (or None)
        panel_config: PanelConfig for adapter construction

    Returns:
        Tuple of (panel_manager_instance, description_string)
    """
    if manifest_value is not None:
        # Explicit user choice from manifest
        if manifest_value == "tmux":
            mgr = TmuxPanelManager(config=panel_config)
            if mgr.is_available():
                return mgr, "tmux (from manifest)"
            else:
                print("⚠️  Configured panel manager 'tmux' is not available, falling back to subprocess-only mode")
                return NullPanelManager(), "none (tmux unavailable)"

        elif manifest_value == "zellij":
            detector = ZellijDetector()
            mgr = ZellijPanelManager(config=panel_config, detector=detector)
            if mgr.is_available():
                return mgr, "zellij (from manifest)"
            else:
                print("⚠️  Configured panel manager 'zellij' is not available, falling back to subprocess-only mode")
                return NullPanelManager(), "none (zellij unavailable)"

        elif manifest_value == "none":
            return NullPanelManager(), "none (from manifest)"

        else:
            print(f"⚠️  Unknown panel_manager value '{manifest_value}' in manifest, falling back to auto-detect")
            # Fall through to auto-detection

    # No manifest field or unknown value — auto-detect (backwards compat)
    detector = ZellijDetector()
    if detector.is_available():
        mgr = ZellijPanelManager(config=panel_config, detector=detector)
        return mgr, "zellij (auto-detected)"

    return NullPanelManager(), "none (no multiplexer detected)"


def main():
    """CLI entry point with dependency injection."""
    # Parse arguments (BR-027: Add --claude-command flag)
    parser = argparse.ArgumentParser(
        description="Claude Code Instance Supervisor v0.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python claude_supervisor.py .                              # Uses clauderock (company account)
  python claude_supervisor.py --claude-command claude .      # Override to use personal account
  CLAUDE_SUPERVISOR_COMMAND=claude python claude_supervisor.py .
        """
    )
    parser.add_argument(
        "working_dir",
        type=str,
        help="Path to working directory (e.g., '.' or './specs/003-cli-installer')"
    )
    parser.add_argument(
        "--claude-command",
        type=str,
        default=os.environ.get("CLAUDE_SUPERVISOR_COMMAND", "clauderock"),
        help="Claude CLI command to use (default: 'clauderock', env: CLAUDE_SUPERVISOR_COMMAND)"
    )

    args = parser.parse_args()
    raw_path = Path(args.working_dir)
    claude_command = args.claude_command

    # Validate working directory
    try:
        working_dir = validate_working_dir(raw_path)
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}")
        sys.exit(EXIT_WORKTREE_NOT_FOUND)

    # Load worker prompt
    # Find repository root by looking for .git directory
    repo_root = find_repo_root(working_dir)
    prompt_file = repo_root / "prompt.md"
    prompt = None

    # Priority: repo root prompt.md > .claude/supervisor/prompt.md > embedded default
    if prompt_file.exists():
        try:
            prompt = load_prompt_from_file(prompt_file)
        except Exception as e:
            print(f"❌ {e}")
            sys.exit(EXIT_INVALID_ARGS)
    else:
        default_prompt_file = repo_root / ".claude" / "supervisor" / "prompt.md"
        if default_prompt_file.exists():
            try:
                prompt = load_prompt_from_file(default_prompt_file)
                print(f"ℹ️  Using prompt from .claude/supervisor/prompt.md")
            except Exception as e:
                print(f"❌ {e}")
                sys.exit(EXIT_INVALID_ARGS)
        else:
            from src.domain.prompts import DEFAULT_WORKER_PROMPT
            prompt = DEFAULT_WORKER_PROMPT
            print(f"ℹ️  Using built-in default prompt (no prompt.md found)")

    # Display banner with log directory location (T074e)
    log_dir = repo_root / ".claude_supervisor"
    manifest_panel_display = read_manifest_panel_manager(repo_root) or "auto-detect"
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║          Claude Code Instance Supervisor v0.2             ║
║          (Hexagonal Architecture)                         ║
╚═══════════════════════════════════════════════════════════╝

📁 Working Directory: {working_dir}
🎯 Goal: Complete all tasks in speckit tasks.md
🔄 Strategy: Restart on context limit until done
🔧 Claude Command: {claude_command}
🖥️  Panel Manager: {manifest_panel_display}
💾 Logs: {log_dir}/
    """)

    # Dependency injection: create production adapters
    # Create feedback first so it can be injected into other adapters
    feedback = ConsoleFeedback()

    # T014-T016: Read manifest and create PanelManager
    manifest_panel_manager = read_manifest_panel_manager(repo_root)
    panel_config = PanelConfig.from_env()
    panel_manager, panel_desc = create_panel_manager(manifest_panel_manager, panel_config)

    # Choose runner based on Zellij availability (runner selection unchanged)
    # PanelManager is injected into whichever runner is selected
    detector = ZellijDetector()
    if detector.is_available():
        config = ZellijConfig.from_env()
        runner = ZellijClaudeRunner(
            config=config,
            detector=detector,
            claude_command=claude_command,
            feedback=feedback,
            panel_manager=panel_manager,
        )
        print(f"✨ Zellij detected - using streaming capture | Panel: {panel_desc}")
    else:
        runner = SubprocessClaudeRunner(claude_command=claude_command, feedback=feedback, panel_manager=panel_manager)
        print(f"📝 Using standard subprocess runner | Panel: {panel_desc}")

    task_repo = FileSystemTaskRepository(feedback=feedback)
    logger = FileSystemOutputLogger()
    verifier = LLMCompletionVerifier(timeout=360, feedback=feedback, claude_command=claude_command)

    # Create supervisor session with injected dependencies
    # MEDIUM-001: Pass working_dir to constructor to reduce coupling
    session = SupervisorSession(
        runner=runner,
        task_repo=task_repo,
        logger=logger,
        verifier=verifier,
        feedback=feedback,
        prompt=prompt,
        working_dir=str(working_dir),
        max_iterations=20
    )

    # Run until complete
    try:
        result = session.run_until_complete()

        if result.success:
            print("\n" + "="*60)
            print("🎉 WORK COMPLETE!")
            print(f"✅ {result.completion_reason}")
            print("="*60 + "\n")
        else:
            print("\n" + "="*60)
            print("⚠️  SUPERVISION STOPPED")
            print(f"❌ {result.completion_reason}")
            print("="*60 + "\n")

        sys.exit(result.exit_code)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user (Ctrl+C)")
        print(f"💾 Logs saved in {working_dir}/.claude_supervisor/")
        sys.exit(EXIT_INTERRUPTED)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
