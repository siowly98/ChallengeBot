import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}. Copy .env.example to .env and fill it in.")
    return value


BOT_TOKEN = _require("BOT_TOKEN")
SHEET_ID = _require("SHEET_ID")
WORKSHEET_NAME = os.environ.get("WORKSHEET_NAME", "Applicants")
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials/service_account.json")
MOD_GROUP_CHAT_ID = int(_require("MOD_GROUP_CHAT_ID"))
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))

# Name of the sheet tab that holds per-round settings (Key | Value columns).
# See README for the exact keys the bot reads - editing this tab is how you
# change the challenge dates/amounts/prize/links each round, no code or git
# required.
CONFIG_WORKSHEET_NAME = os.environ.get("CONFIG_WORKSHEET_NAME", "Config")

# Used for any key missing from the Config tab, or if the tab doesn't exist
# yet at all - the bot falls back to these instead of crashing, so it's safe
# to add the tab gradually.
CONFIG_DEFAULTS = {
    "challenge_start_date": "Monday, August 31",
    "challenge_duration": "3 days",
    "start_amount": "$5,000",
    "target_amount": "$10,000",
    "prize_amount": "$100",
    "wallet_site_url": "testnet.avantisfi.com",
    "guide_link": "https://your-doc-link-here/setup-guide",
    "claim_instructions_link": "https://your-doc-link-here/claim-instructions",
}

# Column layout in the worksheet. Row 1 must be a header row with exactly
# these names (any order - the bot looks columns up by header, not position).
COLUMNS = [
    "Timestamp",
    "Email Address",
    "TelegramUsername",
    "ChatID",
    "Eligible",
    "ApprovalSent",
    "WalletAddress",
    "Funded",
    "GuideSent",
    "ClaimStatus",       # "", "REQUESTED", "VERIFIED", "REJECTED"
    "ClaimInstructionsSent",
    "Notes",
]
