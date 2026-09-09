"""Mod-side actions: the inline button taps in the mod group, plus the
/invite command mods use to send a winner's private-group link through the
bot instead of hunting the trader down themselves.

Everything here checks it's being used inside the configured mod group -
these actions should never be reachable by a trader.
"""
import asyncio
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from .. import messages
from ..deadlines import compute_deadline, format_deadline, format_timedelta, funded_late_in_week
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
    row = await asyncio.to_thread(store.find_by_row, int(row_str))
    if row is None:
        await query.answer("Couldn't find that row anymore - check the sheet.", show_alert=True)
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
            chat_id=int(row["ChatID"]),
            text=messages.render(messages.FUNDED_AND_GUIDE, cfg, deadline=deadline_str),
        )
        note = f"\n\n✅ Funded by {mod_name} - ends {deadline_str}"
        if funded_late_in_week(funded_at):
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
            chat_id=int(row["ChatID"]),
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
        await asyncio.to_thread(store.update_cell, row["_row"], "ClaimStatus", "REJECTED")
        await context.bot.send_message(
            chat_id=int(row["ChatID"]),
            text=messages.CLAIM_REJECTED.format(
                reason=f"Message a mod if you have questions: {messages.CONTACT_LINK}"
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
