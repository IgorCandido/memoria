"""ANSI escape sequence handling utility for dual logging."""
import re
from typing import Tuple


class ANSIHandler:
    """Utility class for handling ANSI escape sequences in terminal output.

    This class provides methods to strip or preserve ANSI codes for dual logging:
    - Streaming logs preserve ANSI codes for rich terminal display
    - Stdout-only logs strip ANSI codes for clean parsing by automation

    Supports all major ANSI sequence types:
    - SGR (Select Graphic Rendition): Colors, bold, italic, etc.
    - Cursor movement: Up, down, left, right, position
    - Erase sequences: Clear line, clear screen
    - 256-color and RGB/truecolor sequences
    - OSC (Operating System Command) sequences

    Usage:
        ```python
        handler = ANSIHandler()

        # Strip ANSI codes for stdout-only log
        clean_text = handler.strip(output_with_ansi)

        # Preserve ANSI codes for streaming log
        rich_text = handler.preserve(output_with_ansi)

        # Calculate size overhead from ANSI codes
        total_bytes, visible_bytes, ansi_bytes, percent = handler.calculate_sizes(output)
        ```
    """

    # Regex pattern for all ANSI escape sequences
    # Based on https://en.wikipedia.org/wiki/ANSI_escape_code
    # Matches:
    # - CSI (Control Sequence Introducer): ESC [ ... (m|A|B|C|D|H|J|K|...)
    # - OSC (Operating System Command): ESC ] ... (BEL|ST)
    # - Simple escape sequences: ESC (c|D|E|H|M|...)
    ANSI_ESCAPE_PATTERN = re.compile(
        r'''
        # CSI sequences: ESC [ <params> <command>
        \x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]
        |
        # OSC sequences: ESC ] ... BEL or ESC ] ... ESC \
        \x1b\][^\x07\x1b]*(?:\x07|\x1b\\)
        |
        # Simple escape sequences: ESC <char>
        \x1b[^\[]
        ''',
        re.VERBOSE
    )

    def strip(self, text: str) -> str:
        """Remove all ANSI escape sequences from text.

        Args:
            text: Text potentially containing ANSI codes

        Returns:
            Clean text with all ANSI sequences removed

        Example:
            >>> handler = ANSIHandler()
            >>> handler.strip("\\x1b[31mRed text\\x1b[0m")
            'Red text'
        """
        if not text:
            return text

        return self.ANSI_ESCAPE_PATTERN.sub('', text)

    def preserve(self, text: str) -> str:
        """Preserve ANSI escape sequences in text (identity function).

        This method exists for API symmetry with strip() and to make dual logging
        code more explicit about intent.

        Args:
            text: Text potentially containing ANSI codes

        Returns:
            Original text unchanged

        Example:
            >>> handler = ANSIHandler()
            >>> handler.preserve("\\x1b[31mRed text\\x1b[0m")
            '\\x1b[31mRed text\\x1b[0m'
        """
        return text

    def calculate_sizes(self, text: str) -> Tuple[int, int, int, float]:
        """Calculate size breakdown: total bytes, visible bytes, ANSI bytes, overhead %.

        Useful for reporting log file sizes and understanding ANSI overhead.

        Args:
            text: Text potentially containing ANSI codes

        Returns:
            Tuple of (total_bytes, visible_bytes, ansi_bytes, overhead_percent)

        Example:
            >>> handler = ANSIHandler()
            >>> text = "\\x1b[31mRed\\x1b[0m"  # 5 ANSI bytes + 3 visible chars
            >>> total, visible, ansi, percent = handler.calculate_sizes(text)
            >>> total == 8  # Total bytes
            >>> visible == 3  # "Red"
            >>> ansi == 5  # ANSI escape sequences
            >>> percent == 62.5  # ANSI overhead percentage
        """
        if not text:
            return (0, 0, 0, 0.0)

        total_bytes = len(text.encode('utf-8'))
        visible_text = self.strip(text)
        visible_bytes = len(visible_text.encode('utf-8'))
        ansi_bytes = total_bytes - visible_bytes
        overhead_percent = (ansi_bytes / total_bytes * 100) if total_bytes > 0 else 0.0

        return (total_bytes, visible_bytes, ansi_bytes, overhead_percent)
