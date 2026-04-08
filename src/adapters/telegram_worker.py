"""LogSentinel Telegram bot — standalone service.

Connects to Telegram, polls the shared SQLite database for new alerts,
and forwards them to the configured chat.  Handles admin commands
(/status, /block, /unblock) by calling the web service REST API.

Usage:
    python -m src.adapters.telegram_worker
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from peewee import SqliteDatabase
from src.infrastructure.db import init_database
from src.infrastructure.models import Alert

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("logsentinel.telegram")


# ── Configuration ────────────────────────────────────────────

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ""
TEST_CHAT_ID = os.getenv("TELEGRAM_TEST_CHAT_ID") or None
TEST_MODE = TEST_CHAT_ID is not None
WEB_API_URL = os.getenv("WORKER_API_URL", "http://web:5000")
API_TOKEN = os.getenv("API_TOKEN") or None
DB_PATH = os.getenv("DB_PATH", "data/sentinel.db")
POLL_INTERVAL = float(os.getenv("TELEGRAM_POLL_INTERVAL", "10"))


class TelegramBot:
    """Telegram bot for LogSentinel alerts and admin commands."""

    def __init__(self) -> None:
        self._app: Application | None = None
        self._last_alert_id = 0
        self._authorized_chats: set[str] = set()

    async def start(self) -> None:
        """Initialise the database, register handlers, and start polling."""
        if not BOT_TOKEN or BOT_TOKEN == "test:token":
            logger.warning(
                "TELEGRAM_BOT_TOKEN not set — Telegram bot inactive. "
                "Set it in .env to enable."
            )
            # Keep container alive — wait forever
            import asyncio

            while True:
                await asyncio.sleep(60)
            return

        # Open shared database
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        db = SqliteDatabase(DB_PATH)
        init_database(db)

        # Seed the last alert ID from existing data
        try:
            latest = Alert.select().order_by(Alert.id.desc()).first()
            if latest:
                self._last_alert_id = latest.id
                logger.info("Seeded alert ID from DB: %d", self._last_alert_id)
        except Exception as exc:
            logger.warning("Could not seed alert ID: %s", exc)

        self._app = Application.builder().token(BOT_TOKEN).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("block", self._cmd_block))
        self._app.add_handler(CommandHandler("unblock", self._cmd_unblock))
        self._app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_text)
        )

        logger.info("Telegram bot starting (test_mode=%s)", TEST_MODE)
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

        # Run alert polling in the background
        import asyncio

        asyncio.create_task(self._poll_alerts())

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self._app.stop()
            await self._app.shutdown()

    # ── Alert polling ─────────────────────────────────────────

    async def _poll_alerts(self) -> None:
        """Periodically check the database for new alerts."""
        import asyncio

        logger.info("Alert poller started (interval=%.0fs)", POLL_INTERVAL)
        while True:
            try:
                new_alerts = (
                    Alert.select()
                    .where(Alert.id > self._last_alert_id)
                    .order_by(Alert.id.asc())
                )
                for alert in new_alerts:
                    msg = (
                        f"🚨 SSH brute-force detected\n"
                        f"IP: {alert.ip}\n"
                        f"Attempts: {alert.attempts}\n"
                        f"Service: {alert.service}\n"
                        f"Time: {alert.last_seen.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                        f"Status: {'Blocked' if alert.blocked else 'Active'}"
                    )
                    await self._broadcast(msg)
                    self._last_alert_id = alert.id
            except Exception as exc:
                logger.error("Alert poll error: %s", exc)
            await asyncio.sleep(POLL_INTERVAL)

    async def _broadcast(self, message: str) -> None:
        """Send a message to all authorized chats."""
        if not self._app or not self._app.bot:
            return
        chats = self._authorized_chats or (
            {TEST_CHAT_ID} if TEST_CHAT_ID else set()
        )
        for chat_id in chats:
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id, text=message, parse_mode="HTML"
                )
            except Exception as exc:
                logger.error("Failed to send alert to %s: %s", chat_id, exc)

    # ── Telegram handlers ─────────────────────────────────────

    def _check_auth(self, update: Update) -> bool:
        """Check if the chat is authorized."""
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        if TEST_MODE:
            if chat_id != TEST_CHAT_ID:
                logger.debug("Unauthorized chat %s in test mode", chat_id)
                return False
        self._authorized_chats.add(chat_id)
        return True

    async def _reply(self, update: Update, text: str) -> None:
        if update.message:
            await update.message.reply_text(text)

    async def _cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._check_auth(update):
            return
        await self._reply(
            update,
            (
                "🛡️ Welcome to LogSentinel!\n\n"
                "/status — Show active and blocked counts\n"
                "/unblock <IP> — Unblock an IP\n"
                "/block <IP> [reason] — Block an IP"
            ),
        )

    async def _cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._check_auth(update):
            return
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{WEB_API_URL}/api/alerts")
                resp.raise_for_status()
                alerts = resp.json()

                resp = await client.get(f"{WEB_API_URL}/api/blocked")
                resp.raise_for_status()
                blocked = resp.json()

                active = sum(1 for a in alerts if not a.get("blocked"))
                total_blocked = len(blocked)
                await self._reply(
                    update,
                    (
                        f"📊 LogSentinel Status\n"
                        f"Active alerts: {active}\n"
                        f"Blocked IPs: {total_blocked}\n"
                        f"Total alerts: {len(alerts)}"
                    ),
                )
        except Exception as exc:
            await self._reply(update, f"❌ Status check failed: {exc}")

    async def _cmd_block(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._check_auth(update):
            return
        ip = context.args[0] if context.args else None
        if not ip:
            await self._reply(update, "Usage: /block <IP> [reason]")
            return
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Telegram admin command"
        await self._api_post(update, "block", {"ip": ip, "reason": reason})

    async def _cmd_unblock(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._check_auth(update):
            return
        ip = context.args[0] if context.args else None
        if not ip:
            await self._reply(update, "Usage: /unblock <IP>")
            return
        await self._api_post(update, "unblock", {"ip": ip})

    async def _api_post(
        self, update: Update, endpoint: str, payload: dict[str, Any]
    ) -> None:
        """Call the web service REST API and reply."""
        if not API_TOKEN:
            await self._reply(
                update, "❌ API_TOKEN not configured — block/unblock disabled."
            )
            return
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{WEB_API_URL}/api/{endpoint}",
                    json=payload,
                    headers={"Authorization": f"Bearer {API_TOKEN}"},
                )
                data = resp.json()
                prefix = "✅" if resp.status_code == 200 else "❌"
                await self._reply(
                    update,
                    f"{prefix} {data.get('message', str(data))}",
                )
        except Exception as exc:
            await self._reply(update, f"❌ API call failed: {exc}")

    async def _handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Parse plain text as a command if it starts with /."""
        if update.message and update.message.text.startswith("/"):
            await self._cmd_start(update, context)


def main() -> None:
    """Entry point."""
    import asyncio

    bot = TelegramBot()
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
