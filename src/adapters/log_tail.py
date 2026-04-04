"""Log tailing utilities — base parser with file streaming.

Provides ``BaseLogParser`` (Template Method) that tails a file and
dispatches each line to ``parse_line()``.  Concrete parsers implement
the parsing logic.
"""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedEntry:
    """A single parsed log line."""

    ip: str
    user: Optional[str]
    timestamp: datetime
    raw_line: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseLogParser(ABC):
    """Abstract base for log parsers (Template Method pattern).

    Subclasses implement ``parse_line()``.  The ``process_stream()``
    method handles file tailing and callback dispatch.
    """

    @abstractmethod
    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        """Parse a single log line.

        Args:
            line: Raw log line text.

        Returns:
            A ParsedEntry if the line matches a pattern of interest,
            or None if the line should be ignored.
        """
        ...

    def process_stream(
        self,
        file_path: str,
        callback: Callable[[ParsedEntry], None],
        poll_interval: float = 0.5,
    ) -> None:
        """Tail a log file and call *callback* for each successfully parsed line.

        Uses ``tail -F`` so the file can be rotated.

        Args:
            file_path: Path to the log file.
            callback: Called with each ParsedEntry.
            poll_interval: Seconds between tail checks (not used with -F).
        """
        logger.info("Starting log tail of %s", file_path)

        try:
            proc = subprocess.Popen(
                ["tail", "-F", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            logger.error("tail command not found — cannot monitor %s", file_path)
            return
        except PermissionError:
            logger.error("Permission denied reading %s", file_path)
            return

        assert proc.stdout is not None

        try:
            for raw_line in proc.stdout:
                entry = self.parse_line(raw_line)
                if entry is not None:
                    logger.debug(
                        "Parsed entry: ip=%s user=%s from line: %s",
                        entry.ip,
                        entry.user,
                        entry.raw_line[:80],
                    )
                    callback(entry)
        except KeyboardInterrupt:
            logger.info("Log tail interrupted")
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            logger.info("Log tail stopped for %s", file_path)
