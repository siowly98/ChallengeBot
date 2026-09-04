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

import gspread
from google.oauth2.service_account import Credentials

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TRUTHY = {"TRUE", "YES", "Y", "1"}


def _truthy(value) -> bool:
    return str(value).strip().upper() in TRUTHY


class SheetStore:
    def __init__(self):
        creds = Credentials.from_service_account_file(config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(config.SHEET_ID).worksheet(config.WORKSHEET_NAME)
        self._header = self.sheet.row_values(1)
        for col in config.COLUMNS:
            if col not in self._header:
                raise RuntimeError(
                    f"Worksheet '{config.WORKSHEET_NAME}' is missing required column '{col}'. "
                    f"Expected header row: {config.COLUMNS}"
                )

    def _col_index(self, col_name: str) -> int:
        # gspread is 1-indexed
        return self._header.index(col_name) + 1

    def all_rows(self) -> list[dict]:
        """Returns every data row as a dict, plus its 1-indexed sheet row number under '_row'."""
        records = self.sheet.get_all_records(expected_headers=self._header)
        return [{**r, "_row": i + 2} for i, r in enumerate(records)]  # +2: header row + 1-index

    def find_by_email(self, email: str) -> dict | None:
        email = email.strip().lower()
        for row in self.all_rows():
            if str(row.get("Email", "")).strip().lower() == email:
                return row
        return None

    def find_by_chat_id(self, chat_id: int) -> dict | None:
        for row in self.all_rows():
            if str(row.get("ChatID", "")).strip() == str(chat_id):
                return row
        return None

    def find_by_row(self, row_number: int) -> dict | None:
        for row in self.all_rows():
            if row["_row"] == row_number:
                return row
        return None

    def update_cell(self, row_number: int, col_name: str, value) -> None:
        self.sheet.update_cell(row_number, self._col_index(col_name), value)

    @staticmethod
    def is_true(row: dict, col_name: str) -> bool:
        return _truthy(row.get(col_name, ""))
