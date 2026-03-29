"""Port interface for verifying work completion via LLM analysis."""
from typing import Protocol
from src.domain.entities import TaskCounts


class CompletionVerifier(Protocol):
    """Port interface for verifying work completion via LLM analysis.

    Used as fallback when tasks.md is missing or task counts are ambiguous.

    Adapters implementing this protocol can use different verification strategies:
    - LLMCompletionVerifier: Asks Claude via subprocess if work is complete
    - AlwaysTrueVerifier: Always returns True (testing)
    - AlwaysFalseVerifier: Always returns False (testing)
    """

    def verify_completion(
        self,
        output: str,
        task_counts: TaskCounts | None
    ) -> bool:
        """Verify if work is complete by analyzing Claude's output.

        Args:
            output: stdout from Claude execution
            task_counts: TaskCounts from tasks.md, or None if not available

        Returns:
            True if work is complete, False otherwise

        Raises:
            RuntimeError: If LLM verification fails or times out
        """
        ...
