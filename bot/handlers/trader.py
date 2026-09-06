"""Everything a trader (applicant) can do: link their account, submit a
wallet address, check status, and claim a win. No decision here is final -
every path that matters (approval, funding, win verification) either waits
for a mod to act on a card, or reflects a decision a mod already made in
the sheet.
"""
import re

from telegram import Update
from telegram.ext import ContextTypes

from .. import messages
from ..mod_cards import claim_requested_card, wallet_submitted_card
from ..sheets import SheetStore

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def get_store(context: ContextTypes.DEFAULT_TYPE) -> SheetStore:
    return context.bot_data["store"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(context)
    row = store.find_by_chat_id(update.effective_chat.id)
    if row is not None:
        await update.message.reply_text(messages.ALREADY_LINKED)
        return
    await update.message.reply_text(messages.WELCOME, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(messages.HELP)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(context)
    row = store.find_by_chat_id(update.effective_chat.id)
    if row is None:
        await update.message.reply_text(messages.STATUS_UNLINKED)
        return
    await update.message.reply_text(
        messages.STATUS_TEMPLATE.format(
            eligible="Yes" if store.is_true(row, "Eligible") else "Not yet",
            has_wallet="Yes" if row.get("WalletAddress") else "No",
            funded="Yes" if store.is_true(row, "Funded") else "No",
            claim_status=row.get("ClaimStatus") or "None submitted",
        )
    )


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(context)
    row = store.find_by_chat_id(update.effective_chat.id)
    if row is None:
        await update.message.reply_text(messages.STATUS_UNLINKED)
        return
    if not store.is_true(row, "Funded"):
        await update.message.reply_text(messages.CLAIM_NOT_ELIGIBLE)
        return
    if row.get("ClaimStatus") == "REQUESTED":
        await update.message.reply_text(messages.CLAIM_ALREADY_SUBMITTED)
        return
    if row.get("ClaimStatus") == "VERIFIED":
        await update.message.reply_text("You're already verified — check earlier messages for your claim steps.")
        return

    store.update_cell(row["_row"], "ClaimStatus", "REQUESTED")
    await update.message.reply_text(messages.CLAIM_RECEIVED)

    row["ClaimStatus"] = "REQUESTED"
    text, keyboard = claim_requested_card(row)
    await context.bot.send_message(
        chat_id=context.bot_data["mod_group_chat_id"],
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes a plain text message based on where this chat_id is in the
    sheet - see README for the state machine this implements."""
    store = get_store(context)
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    row = store.find_by_chat_id(chat_id)

    if row is None:
        # Not linked yet -> treat this message as their application email.
        match = store.find_by_email(text)
        if match is None:
            await update.message.reply_text(messages.EMAIL_NOT_FOUND)
            return

        store.update_cell(match["_row"], "ChatID", str(chat_id))
        username = update.effective_user.username or ""
        store.update_cell(match["_row"], "TelegramUsername", username)

        if store.is_true(match, "Eligible"):
            store.update_cell(match["_row"], "ApprovalSent", "TRUE")
            await update.message.reply_text(messages.APPROVAL_AND_WALLET_REQUEST)
        else:
            await update.message.reply_text(messages.LINK_SUCCESS_NOT_YET_REVIEWED)
        return

    awaiting_wallet = (
        store.is_true(row, "Eligible")
        and store.is_true(row, "ApprovalSent")
        and not row.get("WalletAddress")
    )
    if awaiting_wallet:
        if not WALLET_RE.match(text):
            await update.message.reply_text(messages.INVALID_WALLET_FORMAT)
            return
        store.update_cell(row["_row"], "WalletAddress", text)
        await update.message.reply_text(messages.WALLET_RECEIVED)

        row["WalletAddress"] = text
        card_text, keyboard = wallet_submitted_card(row)
        await context.bot.send_message(
            chat_id=context.bot_data["mod_group_chat_id"],
            text=card_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    # Anything else that doesn't match a known state - point them at /status
    # rather than guessing what they meant.
    await update.message.reply_text(messages.UNKNOWN_MESSAGE)
