"""Domain logic for supervisor session orchestration."""
from collections import deque
from src.domain.entities import RunResult, SessionResult, TaskCounts
from src.domain.exit_codes import EXIT_SUCCESS, EXIT_ERROR, EXIT_MAX_ITERATIONS, EXIT_STUCK_LOOP
from src.ports.claude_runner import ClaudeRunner
from src.ports.task_repository import TaskRepository
from src.ports.output_logger import OutputLogger
from src.ports.completion_verifier import CompletionVerifier
from src.ports.user_feedback import UserFeedback


class SupervisorSession:
    """Domain orchestrator for supervisor iteration loop.

    Pure domain logic with no I/O dependencies - all external interactions
    happen through injected port adapters.
    """

    def __init__(
        self,
        runner: ClaudeRunner,
        task_repo: TaskRepository,
        logger: OutputLogger,
        verifier: CompletionVerifier,
        feedback: UserFeedback,
        prompt: str,
        working_dir: str,
        max_iterations: int = 20
    ):
        """Initialize supervisor session with dependency injection.

        Args:
            runner: Adapter for executing Claude instances
            task_repo: Adapter for reading/parsing tasks.md
            logger: Adapter for logging iteration output
            verifier: Adapter for LLM completion verification
            feedback: Adapter for user feedback (info, warnings, progress)
            prompt: Prompt to send to each Claude instance
            working_dir: Directory containing the feature being supervised
            max_iterations: Maximum iterations before giving up (default: 20)
        """
        # Validate prompt is non-empty
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty or whitespace-only")

        self.runner = runner
        self.task_repo = task_repo
        self.logger = logger
        self.verifier = verifier
        self.feedback = feedback
        self.prompt = prompt
        self.working_dir = working_dir
        self.max_iterations = max_iterations

        # State tracking for stuck loop detection
        self._last_task_count: int | None = None
        self._stuck_iterations = 0

        # HIGH-009 FIX: Track consecutive LLM verification failures to prevent infinite loops
        self._llm_verification_failures = 0
        self.MAX_LLM_FAILURES = 3  # Give up after 3 consecutive LLM verification failures

        # FUTILE DEFERRAL DETECTION: Track unchecked tasks and repeated "complete" claims
        self._last_unchecked_count: int | None = None
        self._llm_said_complete_last_iteration = False
        self._futile_deferral_iterations = 0

    def run_until_complete(self) -> SessionResult:
        """Run Claude instances until work is complete or max iterations reached.

        Implements the core supervision loop:
        1. Execute Claude via runner
        2. Log output via logger
        3. Check completion via task_repo
        4. If ambiguous or stuck, fallback to verifier
        5. Repeat until complete or max iterations

        Returns:
            SessionResult with success status, iterations, exit code, and reason
        """
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Show iteration start with real-time feedback
            self.feedback.info(f"\n{'='*60}")
            self.feedback.info(f"🔄 Iteration {iteration}/{self.max_iterations}")
            self.feedback.info(f"{'='*60}")
            self.feedback.progress_start("🚀 Spawning Claude worker")

            # Generate timestamp ONCE for this iteration (used by both runner and logger)
            # This ensures real-time logs and final logs use the same filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Execute Claude instance
            import time
            start_time = time.time()
            try:
                # Show progress dots during execution
                result = self.runner.run(
                    prompt=self.prompt,
                    working_dir=self.working_dir,
                    timeout=3600,
                    iteration=iteration,  # Pass iteration for live monitoring (Zellij panes, etc.)
                    timestamp=timestamp   # Pass timestamp for consistent log file naming
                )
                elapsed = time.time() - start_time
                self.feedback.progress_end(f"✅ (completed in {elapsed:.1f}s)")
            except Exception as e:
                elapsed = time.time() - start_time
                self.feedback.progress_end(f"❌ (failed after {elapsed:.1f}s)")
                return SessionResult(
                    success=False,
                    iterations=iteration,
                    exit_code=EXIT_ERROR,
                    completion_reason=f"Claude execution failed: {e}"
                )

            # Log iteration output (reuse timestamp for consistent file naming)
            try:
                log_path = self.logger.log_iteration(iteration, result, self.working_dir, timestamp)
                self.feedback.info(f"💾 Saved log: {log_path}")

                # MEDIUM-005: Extract and log final outcome (last 10 lines of stdout)
                # MEDIUM-007: Use deque with maxlen to avoid copying entire stdout
                # This captures Claude's final response/message for debugging
                lines = deque(result.stdout.splitlines(), maxlen=10)
                final_outcome = '\n'.join(lines)
                outcome_path = self.logger.log_outcome(iteration, final_outcome, self.working_dir)
                self.feedback.info(f"📝 Saved outcome: {outcome_path}")
            except Exception as e:
                self.feedback.warning(f"Failed to save log: {e}")
                # Logging failures are non-critical; don't block supervision progress

            # Check completion via tasks.md
            try:
                content = self.task_repo.get_tasks_content(self.working_dir)
                task_counts = self.task_repo.parse_tasks(content)

                self.feedback.info(f"📋 Task Count: {task_counts.checked} checked, {task_counts.unchecked} unchecked, {task_counts.total} total")

                # FIXED LOGIC: Always use LLM verifier as PRIMARY completion check
                # Task count is SECONDARY validation only
                self.feedback.info("🔍 Checking completion with LLM verifier...")

                try:
                    llm_complete = self.verifier.verify_completion(result.stdout, task_counts)

                    if llm_complete:
                        self.feedback.info("✅ LLM Verifier: Work is COMPLETE")

                        # FUTILE DEFERRAL DETECTION: Check if worker is stuck in deferral loop
                        if not task_counts.is_complete:
                            # Tasks unchecked - check if this is a futile deferral loop
                            same_unchecked = (self._last_unchecked_count == task_counts.unchecked)
                            llm_said_complete_before = self._llm_said_complete_last_iteration

                            if same_unchecked and llm_said_complete_before:
                                # FUTILE DEFERRAL LOOP DETECTED
                                self._futile_deferral_iterations += 1
                                self.feedback.warning(
                                    f"⚠️  FUTILE DEFERRAL LOOP DETECTED (iteration {self._futile_deferral_iterations}): "
                                    f"LLM says 'complete' but {task_counts.unchecked} tasks remain unchecked "
                                    f"(same as last iteration). Worker is re-justifying the same deferrals."
                                )

                                if self._futile_deferral_iterations >= 2:
                                    # Worker has claimed "complete with deferrals" twice in a row
                                    # Nothing will change - exit to prevent waste
                                    return SessionResult(
                                        success=False,
                                        iterations=iteration,
                                        exit_code=EXIT_STUCK_LOOP,
                                        completion_reason=(
                                            f"Futile deferral loop: Worker claims 'complete' with {task_counts.unchecked} "
                                            f"deferred tasks for {self._futile_deferral_iterations} consecutive iterations. "
                                            f"Same deferrals, no progress possible. Review CLAUDE.md deferral policy."
                                        )
                                    )

                                # First occurrence - warn and continue
                                self.feedback.info(
                                    "📋 Continuing one more iteration to verify if worker can make progress. "
                                    "If same deferrals next iteration, will exit."
                                )
                                self._last_unchecked_count = task_counts.unchecked
                                self._llm_said_complete_last_iteration = True
                            else:
                                # Different unchecked count or first time seeing "complete" with deferrals
                                self.feedback.warning(
                                    f"⚠️  Task Count Mismatch: LLM says complete but {task_counts.unchecked} tasks unchecked. "
                                    f"Worker may have deferred non-blocking tasks. "
                                    f"Continuing to verify if progress is possible."
                                )
                                # Track state for next iteration
                                self._last_unchecked_count = task_counts.unchecked
                                self._llm_said_complete_last_iteration = True
                                self._futile_deferral_iterations = 0  # Reset counter on first occurrence
                        else:
                            # All tasks checked - truly complete
                            self._llm_said_complete_last_iteration = False
                            self._last_unchecked_count = None
                            self._futile_deferral_iterations = 0

                        # Reset failure counter on LLM success
                        self._llm_verification_failures = 0

                        # Only return success if ALL tasks checked
                        if task_counts.is_complete:
                            return SessionResult(
                                success=True,
                                iterations=iteration,
                                exit_code=EXIT_SUCCESS,
                                completion_reason=f"All tasks complete after {iteration} iterations (LLM verified)"
                            )
                        # else: Continue to next iteration to verify progress
                    else:
                        self.feedback.info("🔄 LLM Verifier: Work is NOT complete, continuing...")

                        # Reset deferral tracking when LLM says not complete
                        self._llm_said_complete_last_iteration = False
                        self._last_unchecked_count = task_counts.unchecked
                        self._futile_deferral_iterations = 0

                        # Track consecutive failures to detect infinite loops
                        self._llm_verification_failures += 1

                        if self._llm_verification_failures >= self.MAX_LLM_FAILURES:
                            return SessionResult(
                                success=False,
                                iterations=iteration,
                                exit_code=EXIT_STUCK_LOOP,
                                completion_reason=f"Stuck in loop: LLM verification failed {self._llm_verification_failures} consecutive times. Unable to make progress."
                            )

                        # Check for stuck loop (same task count)
                        if self._detect_stuck_loop(task_counts.total):
                            self.feedback.warning(f"⚠️  Stuck Loop: Same task count ({task_counts.total}) for {self._stuck_iterations} iterations")
                        else:
                            # Reset failure counter when making progress
                            self._llm_verification_failures = 0
                            self.feedback.info(f"📈 Progress: Task count changed, resetting failure counter")

                        self.feedback.info(f"⏳ Continuing: {task_counts.unchecked} unchecked tasks remaining (verification {self._llm_verification_failures}/{self.MAX_LLM_FAILURES})")

                except Exception as e:
                    self.feedback.warning(f"❌ LLM verification error: {e}")
                    self.feedback.info("↩️  Fallback: Using task count as completion check")

                    # Fallback to task count if LLM fails
                    if task_counts.is_complete:
                        return SessionResult(
                            success=True,
                            iterations=iteration,
                            exit_code=EXIT_SUCCESS,
                            completion_reason=f"All {task_counts.total} tasks complete (LLM failed, used task count)"
                        )
                    else:
                        self.feedback.progress(f"⏳ Still {task_counts.unchecked} unchecked tasks remaining")

            except FileNotFoundError:
                # tasks.md missing - fallback to LLM verification
                self.feedback.warning("tasks.md not found, falling back to LLM verification...")

                try:
                    if self.verifier.verify_completion(result.stdout, None):
                        return SessionResult(
                            success=True,
                            iterations=iteration,
                            exit_code=EXIT_SUCCESS,
                            completion_reason=f"Work complete after {iteration} iterations (no tasks.md, LLM verified)"
                        )
                    else:
                        self.feedback.progress("⏳ LLM says not complete, continuing...")
                except Exception as e:
                    self.feedback.warning(f"LLM verification failed: {e}")
                    # Continue to next iteration

            except Exception as e:
                self.feedback.warning(f"Error checking completion: {e}")
                # Continue to next iteration despite error

            # Continue to next iteration
            self.feedback.info("🔄 Continuing with next iteration...\n")

        # Max iterations reached
        return SessionResult(
            success=False,
            iterations=iteration,
            exit_code=EXIT_MAX_ITERATIONS,
            completion_reason=f"Max iterations ({self.max_iterations}) reached without completion"
        )

    def _detect_stuck_loop(self, current_count: int) -> bool:
        """Detect if the supervisor is stuck in a loop (same task count for 3+ iterations).

        Args:
            current_count: Current total task count

        Returns:
            True if stuck (same count for 3+ iterations), False otherwise
        """
        if self._last_task_count is None:
            # First iteration
            self._last_task_count = current_count
            self._stuck_iterations = 1
            return False

        if current_count == self._last_task_count:
            # Same count as last iteration
            self._stuck_iterations += 1
            return self._stuck_iterations >= 3
        else:
            # Count changed - reset stuck detection
            self._last_task_count = current_count
            self._stuck_iterations = 1
            return False
