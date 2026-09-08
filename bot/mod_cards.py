"""Builds the cards the bot posts into the mod-only group. Each card carries
inline buttons; tapping one fires bot/handlers/admin_actions.py, which
updates the sheet and messages the trader - that's the whole point of the
mod group: act on a card instead of switching to the spreadsheet."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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
    return f"🔁 Repeat participant ({times_before}x before) - proof: {proof}\n"


def wallet_submitted_card(row: dict, cfg: dict):
    text = (
        f"💰 *Wallet submitted*\n"
        f"Email: {row.get('Email Address')}\n"
        f"Telegram: @{row.get('TelegramUsername') or '-'}\n"
        f"Wallet: `{row.get('WalletAddress')}`\n"
        f"{_repeat_participant_line(row)}\n"
        f"Send the {cfg.get('start_amount', '$5,000')} testnet USDC, then tap below."
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Mark Funded", callback_data=f"fund:{row['_row']}")]]
    )
    return text, keyboard


def claim_requested_card(row: dict):
    text = (
        f"🏆 *Claim submitted*\n"
        f"Email: {row.get('Email Address')}\n"
        f"Telegram: @{row.get('TelegramUsername') or '-'}\n"
        f"Wallet: `{row.get('WalletAddress')}`\n"
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
