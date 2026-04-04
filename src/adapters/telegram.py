"""Telegram input adapter — connects python-telegram-bot to CommandHandler.

Translates Telegram ``Update`` objects into commands for the
``CommandHandler`` and sends back the result.  Supports test mode:
only responds to a specific chat ID.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler as TGCommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.interfaces.commands.handler import CommandContext, CommandHandler, CommandResult

logger = logging.getLogger(__name__)


class TelegramInputAdapter:
    """Adapter that bridges Telegram bot messages to our CommandHandler.

    In test mode, only messages from ``test_chat_id`` are processed.
    All other messages are silently ignored (with a debug log).

    Args:
        token: Telegram bot token from BotFather.
        test_mode: If True, restrict access to ``test_chat_id``.
        test_chat_id: The only chat allowed when ``test_mode`` is True.
    """

    def __init__(
        self,
        token: str,
        test_mode: bool = False,
        test_chat_id: Optional[str] = None,
    ) -> None:
        if not token or token == "test:token":
            logger.warning("Bot token looks like a placeholder — bot will not work.")
        self._token = token
        self._test_mode = test_mode
        self._test_chat_id = test_chat_id
        self._handler: Optional[CommandHandler] = None
        self._app: Any = None

    def set_handler(self, handler: CommandHandler) -> None:
        """Attach the CommandHandler to delegate commands to.

        Args:
            handler: The CommandHandler instance.
        """
        self._handler = handler

    def build_app(self) -> Any:
        """Build and return the python-telegram-bot Application.

        Must be called *after* ``set_handler()``.

        Returns:
            A configured Application ready for ``run_polling()``.
        """
        if self._handler is None:
            raise RuntimeError("Call set_handler() before build_app()")

        self._app = Application.builder().token(self._token).build()

        # Register /start, /status, /unblock, /block command handlers
        self._app.add_handler(TGCommandHandler("start", self._handle_start))
        self._app.add_handler(TGCommandHandler("status", self._handle_command))
        self._app.add_handler(TGCommandHandler("unblock", self._handle_command))
        self._app.add_handler(TGCommandHandler("block", self._handle_command))

        # Fallback: parse any text message
        self._app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_text)
        )

        return self._app

    # ── Telegram handlers ─────────────────────────────────────

    async def _handle_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start — send welcome message."""
        if not self._check_authorized(update):
            return

        welcome = (
            "🛡️ Welcome to LogSentinel!\n\n"
            "Available commands:\n"
            "/status — Show active and blocked counts\n"
            "/unblock <IP> — Unblock an IP\n"
            "/block <IP> [reason] — Block an IP\n"
        )
        if update.message:
            await update.message.reply_text(welcome)

    async def _handle_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status, /unblock, /block commands."""
        await self._handle_message(update, context)

    async def _handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle plain text messages — parse as /command if starts with /."""
        await self._handle_message(update, context)

    async def _handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Core dispatch: parse command → forward to CommandHandler → reply.

        This is async because telegram-bot handlers run in an async context.
        """
        if update.message is None:
            logger.debug("Received non-message update, ignoring")
            return

        if not self._check_authorized(update):
            return

        text = update.message.text
        if not text:
            return

        # Parse: strip leading slash, split into command + args
        stripped = text.lstrip("/")
        parts = stripped.split(maxsplit=1)
        command = parts[0]
        args = parts[1].split() if len(parts) > 1 else []

        if self._handler is None:
            logger.error("CommandHandler not set")
            return

        ctx = self._build_context(update)
        result = self._handler.handle(command, args, ctx)
        await self._reply(update, result)

    # ── Helpers ───────────────────────────────────────────────

    def _check_authorized(self, update: Update) -> bool:
        """Check if the chat is authorized (test mode filter).

        Args:
            update: The incoming Telegram update.

        Returns:
            True if the chat is allowed, False otherwise.
        """
        if not self._test_mode:
            return True

        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        if chat_id != self._test_chat_id:
            logger.debug(
                "Unauthorized chat %s in test mode (allowed: %s)",
                chat_id,
                self._test_chat_id,
            )
            return False

        return True

    def _build_context(self, update: Update) -> CommandContext:
        """Build a CommandContext from the Telegram update.

        Args:
            update: The incoming Telegram update.

        Returns:
            A CommandContext with user ID and permission info.
        """
        user_id = str(update.effective_chat.id) if update.effective_chat else "unknown"
        allowed = {"status"}
        if not self._test_mode:
            allowed |= {"block", "unblock"}

        return CommandContext(
            user_id=user_id,
            is_test_mode=self._test_mode,
            allowed_actions=allowed,
        )

    @staticmethod
    async def _reply(update: Update, result: CommandResult) -> None:
        """Send the command result back to the user.

        Args:
            update: The original Telegram update.
            result: The CommandResult from our handler.
        """
        prefix = "✅" if result.success else "❌"
        message = f"{prefix} {result.message}"

        if update.message:
            await update.message.reply_text(message)
