"""Unit tests for Telegram worker broadcasting behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.adapters import telegram_worker


@pytest.mark.asyncio
async def test_broadcast_uses_authorized_chats(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = telegram_worker.TelegramBot()
    bot._authorized_chats = {"1001", "1002"}
    bot._app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    monkeypatch.setattr(telegram_worker, "TEST_CHAT_ID", None)

    await bot._broadcast("hello")

    assert bot._app.bot.send_message.await_count == 2
    sent_chat_ids = {
        call.kwargs["chat_id"] for call in bot._app.bot.send_message.await_args_list
    }
    assert sent_chat_ids == {"1001", "1002"}


@pytest.mark.asyncio
async def test_broadcast_falls_back_to_test_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = telegram_worker.TelegramBot()
    bot._authorized_chats = set()
    bot._app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    monkeypatch.setattr(telegram_worker, "TEST_CHAT_ID", "7777")

    await bot._broadcast("hello")

    bot._app.bot.send_message.assert_awaited_once()
    assert bot._app.bot.send_message.await_args.kwargs["chat_id"] == "7777"
