"""Command factory — creates CommandHandler with injected dependencies.

Centralises wiring so that both CLI and Telegram adapters get the
same handler instance.
"""

from __future__ import annotations

from src.core.services.block_service import BlockService
from src.core.repositories import AlertRepository
from src.interfaces.commands.handler import CommandHandler


def create_command_handler(
    block_service: BlockService,
    alert_repo: AlertRepository,
) -> CommandHandler:
    """Create a CommandHandler with the given service dependencies.

    Args:
        block_service: The BlockService for block/unblock operations.
        alert_repo: The AlertRepository for querying alert data.

    Returns:
        A ready-to-use CommandHandler.
    """
    return CommandHandler(
        block_service=block_service,
        alert_repo=alert_repo,
    )
