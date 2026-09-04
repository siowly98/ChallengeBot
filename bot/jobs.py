"""Safety-net poll loop. Most actions in this bot fire immediately from a
button tap or a trader message. This job exists for the case where a mod
edits the sheet directly instead (e.g. ticking Eligible=TRUE by hand while
reviewing the raw form responses) - it catches that within
POLL_INTERVAL_SECONDS and sends the message the bot would've sent anyway.
"""
import logging

from telegram.ext import ContextTypes

from . import messages

logger = logging.getLogger(__name__)


async def poll_sheet(context: ContextTypes.DEFAULT_TYPE):
    store = context.bot_data["store"]
    try:
        rows = store.all_rows()
    except Exception:
        logger.exception("Failed to read sheet during poll")
        return

    for row in rows:
        chat_id = row.get("ChatID")
        if not chat_id:
            continue  # hasn't linked their Telegram yet - nothing we can send

        try:
            if store.is_true(row, "Eligible") and not store.is_true(row, "ApprovalSent"):
                await context.bot.send_message(chat_id=int(chat_id), text=messages.APPROVAL_AND_WALLET_REQUEST)
                store.update_cell(row["_row"], "ApprovalSent", "TRUE")

            if store.is_true(row, "Funded") and not store.is_true(row, "GuideSent"):
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=messages.FUNDED_AND_GUIDE.format(guide_link="https://your-doc-link-here/setup-guide"),
                )
                store.update_cell(row["_row"], "GuideSent", "TRUE")
        except Exception:
            logger.exception("Failed processing row %s during poll", row.get("_row"))
