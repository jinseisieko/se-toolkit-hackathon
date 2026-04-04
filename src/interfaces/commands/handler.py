"""Command handler — routes admin commands to services.

This module is the central command router.  It knows nothing about
input sources (CLI, Telegram, webhooks) — those are handled by adapters
that call ``CommandHandler.handle()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence, Set


class _BlockServiceProto(Protocol):
    def unblock_ip(self, ip: str) -> bool: ...
    def block_ip(self, ip: str, reason: str = ...) -> bool: ...


class _AlertEntity(Protocol):
    blocked: bool


class _AlertRepoProto(Protocol):
    def get_recent(self, limit: int = ...) -> Sequence[_AlertEntity]: ...


@dataclass(frozen=True)
class CommandContext:
    """Metadata about the current command invocation.

    Attributes:
        user_id: Identifier of the user (chat ID for Telegram, username for CLI).
        is_test_mode: Whether destructive commands should be restricted.
        allowed_actions: Set of action names this user may perform.
    """

    user_id: str
    is_test_mode: bool
    allowed_actions: Set[str] = field(default_factory=lambda: {"status"})


@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution.

    Attributes:
        success: Whether the command completed successfully.
        message: Human-readable output (may include error details).
    """

    success: bool
    message: str


class CommandHandler:
    """Stateless command router — works with any input source.

    Composes a ``BlockService`` and an ``AlertRepository`` to execute
    admin commands (status, block, unblock).
    """

    def __init__(
        self,
        block_service: _BlockServiceProto,
        alert_repo: _AlertRepoProto,
    ) -> None:
        self._block_service = block_service
        self._alert_repo = alert_repo

    def handle(
        self, command: str, args: list[str], context: CommandContext
    ) -> CommandResult:
        """Route *command* to the appropriate handler.

        Args:
            command: The command name without leading slash (e.g. "status").
            args: Arguments following the command name.
            context: Execution context with auth and permission info.

        Returns:
            A CommandResult with success flag and output message.
        """
        if command == "status":
            return self._handle_status(context)
        elif command == "unblock":
            return self._handle_unblock(args, context)
        elif command == "block":
            return self._handle_block(args, context)
        else:
            return CommandResult(
                success=False, message=f"Unknown command: /{command}"
            )

    # ── Command handlers ──────────────────────────────────────

    def _handle_status(self, context: CommandContext) -> CommandResult:
        """Return counts of active and blocked alerts."""
        if "status" not in context.allowed_actions:
            return CommandResult(success=False, message="Permission denied.")

        alerts = self._alert_repo.get_recent(limit=200)
        active = sum(1 for a in alerts if not a.blocked)
        blocked = sum(1 for a in alerts if a.blocked)

        return CommandResult(
            success=True, message=f"Active: {active} | Blocked: {blocked}"
        )

    def _handle_unblock(
        self, args: list[str], context: CommandContext
    ) -> CommandResult:
        """Unblock an IP address."""
        if "unblock" not in context.allowed_actions:
            return CommandResult(success=False, message="Permission denied.")

        if not args:
            return CommandResult(
                success=False, message="Usage: /unblock <IP>"
            )

        ip = args[0]
        if self._block_service.unblock_ip(ip):
            return CommandResult(success=True, message=f"Unblocked {ip}")
        return CommandResult(
            success=False, message=f"Failed to unblock {ip}"
        )

    def _handle_block(
        self, args: list[str], context: CommandContext
    ) -> CommandResult:
        """Block an IP address."""
        if "block" not in context.allowed_actions:
            return CommandResult(success=False, message="Permission denied.")

        if not args:
            return CommandResult(
                success=False, message="Usage: /block <IP> [reason]"
            )

        ip = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "manual block"

        if self._block_service.block_ip(ip, reason):
            return CommandResult(
                success=True, message=f"Blocked {ip}: {reason}"
            )
        return CommandResult(
            success=False, message=f"Failed to block {ip}"
        )
