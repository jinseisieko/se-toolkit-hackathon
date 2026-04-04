"""CLI input adapter — reads commands from stdin for test mode.

Parses lines like ``/command arg1 arg2`` and delegates to a
``CommandHandler``.  Non-slash lines are ignored silently.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from src.interfaces.commands.handler import CommandContext, CommandHandler, CommandResult

logger = logging.getLogger(__name__)


class CLIInputAdapter:
    """Reads commands from standard input.

    Each line starting with ``/`` is parsed and forwarded to the
    ``CommandHandler``.  An empty line or the word ``quit``/``exit``
    stops the loop.
    """

    def __init__(self, prompt: str = "❯ ") -> None:
        self._prompt = prompt

    def start_listening(self, handler: CommandHandler) -> None:
        """Read stdin in a loop, parsing and dispatching commands.

        Args:
            handler: The CommandHandler to delegate parsed commands to.
        """
        print("🧪 TEST MODE: Type commands like '/status' or '/unblock 1.2.3.4'")
        print("Type 'quit' or 'exit' to stop.\n")

        context = CommandContext(
            user_id="cli_test_user",
            is_test_mode=True,
            allowed_actions={"status", "block", "unblock"},
        )

        try:
            while True:
                line = input(self._prompt).strip()
                if not line:
                    continue
                if line.lower() in ("quit", "exit"):
                    print("👋 Exiting test mode.")
                    break

                parsed = self._parse_command(line)
                if parsed is None:
                    logger.debug("Ignoring non-command input: %r", line)
                    continue

                command, args = parsed
                result = handler.handle(command, args, context)
                self._print_result(result)
        except EOFError:
            print("\n👋 EOF received. Exiting test mode.")
        except KeyboardInterrupt:
            print("\n👋 Interrupted. Exiting test mode.")

    def _print_result(self, result: CommandResult) -> None:
        """Print command result to stdout."""
        prefix = "✅" if result.success else "❌"
        print(f"{prefix} {result.message}")

    @staticmethod
    def _parse_command(line: str) -> Optional[Tuple[str, list[str]]]:
        """Parse a command line like ``/unblock 1.2.3.4`` into (command, args).

        Returns ``None`` if the line does not start with ``/``.

        Args:
            line: Raw input line from the user.

        Returns:
            A tuple of (command_name, args) or None.
        """
        stripped = line.strip()
        if not stripped.startswith("/"):
            return None

        # Remove leading slash and split
        parts = stripped[1:].split(maxsplit=1)
        if not parts or not parts[0]:
            return None

        command = parts[0]
        if len(parts) > 1:
            args = parts[1].split()
        else:
            args = []

        return command, args
