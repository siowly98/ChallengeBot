"""HTTP client for registering a trader's wallet on the separate Veranta
Challenges Trading Leaderboard once they're funded here.

This is a one-time *push*, not an ongoing sync: the bot tells the
leaderboard "this handle trades this wallet" once (POST /api/wallets), and
from then on the leaderboard polls that wallet's own trade history straight
from the real Avantis API on its own schedule - this bot has no further
involvement, and no PnL/volume data ever flows back here. Registering a
wallet before it has any real volume is harmless: the leaderboard's own
eligibility gates hide zero-volume rows, so nothing shows up publicly until
the trader actually trades.

Kept as a plain synchronous `requests` call. The caller (jobs.py) always
runs it through `asyncio.to_thread` - the same pattern sheets.py already
uses for its blocking gspread calls - so there's no need to pull in a
separate async HTTP client just for this one endpoint.
"""
from __future__ import annotations

import logging

import requests

from . import config

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15


class LeaderboardNotConfigured(Exception):
    """Raised when LEADERBOARD_API_URL / LEADERBOARD_ADMIN_TOKEN aren't
    set. Callers should treat this as "feature not enabled here", not an
    error - an install that hasn't wired up the leaderboard integration yet
    should keep working exactly as before."""


def register_wallet(telegram_handle: str, wallet_address: str) -> dict:
    """POSTs {telegram_handle, wallet_address} to the leaderboard's
    /api/wallets. Returns the leaderboard's own JSON response
    ({wallet_address, telegram_handle, created}) on success.

    Raises LeaderboardNotConfigured if the integration isn't set up, or
    RuntimeError (carrying the leaderboard's own error message - e.g. "this
    handle already registered with a different wallet") on any non-2xx
    response, so a caller reading the exception message can act on it
    directly instead of seeing a generic failure.
    """
    if not config.LEADERBOARD_API_URL or not config.LEADERBOARD_ADMIN_TOKEN:
        raise LeaderboardNotConfigured(
            "LEADERBOARD_API_URL and/or LEADERBOARD_ADMIN_TOKEN are not set - "
            "leaderboard registration is disabled."
        )
    url = f"{config.LEADERBOARD_API_URL}/api/wallets"
    resp = requests.post(
        url,
        json={"telegram_handle": telegram_handle, "wallet_address": wallet_address},
        headers={"x-admin-token": config.LEADERBOARD_ADMIN_TOKEN},
        timeout=_TIMEOUT_SECONDS,
    )
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        raise RuntimeError(f"Leaderboard registration failed ({resp.status_code}): {detail}")
    return resp.json()
