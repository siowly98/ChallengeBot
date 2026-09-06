import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from . import config
from .handlers import admin, trader
from .jobs import poll_sheet
from .sheets import SheetStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    store = SheetStore()

    app = Application.builder().token(config.BOT_TOKEN).build()
    app.bot_data["store"] = store
    app.bot_data["mod_group_chat_id"] = config.MOD_GROUP_CHAT_ID

    app.add_handler(CommandHandler("start", trader.start))
    app.add_handler(CommandHandler("help", trader.help_command))
    app.add_handler(CommandHandler("status", trader.status))
    app.add_handler(CommandHandler("claim", trader.claim))
    app.add_handler(CommandHandler("invite", admin.invite))
    app.add_handler(CallbackQueryHandler(admin.handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trader.handle_text))

    app.job_queue.run_repeating(poll_sheet, interval=config.POLL_INTERVAL_SECONDS, first=10)

    logger.info("Bot starting (poll interval: %ss)", config.POLL_INTERVAL_SECONDS)
    app.run_polling()


if __name__ == "__main__":
    main()
