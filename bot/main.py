import logging

from telegram import Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from . import config
from .handlers import admin, trader
from .jobs import poll_sheet
from .sheets import SheetStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Catches anything an handler raised (a Sheets API error/rate limit,
    a bug, whatever) so it turns into a visible log line plus a plain
    message to whoever sent the update, instead of the bot just staying
    silent and looking broken/unresponsive."""
    logger.exception("Unhandled error while processing update: %s", update, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Something went wrong on our end - please try again in a moment. "
                "If it keeps happening, message a mod."
            )
        except Exception:
            logger.exception("Failed to notify user about the earlier error")


async def _log_incoming_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Diagnostic only - runs before every other handler and logs which chat
    an update came from. Use this to confirm the real MOD_GROUP_CHAT_ID:
    send any message in the group you think is the mod group, then check
    these logs for its actual chat id/type and compare against the
    MOD_GROUP_CHAT_ID env var. Logs at DEBUG so it stays quiet in normal
    operation (it fired on every single update, which is noise at scale) -
    set the log level to DEBUG temporarily if you need to read chat IDs
    again."""
    chat = update.effective_chat
    if chat is None:
        return
    logger.debug(
        "incoming update: chat_id=%s chat_type=%s chat_title=%r configured_mod_group_id=%s match=%s",
        chat.id,
        chat.type,
        chat.title,
        config.MOD_GROUP_CHAT_ID,
        chat.id == config.MOD_GROUP_CHAT_ID,
    )


def main():
    store = SheetStore()

    # concurrent_updates lets the bot handle multiple people's messages at
    # once instead of processing them one at a time - without this, one
    # slow Sheets API call would hold up every other user's message behind
    # it, which is the main reason things felt slow under any real load.
    #
    # AIORateLimiter throttles OUTGOING messages under Telegram's limits
    # (~30 msg/s globally, ~20/min per group) and automatically waits out
    # 429 "retry after" responses. This matters when a mod bulk-approves a
    # wave of applicants: without it, the poll loop would fire messages
    # faster than Telegram allows and some would bounce.
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .concurrent_updates(True)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    app.bot_data["store"] = store
    app.bot_data["mod_group_chat_id"] = config.MOD_GROUP_CHAT_ID
    app.add_error_handler(on_error)

    # Runs before everything else, in its own group, so it never blocks the
    # real handlers - see _log_incoming_chat_id's docstring.
    app.add_handler(TypeHandler(Update, _log_incoming_chat_id), group=-1)

    # Trader-facing handlers (/start, /status, /claim, and the plain-text
    # email/wallet flow) should never fire inside the mod group - otherwise
    # a mod typing casual chat in there gets misread as a trader's email or
    # wallet address. admin.py's handlers check _is_mod_group() themselves
    # since they're meant to run ONLY there; these need the opposite.
    not_mod_group = ~filters.Chat(chat_id=config.MOD_GROUP_CHAT_ID)

    app.add_handler(CommandHandler("start", trader.start, filters=not_mod_group))
    app.add_handler(CommandHandler("help", trader.help_command, filters=not_mod_group))
    app.add_handler(CommandHandler("status", trader.status, filters=not_mod_group))
    app.add_handler(CommandHandler("wallet", trader.wallet_guide, filters=not_mod_group))
    app.add_handler(CommandHandler("claim", trader.claim, filters=not_mod_group))
    app.add_handler(CommandHandler("invite", admin.invite))
    app.add_handler(CommandHandler("check", admin.check))
    app.add_handler(CallbackQueryHandler(admin.handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & not_mod_group, trader.handle_text))

    app.job_queue.run_repeating(poll_sheet, interval=config.POLL_INTERVAL_SECONDS, first=10)

    logger.info("Bot starting (poll interval: %ss)", config.POLL_INTERVAL_SECONDS)
    app.run_polling()


if __name__ == "__main__":
    main()
