"""
Thin wrapper around the Google Sheet that acts as the bot's database.

Design choice: the bot never keeps its own state in memory. Every decision
("has this person been approved?", "have we sent the guide yet?") is read
fresh from the sheet, and every action writes straight back to it. That
means a mod can also just edit the sheet by hand (e.g. tick Eligible=TRUE)
and the bot's poll loop will pick it up within POLL_INTERVAL_SECONDS -
no need to go through a bot command for everything.
"""
from __future__ import annotations

import json
import os
import time

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# How long a read is reused before hitting the Sheets API again. This isn't
# about correctness (a mod's hand-edit shows up within this window either
# way, same as it always has via the poll job) - it's about not re-fetching
# the entire table on every single message when many people are messaging
# at once. Writes (update_cell/update_cells) invalidate the rows cache
# immediately, so a handler always sees its own writes right away.
_ROWS_CACHE_TTL_SECONDS = 5
_CONFIG_CACHE_TTL_SECONDS = 20

TRUTHY = {"TRUE", "YES", "Y", "1"}


def _truthy(value) -> bool:
    return str(value).strip().upper() in TRUTHY


def _config_key(raw: str) -> str:
    """Turns a Config sheet's "Key" cell (e.g. "Prize Amount") into the
    matching CONFIG_DEFAULTS/template key ("prize_amount")."""
    return raw.strip().lower().replace(" ", "_")


class SheetStore:
    def __init__(self):
        # On a host like Railway there's no way to commit the credentials
        # file into the repo (it's gitignored on purpose - see README).
        # GOOGLE_CREDENTIALS_JSON lets you paste the whole key file's
        # content into a single env var instead; if it's not set, fall
        # back to reading the file from GOOGLE_CREDENTIALS_PATH, which is
        # how local development works.
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        self._spreadsheet = client.open_by_key(config.SHEET_ID)
        self.sheet = self._spreadsheet.worksheet(config.WORKSHEET_NAME)
        # Startup sanity check only - a local variable, not stored on self.
        # Nothing afterwards should trust a header snapshot taken once at
        # boot (see _col_index's docstring, and all_rows()'s use of
        # config.COLUMNS instead of a cached snapshot, for why).
        header = self.sheet.row_values(1)
        for col in config.COLUMNS:
            if col not in header:
                raise RuntimeError(
                    f"Worksheet '{config.WORKSHEET_NAME}' is missing required column '{col}'. "
                    f"Expected header row: {config.COLUMNS}"
                )

        self._rows_cache: list[dict] | None = None
        self._rows_cache_at = 0.0
        self._config_cache: dict | None = None
        self._config_cache_at = 0.0

    def _col_index(self, col_name: str) -> int:
        """Always re-reads the live header row rather than trusting a
        snapshot cached at startup. The sheet's columns can change without
        the bot restarting - most commonly, adding a question to a Form
        that's linked to this sheet appends a new response column. If a
        write resolved column position from a stale cache, it would
        silently land the value in whatever now sits at that old numeric
        position instead of the actual named column - no error, just wrong
        data. One extra lightweight API call per write is a small price
        for that not happening."""
        header = self.sheet.row_values(1)
        if col_name not in header:
            raise RuntimeError(
                f"Column '{col_name}' not found in the current header row: {header}. "
                "Was it renamed or removed from the sheet?"
            )
        return header.index(col_name) + 1  # gspread is 1-indexed

    def _invalidate_rows_cache(self) -> None:
        self._rows_cache = None

    def all_rows(self) -> list[dict]:
        """Returns every data row as a dict, plus its 1-indexed sheet row number under '_row'.
        Cached briefly (see _ROWS_CACHE_TTL_SECONDS) - any write through this
        store clears the cache immediately, so this never serves stale data
        back to the same request that just wrote something.

        expected_headers is config.COLUMNS (the bot's actual required
        columns), not a snapshot of the live header taken at some earlier
        point in time. gspread requires expected_headers to be a subset of
        the CURRENT header row or it raises - passing a stale snapshot here
        used to mean any drift in the sheet's columns since the bot last
        started (a renamed/retyped/removed column, e.g. while adding a new
        Form question) broke every read in the bot at once, since every
        read goes through this method. config.COLUMNS never goes stale and
        only checks what's actually required, so a new optional column
        (a Form question, a repeat-participant column) never trips it."""
        now = time.monotonic()
        if self._rows_cache is not None and (now - self._rows_cache_at) < _ROWS_CACHE_TTL_SECONDS:
            return self._rows_cache
        records = self.sheet.get_all_records(expected_headers=config.COLUMNS)
        rows = [{**r, "_row": i + 2} for i, r in enumerate(records)]  # +2: header row + 1-index
        self._rows_cache = rows
        self._rows_cache_at = now
        return rows

    def find_by_email(self, email: str) -> dict | None:
        email = email.strip().lower()
        for row in self.all_rows():
            if str(row.get("Email Address", "")).strip().lower() == email:
                return row
        return None

    def find_by_chat_id(self, chat_id: int) -> dict | None:
        for row in self.all_rows():
            if str(row.get("ChatID", "")).strip() == str(chat_id):
                return row
        return None

    def find_by_wallet(self, wallet: str) -> dict | None:
        """Used to block wallet reuse - one wallet address per application,
        so someone can't submit the same funded wallet under a second
        application/Telegram account to try to get funded twice."""
        wallet = wallet.strip().lower()
        for row in self.all_rows():
            if str(row.get("WalletAddress", "")).strip().lower() == wallet:
                return row
        return None

    def find_by_row(self, row_number: int) -> dict | None:
        for row in self.all_rows():
            if row["_row"] == row_number:
                return row
        return None

    def update_cell(self, row_number: int, col_name: str, value) -> None:
        # Delegates to update_cells so single- and multi-cell writes share
        # one code path (and one value_input_option - see below).
        self.update_cells(row_number, {col_name: value})

    def update_cells(self, row_number: int, updates: dict) -> None:
        """Writes several columns for one row in a single API call instead
        of one round trip per column - e.g. linking ChatID + TelegramUsername
        together, or Funded + GuideSent together. Cuts latency (fewer round
        trips) and API quota use (fewer requests) versus one write per column.

        Uses RAW, not USER_ENTERED: this sheet is a database, so values must
        be stored exactly as given. USER_ENTERED would let Sheets reinterpret
        them - a numeric ChatID becomes a float (risking precision loss on
        long IDs), and anything that looked like a formula or date would be
        silently transformed. RAW stores the literal string every time."""
        if not updates:
            return
        data = [
            {
                "range": gspread.utils.rowcol_to_a1(row_number, self._col_index(col)),
                "values": [[value]],
            }
            for col, value in updates.items()
        ]
        self.sheet.batch_update(data, value_input_option="RAW")
        self._invalidate_rows_cache()

    def get_config(self) -> dict:
        """Reads the Config tab (Key | Value columns) into a dict, filling
        in anything missing - or the whole tab, if it doesn't exist yet -
        from CONFIG_DEFAULTS. This is what lets a mod change the challenge
        dates/amounts/prize/links by editing spreadsheet cells instead of
        code. Cached briefly (see _CONFIG_CACHE_TTL_SECONDS) since this gets
        read on nearly every trader-facing message - a round's settings
        don't need to be instant, just eventually-consistent within a few
        seconds, same as the poll job already assumed."""
        now = time.monotonic()
        if self._config_cache is not None and (now - self._config_cache_at) < _CONFIG_CACHE_TTL_SECONDS:
            return self._config_cache

        cfg = dict(config.CONFIG_DEFAULTS)
        try:
            tab = self._spreadsheet.worksheet(config.CONFIG_WORKSHEET_NAME)
        except WorksheetNotFound:
            self._config_cache = cfg
            self._config_cache_at = now
            return cfg
        for row in tab.get_all_records():
            key = _config_key(str(row.get("Key", "")))
            value = str(row.get("Value", "")).strip()
            if key and value:
                cfg[key] = value
        self._config_cache = cfg
        self._config_cache_at = now
        return cfg

    @staticmethod
    def is_true(row: dict, col_name: str) -> bool:
        return _truthy(row.get(col_name, ""))
