"""Small, dependency-free-ish tests for the pieces of logic that are easy
to get subtly wrong: wallet validation and the sheet's truthy parsing.
These don't touch the network or Google Sheets - see README for how to
smoke-test the bot end to end against a real sheet.
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("SHEET_ID", "test-sheet")
os.environ.setdefault("MOD_GROUP_CHAT_ID", "-1001234567890")

from bot import messages  # noqa: E402
from bot.handlers import trader  # noqa: E402
from bot.handlers.trader import WALLET_RE  # noqa: E402
from bot.messages import render  # noqa: E402
from bot.mod_cards import claim_requested_card, wallet_submitted_card  # noqa: E402
from bot.sheets import _config_key, _truthy  # noqa: E402


def test_valid_wallet_address():
    assert WALLET_RE.match("0x1234567890abcdef1234567890abcdef12345678")


def test_wallet_address_wrong_length_rejected():
    assert not WALLET_RE.match("0x1234")


def test_wallet_address_missing_prefix_rejected():
    assert not WALLET_RE.match("1234567890abcdef1234567890abcdef12345678")


def test_truthy_values():
    for v in ["TRUE", "true", "Yes", "y", "1", " TRUE "]:
        assert _truthy(v) is True


def test_falsy_values():
    for v in ["", "FALSE", "no", "0", None]:
        assert _truthy(v) is False


def test_config_key_normalizes_sheet_header_style():
    assert _config_key("Prize Amount") == "prize_amount"
    assert _config_key(" Wallet Site URL ") == "wallet_site_url"


def test_render_fills_config_and_extra_placeholders():
    cfg = {"prize_amount": "$100"}
    result = render("Win {prize_amount}, here: {claim_instructions_link}", cfg, claim_instructions_link="x.co")
    assert result == "Win $100, here: x.co"


def _make_update(chat_id, text):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user.username = "leo"
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def test_duplicate_email_is_blocked():
    """A second Telegram account can't link to an application email that's
    already linked to someone else's account."""
    store = MagicMock()
    store.find_by_chat_id.return_value = None
    store.find_by_email.return_value = {"_row": 5, "ChatID": "999999", "Eligible": "FALSE"}
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(111111, "a@x.com")

    asyncio.run(trader.handle_text(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.DUPLICATE_EMAIL)
    store.update_cells.assert_not_called()


def test_duplicate_wallet_is_blocked():
    """The same wallet address can't be reused across two different rows."""
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    store.find_by_wallet.return_value = {"_row": 42, "WalletAddress": "0x" + "a" * 40}
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(222222, "0x" + "a" * 40)

    asyncio.run(trader.handle_text(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.DUPLICATE_WALLET)
    store.update_cell.assert_not_called()


def test_resubmitting_own_wallet_is_not_blocked():
    """find_by_wallet matching the SAME row (not a different one) must not
    trip the duplicate-wallet check."""
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    store.find_by_wallet.return_value = {"_row": 7, "WalletAddress": "0x" + "a" * 40}
    context = MagicMock()
    context.bot_data = {"store": store, "mod_group_chat_id": -100}
    context.bot.send_message = AsyncMock()
    update = _make_update(333333, "0x" + "a" * 40)

    asyncio.run(trader.handle_text(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.WALLET_RECEIVED)


def test_wallet_card_failure_rolls_back_the_write(monkeypatch):
    """If the mod card can't be delivered, the WalletAddress write must be
    rolled back so the row returns to 'awaiting wallet' and the trader can
    resend - not left stuck with a wallet on file and no fundable card."""
    monkeypatch.setattr(trader.asyncio, "sleep", AsyncMock())  # skip the retry delay
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    store.find_by_wallet.return_value = None
    context = MagicMock()
    context.bot_data = {"store": store, "mod_group_chat_id": -100}
    context.bot.send_message = AsyncMock(side_effect=RuntimeError("mod group unreachable"))
    update = _make_update(333333, "0x" + "a" * 40)

    asyncio.run(trader.handle_text(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.WALLET_SUBMIT_RETRY)
    # The wallet was written, then rolled back to "" - both writes present.
    writes = [c.args for c in store.update_cell.call_args_list]
    assert (7, "WalletAddress", "0x" + "a" * 40) in writes
    assert (7, "WalletAddress", "") in writes
    assert writes[-1] == (7, "WalletAddress", "")  # rollback is the last write


def test_claim_card_failure_rolls_back_the_status(monkeypatch):
    """Same guarantee for /claim: a failed card send rolls ClaimStatus back
    to '' so the trader can send /claim again."""
    monkeypatch.setattr(trader.asyncio, "sleep", AsyncMock())
    store = MagicMock()
    store.find_by_chat_id.return_value = {"_row": 9, "Funded": "TRUE", "ClaimStatus": ""}
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    context = MagicMock()
    context.bot_data = {"store": store, "mod_group_chat_id": -100}
    context.bot.send_message = AsyncMock(side_effect=RuntimeError("mod group unreachable"))
    update = _make_update(444444, "/claim")

    asyncio.run(trader.claim(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.CLAIM_SUBMIT_RETRY)
    writes = [c.args for c in store.update_cell.call_args_list]
    assert (9, "ClaimStatus", "REQUESTED") in writes
    assert writes[-1] == (9, "ClaimStatus", "")  # rollback is the last write


def test_mod_card_escapes_underscores_in_dynamic_fields():
    """Regression test: a username/email/referral-proof containing a raw
    underscore used to break Telegram's legacy Markdown parser (an
    unbalanced "_" is an unclosed italic marker), which made the whole
    send_message call to the mod group fail silently - the trader would
    get WALLET_RECEIVED but the mod group would never see the card. Every
    underscore coming from row data must show up backslash-escaped."""
    row = {
        "_row": 5,
        "Email Address": "john_doe.test@x.com",
        "TelegramUsername": "john_the_trader_99",
        "WalletAddress": "0x" + "a" * 40,
        "TimesParticipatedBefore": "1",
        "ReferralProof": "@friend_one, @friend_two_x, @friend_3",
    }
    text, _ = wallet_submitted_card(row, {"start_amount": "$5,000"})
    assert "john\\_doe.test@x.com" in text
    assert "john\\_the\\_trader\\_99" in text
    assert "@friend\\_one, @friend\\_two\\_x, @friend\\_3" in text
    assert "john_the_trader_99" not in text  # the raw, unescaped form must not appear

    text2, _ = claim_requested_card(row)
    assert "john\\_the\\_trader\\_99" in text2
    assert "john_the_trader_99" not in text2
