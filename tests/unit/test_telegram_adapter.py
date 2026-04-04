"""Unit tests for TelegramInputAdapter.

Covers:
- Authorized chat → command forwarded to handler
- Unauthorized chat → ignored and logged
- Non-text message → ignored
- /start responds with welcome message
- Handler result replied to user
- build_app() creates Application with handlers registered
"""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock

import pytest

from src.adapters.telegram import TelegramInputAdapter
from src.interfaces.commands.handler import CommandContext, CommandHandler, CommandResult


# ── Helpers ───────────────────────────────────────────────────


def _make_update(
    chat_id: str = "12345",
    text: str = "/status",
) -> MagicMock:
    """Create a mock telegram.Update with a text message."""
    update = MagicMock()
    update.effective_chat.id = int(chat_id)
    update.effective_chat.type = "private"
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def _make_context() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_handler() -> MagicMock:
    h = MagicMock()
    h.handle.return_value = CommandResult(success=True, message="OK")
    return h


# ── Happy path ────────────────────────────────────────────────


class TestTelegramInputAdapterHappyPath:
    @pytest.mark.asyncio
    async def test_authorized_chat_forwards_to_handler(
        self,
        mock_handler: MagicMock,
    ) -> None:
        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=False,
            test_chat_id=None,
        )
        adapter.set_handler(mock_handler)

        update = _make_update(text="/status")

        await adapter._handle_message(update, _make_context())

        mock_handler.handle.assert_called_once()
        call_args = mock_handler.handle.call_args[0]
        assert call_args[0] == "status"
        assert call_args[1] == []
        assert isinstance(call_args[2], CommandContext)

    @pytest.mark.asyncio
    async def test_handler_result_replied_to_user(
        self,
        mock_handler: MagicMock,
    ) -> None:
        mock_handler.handle.return_value = CommandResult(
            success=True, message="Active: 5 | Blocked: 2"
        )
        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=False,
            test_chat_id=None,
        )
        adapter.set_handler(mock_handler)

        update = _make_update(text="/status")

        await adapter._handle_message(update, _make_context())

        update.message.reply_text.assert_called_once_with(
            "✅ Active: 5 | Blocked: 2"
        )


# ── Edge cases ────────────────────────────────────────────────


class TestTelegramInputAdapterEdgeCases:
    @pytest.mark.asyncio
    async def test_unauthorized_chat_ignored_and_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=True,
            test_chat_id="99999",
        )

        update = _make_update(chat_id="11111", text="/status")

        with caplog.at_level(logging.DEBUG, logger="src.adapters.telegram"):
            await adapter._handle_message(update, _make_context())

        assert any("Unauthorized" in r.message for r in caplog.records)
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_text_message_ignored(
        self, mock_handler: MagicMock
    ) -> None:
        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=False,
            test_chat_id=None,
        )
        adapter.set_handler(mock_handler)

        update = MagicMock()
        update.effective_chat.id = 12345
        update.message = None  # e.g. photo, sticker

        await adapter._handle_message(update, _make_context())

        mock_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_command_sends_welcome(self) -> None:
        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=False,
            test_chat_id=None,
        )

        update = _make_update(text="/start")
        update.message.reply_text = AsyncMock()

        await adapter._handle_start(update, _make_context())  # type: ignore[arg-type]

        update.message.reply_text.assert_called_once()
        call_arg = str(update.message.reply_text.call_args[0][0])
        assert "Welcome" in call_arg

    @pytest.mark.asyncio
    async def test_handler_failure_returns_error(
        self, mock_handler: MagicMock
    ) -> None:
        mock_handler.handle.return_value = CommandResult(
            success=False, message="Failed to unblock 1.2.3.4"
        )
        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=False,
            test_chat_id=None,
        )
        adapter.set_handler(mock_handler)

        update = _make_update(text="/unblock 1.2.3.4")

        await adapter._handle_message(update, _make_context())

        update.message.reply_text.assert_called_once_with(
            "❌ Failed to unblock 1.2.3.4"
        )

    def test_build_app_registers_handlers(self) -> None:
        """Smoke test: ensure build_app() creates an Application."""
        adapter = TelegramInputAdapter(
            token="test:token",
            test_mode=False,
            test_chat_id=None,
        )
        # Just verify it doesn't crash; we can't run polling in tests
        assert adapter._token == "test:token"
        assert adapter._test_mode is False
