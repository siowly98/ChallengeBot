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
from .deadlines import compute_deadline, format_deadline, elapsed_since_iso
from .sheets import _truthy

logger = logging.getLogger(__name__)


def _hours(cfg: dict, key: str, default: float) -> float:
    """Reads a Config tab hours value, falling back to `default` if it's
    missing or not a real number - same fail-open approach as
    challenge_duration_hours elsewhere."""
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


async def poll_sheet(context: ContextTypes.DEFAULT_TYPE):
    store = context.bot_data["store"]
    try:
        rows = await asyncio.to_thread(store.all_rows)
        cfg = await asyncio.to_thread(store.get_config)
    except Exception:
        logger.exception("Failed to read sheet during poll")
        return

    now = datetime.now(timezone.utc)
    leaderboard_delay = _hours(cfg, "leaderboard_invite_delay_hours", 48.0)
    claim_reminder_delay = _hours(cfg, "claim_reminder_delay_hours", 24.0)
    # Kill switch - see leaderboard_invite_enabled in config.py. Defaults to
    # TRUE (on) when unset, so existing setups keep working unchanged.
    leaderboard_invite_enabled = _truthy(cfg.get("leaderboard_invite_enabled", "TRUE"))

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

            # Invite to the separate weekly leaderboard a couple of days
            # after funding - unrelated to whether they've claimed
            # anything on this challenge, so it's independent of GuideSent.
            if (
                leaderboard_invite_enabled
                and store.is_true(row, "Funded")
                and not store.is_true(row, "LeaderboardInviteSent")
                and row.get("FundedAt")
            ):
                elapsed = elapsed_since_iso(row.get("FundedAt"), now)
                if elapsed is not None and elapsed.total_seconds() >= leaderboard_delay * 3600:
                    await context.bot.send_message(
                        chat_id=int(chat_id), text=messages.render(messages.LEADERBOARD_INVITE, cfg)
                    )
                    await asyncio.to_thread(store.update_cell, row["_row"], "LeaderboardInviteSent", "TRUE")

            # Nudge the mod group about a claim that's sat unattended (no
            # Verify/Reject tap) for too long - the claim card itself is
            # already louder (see mod_cards.claim_requested_card), this is
            # the backstop for when it still gets missed. elapsed_since_iso
            # is a generic "how long ago was this ISO timestamp" helper
            # despite the name - reused here for ClaimRequestedAt.
            if (
                row.get("ClaimStatus") == "REQUESTED"
                and not store.is_true(row, "ClaimReminderSent")
                and row.get("ClaimRequestedAt")
            ):
                elapsed = elapsed_since_iso(row.get("ClaimRequestedAt"), now)
                if elapsed is not None and elapsed.total_seconds() >= claim_reminder_delay * 3600:
                    # No parse_mode - the email/username below are plugged
                    # in unescaped, and a bare underscore in either would
                    # break a Markdown-parsed send (the exact bug class
                    # fixed in admin.py's card edits - see its comments).
                    await context.bot.send_message(
                        chat_id=context.bot_data["mod_group_chat_id"],
                        text=(
                            f"⏰ Unattended claim - row {row['_row']}, "
                            f"{row.get('Email Address') or '-'} (@{row.get('TelegramUsername') or '-'}) "
                            f"has been waiting on Verify/Reject for over {int(claim_reminder_delay)}h. "
                            f"Use /check {row['_row']} or scroll up to find the card."
                        ),
                    )
                    await asyncio.to_thread(store.update_cell, row["_row"], "ClaimReminderSent", "TRUE")
        except Exception:
            logger.exception("Failed processing row %s during poll", row.get("_row"))
