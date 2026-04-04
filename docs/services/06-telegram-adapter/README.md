# 6. TelegramInputAdapter

**Pattern:** Adapter  
**File:** `src/adapters/telegram.py`  
**Tests:** `tests/unit/test_telegram_adapter.py` (7 tests)

---

## Purpose

Connects `python-telegram-bot` to `CommandHandler`. Receives Telegram updates, parses commands, forwards to the handler, and sends back results. Supports test mode with chat ID filtering.

---

## API

```python
from src.adapters.telegram import TelegramInputAdapter

adapter = TelegramInputAdapter(
    token="123456:ABC-DEF...",
    test_mode=False,
    test_chat_id=None,  # only relevant when test_mode=True
)

adapter.set_handler(command_handler)
app = adapter.build_app()
app.run_polling()  # blocks, runs forever
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | Telegram bot token from @BotFather |
| `test_mode` | `bool` | If True, only `test_chat_id` can interact |
| `test_chat_id` | `str \| None` | The only allowed chat ID in test mode |

---

## Supported Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with available commands |
| `/status` | Show active and blocked counts |
| `/unblock <IP>` | Unblock an IP |
| `/block <IP> [reason]` | Block an IP |

---

## Behavior

- **Test mode:** Only messages from `test_chat_id` are processed. Other chats are silently ignored (DEBUG log).
- **Non-text messages:** (photos, stickers) are ignored.
- **Reply format:** `✅ <message>` for success, `❌ <message>` for failure.
- **Permission model:** Test mode restricts `allowed_actions` to `{"status"}` only. Production mode allows all actions.

---

## Internal Dispatch

```
Telegram Update
    → _handle_message() (async)
        → _check_authorized() (test mode filter)
        → Parse command from text
        → CommandHandler.handle(command, args, context)
        → _reply(update, result) (async)
```

---

## Design Decisions

- **Async handlers:** All telegram-bot handlers are async because the library requires it. The `CommandHandler` itself is sync — the adapter bridges the async/sync boundary.
- **Separate `/start` handler:** Sends a welcome message with instructions, independent of the command router.
