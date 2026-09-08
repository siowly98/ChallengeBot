"""Safety-net poll loop. Most actions in this bot fire immediately from a
button tap or a trader message. This job exists for the case where a mod
edits the sheet directly instead (e.g. ticking Eligible=TRUE by hand while
reviewing the raw form responses) - it catches that within
POLL_INTERVAL_SECONDS and sends the message the bot would've sent anyway.
"""
import asyncio
import logging
from datetime import datetime, timezone

from telegram.ext import ContextTypes

from . import messages
from .deadlines import compute_deadline, format_deadline

logger = logging.getLogger(__name__)


async def poll_sheet(context: ContextTypes.DEFAULT_TYPE):
    store = context.bot_data["store"]
    try:
        rows = await asyncio.to_thread(store.all_rows)
        cfg = await asyncio.to_thread(store.get_config)
    except Exception:
        logger.exception("Failed to read sheet during poll")
        return

    for row in rows:
        chat_id = row.get("ChatID")
        if not chat_id:
            continue  # hasn't linked their Telegram yet - nothing we can send

        try:
            if store.is_true(row, "Eligible") and not store.is_true(row, "ApprovalSent"):
                await context.bot.send_message(
                    chat_id=int(chat_id), text=messages.render(messages.APPROVAL_AND_WALLET_REQUEST, cfg)
                )
                await asyncio.to_thread(store.update_cell, row["_row"], "ApprovalSent", "TRUE")

            if store.is_true(row, "Funded") and not store.is_true(row, "GuideSent"):
                funded_at_iso = row.get("FundedAt") or ""
                if not funded_at_iso:
                    # Mod ticked Funded by hand in the sheet instead of using
                    # the Fund button - stamp FundedAt now so there's still a
                    # reference point for the deadline and for /status.
                    funded_at_iso = datetime.now(timezone.utc).isoformat()
                    await asyncio.to_thread(store.update_cell, row["_row"], "FundedAt", funded_at_iso)
                deadline = compute_deadline(funded_at_iso, cfg.get("challenge_duration_hours"))
                deadline_str = format_deadline(deadline) if deadline else "the deadline"
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=messages.render(messages.FUNDED_AND_GUIDE, cfg, deadline=deadline_str),
                )
                await asyncio.to_thread(store.update_cell, row["_row"], "GuideSent", "TRUE")
        except Exception:
            logger.exception("Failed processing row %s during poll", row.get("_row"))
