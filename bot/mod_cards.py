"""Builds the cards the bot posts into the mod-only group. Each card carries
inline buttons; tapping one fires bot/handlers/admin_actions.py, which
updates the sheet and messages the trader — that's the whole point of the
mod group: act on a card instead of switching to the spreadsheet."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def wallet_submitted_card(row: dict):
    text = (
        f"💰 *Wallet submitted*\n"
        f"Email: {row.get('Email Address')}\n"
        f"Telegram: @{row.get('TelegramUsername') or '—'}\n"
        f"Wallet: `{row.get('WalletAddress')}`\n\n"
        f"Send the $5,000 testnet USDC, then tap below."
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Mark Funded", callback_data=f"fund:{row['_row']}")]]
    )
    return text, keyboard


def claim_requested_card(row: dict):
    text = (
        f"🏆 *Claim submitted*\n"
        f"Email: {row.get('Email Address')}\n"
        f"Telegram: @{row.get('TelegramUsername') or '—'}\n"
        f"Wallet: `{row.get('WalletAddress')}`\n\n"
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
