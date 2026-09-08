"""Builds the cards the bot posts into the mod-only group. Each card carries
inline buttons; tapping one fires bot/handlers/admin_actions.py, which
updates the sheet and messages the trader - that's the whole point of the
mod group: act on a card instead of switching to the spreadsheet.

IMPORTANT: these cards are sent with parse_mode="Markdown". Any dynamic
value that goes into the text (email, username, referral/social proof -
anything that isn't a value the bot itself validated, like WalletAddress's
0x-regex) MUST go through _md() first. An unescaped underscore is enough
to break this - Telegram usernames very often contain one, and legacy
Markdown treats a single "_" as an unclosed italic marker, which makes the
whole send_message call fail. If that call fails, the card silently never
reaches the mod group even though everything before it (writing the sheet,
replying to the trader) already succeeded - so this isn't cosmetic, it's
what makes the mod group actually receive the card at all.
"""

from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from .deadlines import compute_deadline, format_deadline, format_timedelta


def _md(value) -> str:
    """Escapes a value for safe interpolation into a parse_mode="Markdown"
    (legacy) message. Use this on every field that isn't already known to
    be safe (regex-validated, bot-generated, etc.)."""
    return escape_markdown(str(value), version=1)


def _repeat_participant_line(row: dict) -> str:
    """Optional extra line shown on a card when the sheet has repeat-entry
    columns filled in (TimesParticipatedBefore/ReferralProof/SocialProofLink
    - self-reported on the Form, see README). Blank/missing/zero columns
    produce no line at all, so this is a no-op for a normal first-time
    applicant's card."""
    try:
        times_before = int(str(row.get("TimesParticipatedBefore", "")).strip() or 0)
    except ValueError:
        times_before = 0
    if times_before <= 0:
        return ""
    referral = str(row.get("ReferralProof", "")).strip()
    social = str(row.get("SocialProofLink", "")).strip()
    proof = referral or social or "no proof on file"
    return f"🔁 Repeat participant ({times_before}x before) - proof: {_md(proof)}\n"


def wallet_submitted_card(row: dict, cfg: dict):
    text = (
        f"💰 *Wallet submitted*\n"
        f"Email: {_md(row.get('Email Address'))}\n"
        f"Telegram: @{_md(row.get('TelegramUsername') or '-')}\n"
        f"Wallet: `{row.get('WalletAddress')}`\n"
        f"{_repeat_participant_line(row)}\n"
        f"Send the {_md(cfg.get('start_amount', '$5,000'))} testnet USDC, then tap below."
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Mark Funded", callback_data=f"fund:{row['_row']}")]]
    )
    return text, keyboard


def claim_requested_card(row: dict, cfg: dict):
    # Mods decide whether a late claim still counts - see README - so the
    # card needs to show them the deadline and whether this was on time,
    # rather than making them go check /status or the sheet separately.
    deadline_line = ""
    deadline = compute_deadline(row.get("FundedAt"), cfg.get("challenge_duration_hours"))
    if deadline is not None:
        now = datetime.now(timezone.utc)
        if now > deadline:
            deadline_line = f"⏰ Deadline was {format_deadline(deadline)} - claimed {format_timedelta(now - deadline)} late\n"
        else:
            deadline_line = (
                f"⏰ Deadline: {format_deadline(deadline)} - {format_timedelta(deadline - now)} left when claimed\n"
            )

    text = (
        f"🏆 *Claim submitted*\n"
        f"Email: {_md(row.get('Email Address'))}\n"
        f"Telegram: @{_md(row.get('TelegramUsername') or '-')}\n"
        f"Wallet: `{row.get('WalletAddress')}`\n"
        f"{deadline_line}"
        f"{_repeat_participant_line(row)}\n"
        f"Go check their testnet account, then tap below."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Verify win", callback_data=f"verify:{row['_row']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{row['_row']}"),
            ]
        ]
    )
    return text, keyboard
