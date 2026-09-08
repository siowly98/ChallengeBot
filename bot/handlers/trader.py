"""Everything a trader (applicant) can do: link their account, submit a
wallet address, check status, and claim a win. No decision here is final -
every path that matters (approval, funding, win verification) either waits
for a mod to act on a card, or reflects a decision a mod already made in
the sheet.
"""
import asyncio
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from .. import messages
from ..deadlines import compute_deadline, format_deadline
from ..mod_cards import claim_requested_card, wallet_submitted_card
from ..sheets import SheetStore

logger = logging.getLogger(__name__)

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def get_store(context: ContextTypes.DEFAULT_TYPE) -> SheetStore:
    return context.bot_data["store"]


async def _post_mod_card(context: ContextTypes.DEFAULT_TYPE, text: str, keyboard) -> bool:
    """Sends a card to the mod group. Returns True on success, False if it
    couldn't be delivered after one retry.

    This is the linchpin of the two flows that write to the sheet and THEN
    tell the mods about it (wallet submitted, claim requested). If the card
    send fails after the sheet write, the row is left in a state the poll
    loop doesn't cover - a wallet on file with no fundable card, or a
    REQUESTED claim with no verify/reject card - and the trader has no way
    to re-trigger it. So the callers roll their write back when this returns
    False, which puts the row back to a state the trader can retry from."""
    for attempt in range(2):
        try:
            await context.bot.send_message(
                chat_id=context.bot_data["mod_group_chat_id"],
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            return True
        except Exception:
            logger.exception("Failed to post mod card (attempt %s of 2)", attempt + 1)
            if attempt == 0:
                await asyncio.sleep(1)
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(context)
    row = await asyncio.to_thread(store.find_by_chat_id, update.effective_chat.id)
    if row is not None:
        await update.message.reply_text(messages.ALREADY_LINKED)
        return
    await update.message.reply_text(messages.WELCOME, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(messages.HELP)


async def wallet_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/wallet - re-send the "how to get your testnet wallet" steps. Once a
    trader is linked, the guide was only ever sent once (at approval), with
    no way to see it again short of scrolling. This gives them that on
    demand, and only when it's actually relevant to their state."""
    store = get_store(context)
    row = await asyncio.to_thread(store.find_by_chat_id, update.effective_chat.id)
    if row is None:
        await update.message.reply_text(messages.STATUS_UNLINKED)
        return
    if not (store.is_true(row, "Eligible") and store.is_true(row, "ApprovalSent")):
        await update.message.reply_text(messages.WALLET_NOT_APPROVED_YET)
        return
    if row.get("WalletAddress"):
        await update.message.reply_text(messages.WALLET_ALREADY_ON_FILE)
        return
    cfg = await asyncio.to_thread(store.get_config)
    await update.message.reply_text(messages.render(messages.WALLET_GUIDE, cfg))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(context)
    row = await asyncio.to_thread(store.find_by_chat_id, update.effective_chat.id)
    if row is None:
        await update.message.reply_text(messages.STATUS_UNLINKED)
        return

    deadline_line = ""
    if store.is_true(row, "Funded") and row.get("FundedAt"):
        cfg = await asyncio.to_thread(store.get_config)
        deadline = compute_deadline(row.get("FundedAt"), cfg.get("challenge_duration_hours"))
        if deadline is not None:
            deadline_line = f"- Challenge ends: {format_deadline(deadline)}\n"

    await update.message.reply_text(
        messages.STATUS_TEMPLATE.format(
            eligible="Yes" if store.is_true(row, "Eligible") else "Not yet",
            has_wallet="Yes" if row.get("WalletAddress") else "No",
            funded="Yes" if store.is_true(row, "Funded") else "No",
            deadline_line=deadline_line,
            claim_status=row.get("ClaimStatus") or "None submitted",
        )
    )


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(context)
    row = await asyncio.to_thread(store.find_by_chat_id, update.effective_chat.id)
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
        await update.message.reply_text("You're already verified - check earlier messages for your claim steps.")
        return

    await asyncio.to_thread(store.update_cell, row["_row"], "ClaimStatus", "REQUESTED")
    row["ClaimStatus"] = "REQUESTED"
    text, keyboard = claim_requested_card(row)

    if await _post_mod_card(context, text, keyboard):
        await update.message.reply_text(messages.CLAIM_RECEIVED)
    else:
        # Card never reached the mods - roll the status back so /claim works
        # again, instead of leaving a REQUESTED claim no mod can see or act on.
        await asyncio.to_thread(store.update_cell, row["_row"], "ClaimStatus", "")
        await update.message.reply_text(messages.CLAIM_SUBMIT_RETRY)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes a plain text message based on where this chat_id is in the
    sheet - see README for the state machine this implements."""
    store = get_store(context)
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    row = await asyncio.to_thread(store.find_by_chat_id, chat_id)

    if row is None:
        # Not linked yet -> treat this message as their application email.
        match = await asyncio.to_thread(store.find_by_email, text)
        if match is None:
            await update.message.reply_text(messages.EMAIL_NOT_FOUND)
            return

        existing_chat_id = str(match.get("ChatID") or "").strip()
        if existing_chat_id and existing_chat_id != str(chat_id):
            # Someone (possibly this same person on a second account) is
            # trying to claim an application slot that's already linked to
            # a different Telegram account - block it rather than letting
            # a second account ride along on the same application.
            await update.message.reply_text(messages.DUPLICATE_EMAIL)
            return

        # Link ChatID + username, and (if already eligible) ApprovalSent -
        # all decided before touching the network, then written in one
        # batched call instead of up to three separate round trips.
        username = update.effective_user.username or ""
        updates = {"ChatID": str(chat_id), "TelegramUsername": username}
        eligible = store.is_true(match, "Eligible")
        if eligible:
            updates["ApprovalSent"] = "TRUE"
        await asyncio.to_thread(store.update_cells, match["_row"], updates)

        if eligible:
            cfg = await asyncio.to_thread(store.get_config)
            await update.message.reply_text(messages.render(messages.APPROVAL_AND_WALLET_REQUEST, cfg))
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
            # Distinguish a botched address from a confused user: if it
            # starts with "0x" they clearly tried to paste an address, so
            # keep the terse "that's not valid" nudge. Anything else (a
            # question, "how do i get my wallet", "help") gets the full
            # guide re-sent - which is how a linked trader re-prompts it
            # without needing to know the /wallet command exists.
            if text.lower().startswith("0x"):
                await update.message.reply_text(messages.INVALID_WALLET_FORMAT)
            else:
                cfg = await asyncio.to_thread(store.get_config)
                await update.message.reply_text(messages.render(messages.WALLET_GUIDE, cfg))
            return

        existing = await asyncio.to_thread(store.find_by_wallet, text)
        if existing is not None and existing["_row"] != row["_row"]:
            # Same wallet already sitting on someone else's row - block it
            # rather than letting one wallet get funded twice.
            await update.message.reply_text(messages.DUPLICATE_WALLET)
            return

        await asyncio.to_thread(store.update_cell, row["_row"], "WalletAddress", text)
        row["WalletAddress"] = text
        cfg = await asyncio.to_thread(store.get_config)
        card_text, keyboard = wallet_submitted_card(row, cfg)

        if await _post_mod_card(context, card_text, keyboard):
            await update.message.reply_text(messages.WALLET_RECEIVED)
        else:
            # Card never reached the mods - roll the wallet write back so the
            # row returns to "awaiting wallet" and the trader can just resend,
            # instead of being silently stuck with a wallet on file and no
            # fundable card (the exact stuck state we hit before).
            await asyncio.to_thread(store.update_cell, row["_row"], "WalletAddress", "")
            await update.message.reply_text(messages.WALLET_SUBMIT_RETRY)
        return

    # Anything else that doesn't match a known state - point them at /status
    # rather than guessing what they meant.
    await update.message.reply_text(messages.UNKNOWN_MESSAGE)
