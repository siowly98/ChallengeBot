"""Mod-side actions: the inline button taps in the mod group, plus the
/invite command mods use to send a winner's private-group link through the
bot instead of hunting the trader down themselves.

Everything here checks it's being used inside the configured mod group -
these actions should never be reachable by a trader.
"""
import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from .. import messages
from ..deadlines import compute_deadline, format_deadline, format_timedelta, funded_late_in_week
from ..sheets import SheetStore

logger = logging.getLogger(__name__)

# Deliberately far under Telegram's documented ~30 msg/sec free-tier ceiling
# for bulk notifications - a broadcast here is never time-sensitive, so
# there's no reason to push anywhere near that limit for a one-off
# announcement. This paces sends on top of (not instead of) the bot's own
# AIORateLimiter, as a second, independent throttle.
BROADCAST_SEND_DELAY_SECONDS = 1.0
# How often (in recipients processed) to post a progress update in the mod
# group during a large broadcast, so a multi-minute run doesn't look stalled.
BROADCAST_PROGRESS_EVERY = 100


def get_store(context: ContextTypes.DEFAULT_TYPE) -> SheetStore:
    return context.bot_data["store"]


def _is_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return update.effective_chat.id == context.bot_data["mod_group_chat_id"]


def _command_argument_text(update: Update) -> str:
    """Everything typed after the /command token, preserving line breaks.

    context.args isn't usable here - it splits the whole command on any
    whitespace, which throws away line breaks a mod puts in a multi-line
    announcement. Locating the bot_command entity handles both "/broadcast
    text" and "/broadcast@YourBotName text" (the latter is how Telegram
    sends commands in some group contexts) without guessing at the command
    name's length.
    """
    message = update.message
    if not message or not message.text:
        return ""
    for entity in message.entities or []:
        if entity.type == "bot_command" and entity.offset == 0:
            return message.text[entity.offset + entity.length :].strip()
    return ""


def _funded_recipients(store: SheetStore) -> list[tuple[int, dict]]:
    """Every currently-funded trader with a linked Telegram chat, as
    (chat_id, row) pairs. A Funded row with no ChatID (shouldn't normally
    happen, but the sheet is hand-edited) is silently excluded rather than
    counted as a later "failed" send - it was never sendable to begin with."""
    out = []
    for row in store.all_rows():
        if not store.is_true(row, "Funded"):
            continue
        chat_id_raw = row.get("ChatID")
        if not chat_id_raw:
            continue
        try:
            out.append((int(chat_id_raw), row))
        except ValueError:
            continue
    return out


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage (in the mod group): /broadcast <message>

    Stages a plain-text broadcast to every currently-funded trader and
    replies with a preview plus the recipient count - it does NOT send
    anything itself. A mod has to follow up with /broadcastconfirm to
    actually fire it. Two steps on purpose: a broadcast has no
    per-recipient undo, so a typo or a wrong draft going out to hundreds
    of people can't be walked back the way a single DM or an edited card
    can be.

    No Markdown/HTML parsing - past Telegram-parsing bugs here (see the
    "verify" branch of handle_button) came from re-parsing text that
    contained characters Markdown treats as formatting syntax. A mod's own
    free-text announcement is exactly the kind of input that's likely to
    contain those by accident, so this sends it as plain text rather than
    risk the whole broadcast failing on a parse error.
    """
    if not _is_mod_group(update, context):
        return

    text = _command_argument_text(update)
    if not text:
        await update.message.reply_text(
            "Usage: /broadcast <message>\n\nThen confirm with /broadcastconfirm."
        )
        return

    store = get_store(context)
    recipients = await asyncio.to_thread(_funded_recipients, store)
    if not recipients:
        await update.message.reply_text("No funded traders with a linked Telegram to broadcast to.")
        return

    context.bot_data["pending_broadcast"] = {
        "text": text,
        "recipients": recipients,
        "staged_by": update.effective_user.first_name if update.effective_user else "a mod",
    }
    eta_minutes = round(len(recipients) * BROADCAST_SEND_DELAY_SECONDS / 60, 1)
    await update.message.reply_text(
        f"Draft staged - will send to {len(recipients)} funded traders as plain text "
        f"(~{eta_minutes} min at the throttled send rate):\n\n"
        f"{text}\n\n"
        f"Reply /broadcastconfirm to send, or run /broadcast again to replace this draft."
    )


async def broadcastconfirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage (in the mod group): /broadcastconfirm - sends the draft staged
    by /broadcast. See that command's docstring for why this is a separate
    confirmation step rather than /broadcast sending directly."""
    if not _is_mod_group(update, context):
        return

    if context.bot_data.get("broadcast_running"):
        await update.message.reply_text(
            "A broadcast is already in progress - wait for it to finish before starting another."
        )
        return

    pending = context.bot_data.pop("pending_broadcast", None)
    if pending is None:
        await update.message.reply_text("No broadcast is staged. Run /broadcast <message> first.")
        return

    context.bot_data["broadcast_running"] = True
    mod_group_id = context.bot_data["mod_group_chat_id"]
    await update.message.reply_text(
        f"Sending to {len(pending['recipients'])} funded traders, throttled to about "
        f"1 message/second - progress updates will follow in this chat."
    )
    asyncio.create_task(_run_broadcast(context, pending, mod_group_id))


async def _run_broadcast(context: ContextTypes.DEFAULT_TYPE, pending: dict, mod_group_id: int):
    """Runs in the background (kicked off by broadcastconfirm via
    asyncio.create_task) so the command handler returns immediately instead
    of holding the mod group's chat open for however long a throttled
    500-recipient send takes (~8-9 minutes at the default pacing).

    Sends are sequential with an explicit sleep between them - see
    BROADCAST_SEND_DELAY_SECONDS - and a failure on one recipient (blocked
    the bot, deleted account, etc.) is logged and counted, not retried
    forever and not allowed to abort the rest of the run.
    """
    text = pending["text"]
    recipients = pending["recipients"]
    total = len(recipients)
    sent = 0
    failed = 0
    try:
        for i, (chat_id, row) in enumerate(recipients, start=1):
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
                sent += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Broadcast send failed for chat_id=%s (row %s)", chat_id, row.get("_row")
                )

            if i % BROADCAST_PROGRESS_EVERY == 0 and i != total:
                await context.bot.send_message(
                    chat_id=mod_group_id,
                    text=f"Broadcast progress: {i}/{total} processed ({sent} sent, {failed} failed)",
                )

            if i != total:
                await asyncio.sleep(BROADCAST_SEND_DELAY_SECONDS)
    finally:
        context.bot_data["broadcast_running"] = False

    await context.bot.send_message(
        chat_id=mod_group_id,
        text=f"Broadcast complete: {sent} sent, {failed} failed, out of {total} funded traders.",
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_mod_group(update, context):
        await query.answer("This only works in the mod group.", show_alert=True)
        return

    store = get_store(context)
    action, id_str = query.data.split(":")
    # Cards used to encode the sheet ROW number at send time (fund:73).
    # That breaks the moment anyone inserts, deletes, or sorts rows above
    # it afterwards - every row below the change shifts, so an old card's
    # button now points at a different, unrelated row (often one with a
    # blank ChatID, which is what "That trader hasn't linked their
    # Telegram" turned out to actually mean - not a data problem, a stale
    # pointer problem). ChatID doesn't move when rows shift, and it's
    # always present by the time a card exists (funding/claim cards only
    # get built after the trader has already linked), so cards now encode
    # that instead and we look the row up by it.
    try:
        chat_id = int(id_str)
    except ValueError:
        await query.answer("This button is from an old card format - use /check and the sheet instead.", show_alert=True)
        return
    row = await asyncio.to_thread(store.find_by_chat_id, chat_id)
    if row is None:
        await query.answer("Couldn't find that trader anymore - check the sheet.", show_alert=True)
        return

    mod_name = query.from_user.first_name or "a mod"

    if action == "fund":
        cfg = await asyncio.to_thread(store.get_config)
        # The challenge clock starts now, per participant - not on a shared
        # Config date. FundedAt is what /status and the deadline shown below
        # are computed from (see bot/deadlines.py).
        funded_at = datetime.now(timezone.utc)
        await asyncio.to_thread(
            store.update_cells,
            row["_row"],
            {"Funded": "TRUE", "GuideSent": "TRUE", "FundedAt": funded_at.isoformat()},
        )
        deadline = compute_deadline(funded_at.isoformat(), cfg.get("challenge_duration_hours"))
        deadline_str = format_deadline(deadline) if deadline else "the deadline"
        await context.bot.send_message(
            chat_id=chat_id,
            text=messages.render(messages.FUNDED_AND_GUIDE, cfg, deadline=deadline_str),
        )
        note = f"\n\n✅ Funded by {mod_name} - ends {deadline_str}"
        if funded_late_in_week(funded_at, cfg.get("challenge_duration_hours")):
            # Display-only nudge - mods still decide, nothing here blocks
            # funding on a Thursday/Friday/weekend.
            note += "\n⚠️ Funded Thu-Sun - this window will include a weekend day"
        # No parse_mode here - see the comment on the "verify" branch below,
        # No parse_mode - see the comment on this same call in the "verify"
        # branch below.
        await query.edit_message_text(f"{query.message.text}{note}")

    elif action == "verify":
        cfg = await asyncio.to_thread(store.get_config)
        await asyncio.to_thread(
            store.update_cells, row["_row"], {"ClaimStatus": "VERIFIED", "ClaimInstructionsSent": "TRUE"}
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=messages.render(messages.CLAIM_VERIFIED, cfg),
        )
        # query.message.text is the card as Telegram rendered it, NOT the
        # raw Markdown source we originally sent - Telegram strips
        # formatting syntax on delivery (the escaped underscores that
        # protected a username like john_the_trader_99 are gone, leaving
        # bare underscores in the plain text). Re-parsing that as Markdown
        # a second time treats those bare underscores as unclosed italic
        # markers and Telegram rejects the whole edit - which was making
        # EVERY Fund/Verify/Reject tap fail whenever the card had an
        # odd number of underscores anywhere in it (very common in
        # usernames). Editing without parse_mode avoids re-parsing
        # already-rendered text as if it were still source.
        await query.edit_message_text(f"{query.message.text}\n\n✅ Verified by {mod_name}")

    elif action == "reject":
        cfg = await asyncio.to_thread(store.get_config)
        await asyncio.to_thread(store.update_cell, row["_row"], "ClaimStatus", "REJECTED")
        await context.bot.send_message(
            chat_id=chat_id,
            text=messages.render(
                messages.CLAIM_REJECTED,
                cfg,
                reason=f"Message a mod if you have questions: {cfg.get('mod_contact_link')}",
            ),
        )
        await query.edit_message_text(f"{query.message.text}\n\n❌ Rejected by {mod_name}")

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
    row = await asyncio.to_thread(store.find_by_row, row_number)
    if row is None or not row.get("ChatID"):
        await update.message.reply_text("Couldn't find that row, or that trader hasn't linked their Telegram yet.")
        return

    await context.bot.send_message(
        chat_id=int(row["ChatID"]),
        text=messages.GROUP_INVITE.format(invite_link=invite_link),
    )
    await update.message.reply_text(f"Sent the invite link to {row.get('Email Address')}.")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage (in the mod group): /check <sheet_row_number> - read-only
    lookup of a trader's status and deadline without leaving the group or
    opening the sheet. Doesn't change anything."""
    if not _is_mod_group(update, context):
        return

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /check <sheet_row_number>")
        return

    store = get_store(context)
    try:
        row_number = int(args[0])
    except ValueError:
        await update.message.reply_text("Row number must be a number (see the card above).")
        return

    row = await asyncio.to_thread(store.find_by_row, row_number)
    if row is None:
        await update.message.reply_text("Couldn't find that row - check the sheet.")
        return

    lines = [
        f"Row {row_number}: {row.get('Email Address') or '-'} (@{row.get('TelegramUsername') or '-'})",
        f"Eligible: {'Yes' if store.is_true(row, 'Eligible') else 'No'}",
        f"Wallet on file: {'Yes' if row.get('WalletAddress') else 'No'}",
        f"Funded: {'Yes' if store.is_true(row, 'Funded') else 'No'}",
    ]

    # Optional column - only shows once the Form question + sheet column
    # for it exist (see README's "Mainnet EVM address" note). Blank for
    # any row from before that was added.
    mainnet_address = row.get("MainnetEVMAddress")
    if mainnet_address:
        lines.append(f"Mainnet EVM address: {mainnet_address}")

    if store.is_true(row, "Funded"):
        cfg = await asyncio.to_thread(store.get_config)
        deadline = compute_deadline(row.get("FundedAt"), cfg.get("challenge_duration_hours"))
        if deadline is not None:
            now = datetime.now(timezone.utc)
            if now > deadline:
                lines.append(f"Deadline: {format_deadline(deadline)} - passed {format_timedelta(now - deadline)} ago")
            else:
                lines.append(f"Deadline: {format_deadline(deadline)} - {format_timedelta(deadline - now)} left")

    lines.append(f"Claim status: {row.get('ClaimStatus') or 'None submitted'}")
    await update.message.reply_text("\n".join(lines))
