"""Small, dependency-free-ish tests for the pieces of logic that are easy
to get subtly wrong: wallet validation and the sheet's truthy parsing.
These don't touch the network or Google Sheets - see README for how to
smoke-test the bot end to end against a real sheet.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("SHEET_ID", "test-sheet")
os.environ.setdefault("MOD_GROUP_CHAT_ID", "-1001234567890")

from bot.handlers.trader import WALLET_RE  # noqa: E402
from bot.sheets import _truthy  # noqa: E402


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
