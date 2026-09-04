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

# Column layout in the worksheet. Row 1 must be a header row with exactly
# these names (any order — the bot looks columns up by header, not position).
COLUMNS = [
    "Timestamp",
    "Email",
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
