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
    "challenge_duration": "3 days",
    # Numeric twin of challenge_duration, used for actual deadline math
    # (FundedAt + this many hours) - see bot/deadlines.py. Keep this in
    # sync with challenge_duration by hand (e.g. "3 days" -> "72").
    "challenge_duration_hours": "72",
    "start_amount": "$5,000",
    "target_amount": "$10,000",
    "prize_amount": "$100",
    "wallet_site_url": "testnet.avantisfi.com",
    "guide_link": "https://your-doc-link-here/setup-guide",
    "claim_instructions_link": "https://your-doc-link-here/claim-instructions",
    # Shown when someone messages the bot with an email that's not in the
    # Applicants sheet - covers the case where they found the bot before
    # ever filling out the application (see EMAIL_NOT_FOUND in messages.py).
    "google_form_link": "https://your-form-link-here",
    # Minimum time a trader must wait after being funded before /claim
    # does anything - blocks the reflexive tap right after the funded
    # message arrives (it's the message that tells them /claim exists),
    # long before they could've plausibly reached the target balance.
    # Doesn't verify they actually hit the target - that's still a manual
    # mod check - it just filters out claims that are obviously too early.
    "min_claim_delay_minutes": "15",
    # Where every "message a mod" line in trader-facing copy points.
    # Placeholder is the old Avantis group - update this in the Config tab
    # once the new Veranta group/link exists, no redeploy needed.
    "mod_contact_link": "https://t.me/AvantisChallenges/6/27",
    # How long after funding to invite someone to the separate weekly
    # rolling leaderboard (top-3 PnL cash + raffles) - see LEADERBOARD_INVITE
    # in messages.py and poll_sheet in jobs.py.
    "leaderboard_invite_delay_hours": "48",
    "leaderboard_url": "https://avantis-traders-club.up.railway.app/",
    # How long a claim can sit with no Verify/Reject tap before the mod
    # group gets a reminder nudge - see poll_sheet in jobs.py.
    "claim_reminder_delay_hours": "24",
}

# Column layout in the worksheet. Row 1 must be a header row with exactly
# these names (any order - the bot looks columns up by header, not position).
#
# LeaderboardInviteSent, ClaimRequestedAt, and ClaimReminderSent are new -
# if you're upgrading an existing sheet, add these three columns to the
# header row BEFORE deploying this version, or the bot will refuse to
# start (same RuntimeError FundedAt caused when that one was added).
COLUMNS = [
    "Timestamp",
    "Email Address",
    "TelegramUsername",
    "ChatID",
    "Eligible",
    "ApprovalSent",
    "WalletAddress",
    "Funded",
    "FundedAt",         # ISO UTC timestamp, written when a mod clicks Fund - the challenge clock starts here
    "GuideSent",
    "LeaderboardInviteSent",  # TRUE once the weekly-leaderboard invite has gone out for this row
    "ClaimStatus",       # "", "REQUESTED", "VERIFIED", "REJECTED"
    "ClaimRequestedAt",  # ISO UTC timestamp, stamped when a claim is confirmed - used for the 24h stale-claim reminder
    "ClaimReminderSent",  # TRUE once the mod group has been nudged about a stale REQUESTED claim
    "ClaimInstructionsSent",
    "Notes",
]
