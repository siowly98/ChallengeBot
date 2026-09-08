"""Small, dependency-free-ish tests for the pieces of logic that are easy
to get subtly wrong: wallet validation and the sheet's truthy parsing.
These don't touch the network or Google Sheets - see README for how to
smoke-test the bot end to end against a real sheet.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("SHEET_ID", "test-sheet")
os.environ.setdefault("MOD_GROUP_CHAT_ID", "-1001234567890")

from bot import messages  # noqa: E402
from bot.deadlines import compute_deadline, format_deadline, funded_late_in_week  # noqa: E402
from bot.handlers import admin, trader  # noqa: E402
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


def _make_callback_update(chat_id, data, first_name="Mod"):
    """Simulates a mod tapping an inline button (Fund/Verify/Reject)."""
    update = MagicMock()
    update.effective_chat.id = chat_id
    query = MagicMock()
    query.data = data
    query.from_user.first_name = first_name
    query.message.text = "Card text"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update, query


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


def test_wallet_command_resends_guide_when_awaiting():
    """/wallet re-sends the acquisition steps to a linked, approved trader
    who hasn't submitted a wallet yet."""
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    store.get_config.return_value = {"wallet_site_url": "testnet.example.com"}
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(111, "/wallet")

    asyncio.run(trader.wallet_guide(update, context))

    sent = update.message.reply_text.call_args[0][0]
    assert "how to get it" in sent.lower()
    assert "testnet.example.com" in sent


def test_wallet_command_when_not_approved():
    store = MagicMock()
    store.find_by_chat_id.return_value = {"_row": 7, "Eligible": "FALSE", "ApprovalSent": "FALSE"}
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(111, "/wallet")

    asyncio.run(trader.wallet_guide(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.WALLET_NOT_APPROVED_YET)


def test_wallet_command_when_already_on_file():
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "0x" + "a" * 40,
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(111, "/wallet")

    asyncio.run(trader.wallet_guide(update, context))

    update.message.reply_text.assert_awaited_once_with(messages.WALLET_ALREADY_ON_FILE)


def test_awaiting_wallet_question_resends_guide_but_bad_address_stays_terse():
    """A waiting trader who types a question gets the guide re-sent; one who
    fumbles an actual 0x address gets the terse 'not valid' nudge."""
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    store.get_config.return_value = {"wallet_site_url": "testnet.example.com"}
    context = MagicMock()
    context.bot_data = {"store": store}

    # a question -> guide re-sent
    q = _make_update(111, "how do i get my wallet??")
    asyncio.run(trader.handle_text(q, context))
    assert "how to get it" in q.message.reply_text.call_args[0][0].lower()

    # a botched 0x address -> terse nudge
    bad = _make_update(111, "0x123")
    asyncio.run(trader.handle_text(bad, context))
    bad.message.reply_text.assert_awaited_once_with(messages.INVALID_WALLET_FORMAT)


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


def test_compute_deadline_adds_duration_hours():
    funded_at = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    deadline = compute_deadline(funded_at.isoformat(), "72")
    assert deadline == funded_at + timedelta(hours=72)


def test_compute_deadline_handles_missing_or_unparseable_input():
    assert compute_deadline("", "72") is None
    assert compute_deadline(None, "72") is None
    assert compute_deadline("not-a-date", "72") is None


def test_compute_deadline_falls_back_to_default_hours_on_bad_config():
    """A blank or non-numeric Challenge Duration Hours shouldn't crash the
    deadline math - fall back to the 72h default instead."""
    funded_at = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    assert compute_deadline(funded_at.isoformat(), "not-a-number") == funded_at + timedelta(hours=72)
    assert compute_deadline(funded_at.isoformat(), "") == funded_at + timedelta(hours=72)


def test_funded_late_in_week():
    assert not funded_late_in_week(datetime(2026, 9, 8, tzinfo=timezone.utc))  # Tuesday
    assert not funded_late_in_week(datetime(2026, 9, 9, tzinfo=timezone.utc))  # Wednesday
    assert funded_late_in_week(datetime(2026, 9, 10, tzinfo=timezone.utc))  # Thursday
    assert funded_late_in_week(datetime(2026, 9, 13, tzinfo=timezone.utc))  # Sunday


def test_fund_action_writes_funded_at_and_computes_deadline(monkeypatch):
    """Tapping Fund stamps FundedAt and renders a concrete deadline into the
    trader's message and the mod card note - not a vague 'time's up'."""
    fixed_now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)  # Tuesday

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(admin, "datetime", _FixedDatetime)

    store = MagicMock()
    store.find_by_row.return_value = {"_row": 3, "ChatID": "555", "Eligible": "TRUE"}
    store.get_config.return_value = {
        "start_amount": "$5,000",
        "target_amount": "$10,000",
        "prize_amount": "$100",
        "challenge_duration": "3 days",
        "challenge_duration_hours": "72",
        "guide_link": "https://example.com/guide",
    }
    context = MagicMock()
    context.bot_data = {"store": store, "mod_group_chat_id": -100}
    context.bot.send_message = AsyncMock()
    update, query = _make_callback_update(-100, "fund:3")

    asyncio.run(admin.handle_button(update, context))

    updates = store.update_cells.call_args[0][1]
    assert updates["Funded"] == "TRUE"
    assert updates["FundedAt"] == fixed_now.isoformat()

    # Deadline = FundedAt + 72h = Fri Sep 11, 12:00 UTC
    sent_text = context.bot.send_message.call_args.kwargs["text"]
    assert "Sep 11" in sent_text
    assert "{deadline}" not in sent_text  # placeholder must actually get filled

    edited_text = query.edit_message_text.call_args[0][0]
    assert "ends" in edited_text
    assert "weekend" not in edited_text.lower()  # Tuesday funding, no warning


def test_fund_action_warns_on_late_week_funding(monkeypatch):
    """Funding on a Thursday/Friday/weekend gets a heads-up note on the mod
    card - display-only, doesn't block the fund action itself."""
    fixed_now = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)  # Thursday

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(admin, "datetime", _FixedDatetime)

    store = MagicMock()
    store.find_by_row.return_value = {"_row": 4, "ChatID": "556", "Eligible": "TRUE"}
    store.get_config.return_value = {
        "start_amount": "$5,000",
        "target_amount": "$10,000",
        "prize_amount": "$100",
        "challenge_duration": "3 days",
        "challenge_duration_hours": "72",
        "guide_link": "https://example.com/guide",
    }
    context = MagicMock()
    context.bot_data = {"store": store, "mod_group_chat_id": -100}
    context.bot.send_message = AsyncMock()
    update, query = _make_callback_update(-100, "fund:4")

    asyncio.run(admin.handle_button(update, context))

    edited_text = query.edit_message_text.call_args[0][0]
    assert "weekend" in edited_text.lower()


def test_status_shows_deadline_when_funded():
    funded_at = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "0x" + "a" * 40,
        "Funded": "TRUE",
        "FundedAt": funded_at.isoformat(),
        "ClaimStatus": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    store.get_config.return_value = {"challenge_duration_hours": "72"}
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(111, "/status")

    asyncio.run(trader.status(update, context))

    sent = update.message.reply_text.call_args[0][0]
    assert "Challenge ends:" in sent
    assert "Sep 11" in sent


def test_status_omits_deadline_when_not_funded():
    store = MagicMock()
    store.find_by_chat_id.return_value = {
        "_row": 7,
        "Eligible": "TRUE",
        "ApprovalSent": "TRUE",
        "WalletAddress": "",
        "Funded": "FALSE",
        "FundedAt": "",
        "ClaimStatus": "",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    context = MagicMock()
    context.bot_data = {"store": store}
    update = _make_update(111, "/status")

    asyncio.run(trader.status(update, context))

    sent = update.message.reply_text.call_args[0][0]
    assert "Challenge ends:" not in sent
    store.get_config.assert_not_called()  # shouldn't fetch config when there's nothing to compute


def test_poll_backfills_funded_at_for_hand_ticked_rows(monkeypatch):
    """A mod ticking Funded=TRUE directly in the sheet (skipping the Fund
    button) must still get a FundedAt stamped - otherwise FUNDED_AND_GUIDE's
    {deadline} placeholder has nothing to render from and this would crash."""
    from bot import jobs

    fixed_now = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(jobs, "datetime", _FixedDatetime)

    store = MagicMock()
    store.all_rows.return_value = [
        {
            "_row": 2,
            "ChatID": "777",
            "Eligible": "TRUE",
            "ApprovalSent": "TRUE",
            "Funded": "TRUE",
            "FundedAt": "",
            "GuideSent": "FALSE",
        }
    ]
    store.get_config.return_value = {
        "start_amount": "$5,000",
        "target_amount": "$10,000",
        "prize_amount": "$100",
        "challenge_duration": "3 days",
        "challenge_duration_hours": "72",
        "guide_link": "https://example.com/guide",
    }
    store.is_true.side_effect = lambda row, col: str(row.get(col, "")).strip().upper() == "TRUE"
    context = MagicMock()
    context.bot_data = {"store": store}
    context.bot.send_message = AsyncMock()

    asyncio.run(jobs.poll_sheet(context))

    writes = [c.args for c in store.update_cell.call_args_list]
    assert (2, "FundedAt", fixed_now.isoformat()) in writes
    sent_text = context.bot.send_message.call_args.kwargs["text"]
    assert "{deadline}" not in sent_text
