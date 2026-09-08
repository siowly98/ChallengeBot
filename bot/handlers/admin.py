"""Mod-side actions: the inline button taps in the mod group, plus the
/invite command mods use to send a winner's private-group link through the
bot instead of hunting the trader down themselves.

Everything here checks it's being used inside the configured mod group -
these actions should never be reachable by a trader.
"""
from telegram import Update
from telegram.ext import ContextTypes

from .. import messages
from ..sheets import SheetStore


def get_store(context: ContextTypes.DEFAULT_TYPE) -> SheetStore:
    return context.bot_data["store"]


def _is_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return update.effective_chat.id == context.bot_data["mod_group_chat_id"]


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_mod_group(update, context):
        await query.answer("This only works in the mod group.", show_alert=True)
        return

    store = get_store(context)
    action, row_str = query.data.split(":")
    row = store.find_by_row(int(row_str))
    if row is None:
        await query.answer("Couldn't find that row anymore - check the sheet.", show_alert=True)
        return

    mod_name = query.from_user.first_name

    if action == "fund":
        cfg = store.get_config()
        store.update_cell(row["_row"], "Funded", "TRUE")
        store.update_cell(row["_row"], "GuideSent", "TRUE")
        await context.bot.send_message(
            chat_id=int(row["ChatID"]),
            text=messages.render(messages.FUNDED_AND_GUIDE, cfg),
        )
        await query.edit_message_text(f"{query.message.text}\n\n✅ Funded by {mod_name}", parse_mode="Markdown")

    elif action == "verify":
        cfg = store.get_config()
        store.update_cell(row["_row"], "ClaimStatus", "VERIFIED")
        store.update_cell(row["_row"], "ClaimInstructionsSent", "TRUE")
        await context.bot.send_message(
            chat_id=int(row["ChatID"]),
            text=messages.render(messages.CLAIM_VERIFIED, cfg),
        )
        await query.edit_message_text(f"{query.message.text}\n\n✅ Verified by {mod_name}", parse_mode="Markdown")

    elif action == "reject":
        store.update_cell(row["_row"], "ClaimStatus", "REJECTED")
        await context.bot.send_message(
            chat_id=int(row["ChatID"]),
            text=messages.CLAIM_REJECTED.format(reason="Message a mod if you have questions."),
        )
        await query.edit_message_text(f"{query.message.text}\n\n❌ Rejected by {mod_name}", parse_mode="Markdown")

    await query.answer()


async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage (in the mod group): /invite <sheet_row_number> <invite_link>"""
    if not _is_mod_group(update, context):
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /invite <sheet_row_number> <invite_link>")
        return

    store = get_store(context)
    try:
        row_number = int(args[0])
    except ValueError:
        await update.message.reply_text("First argument must be the sheet row number (see the card above).")
        return

    invite_link = args[1]
    row = store.find_by_row(row_number)
    if row is None or not row.get("ChatID"):
        await update.message.reply_text("Couldn't find that row, or that trader hasn't linked their Telegram yet.")
        return

    await context.bot.send_message(
        chat_id=int(row["ChatID"]),
        text=messages.GROUP_INVITE.format(invite_link=invite_link),
    )
    await update.message.reply_text(f"Sent the invite link to {row.get('Email Address')}.")
