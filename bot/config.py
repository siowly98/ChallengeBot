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

# Optional - wires this bot up to the separate Veranta Challenges Trading
# Leaderboard so a trader's wallet gets registered there automatically once
# they're funded here (see bot/leaderboard.py and the registration block in
# jobs.py's poll_sheet). LEADERBOARD_API_URL is that leaderboard's base URL
# (e.g. https://veranta-challenges-leaderboard-production.up.railway.app);
# LEADERBOARD_ADMIN_TOKEN is the value of ITS OWN ADMIN_TOKEN env var, sent
# as x-admin-token so the leaderboard's /api/wallets accepts the write.
#
# Both are secrets/infra config, so they're env vars here - not Config tab
# values like leaderboard_url below, which is just display copy shown to
# traders. Leave both unset to run this bot exactly as before, with no
# leaderboard integration at all: registration is skipped silently (not an
# error) whenever either is blank, so upgrading to this version is safe
# even before the leaderboard side is wired up.
LEADERBOARD_API_URL = os.environ.get("LEADERBOARD_API_URL", "").rstrip("/")
LEADERBOARD_ADMIN_TOKEN = os.environ.get("LEADERBOARD_ADMIN_TOKEN", "")

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
    # Where a trader sends back any leftover testnet USDC before being
    # funded - a repeat entrant's wallet can still hold a balance from a
    # previous round, which would let them start this round with more than
    # start_amount (unfair to everyone else). Shown in WALLET_RECEIVED,
    # right after they submit a wallet - see messages.py.
    "withdrawal_address": "0xBB4aD384eA26d0Ea59d01c9DB78D096b8e22b802",
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
    # The CURRENT Veranta Challenges Trading Leaderboard - update this same
    # key in the Config tab if the Railway domain ever changes; this default
    # is only what's used if that Config row is ever missing.
    "leaderboard_url": "https://veranta-challenges-leaderboard-production.up.railway.app/",
    # Kill switch for the leaderboard invite - set to FALSE in the Config
    # tab to stop it going out entirely (e.g. while the leaderboard itself
    # isn't ready yet), no redeploy needed. Defaults to TRUE so existing
    # behavior is unchanged for anyone who doesn't set this.
    "leaderboard_invite_enabled": "TRUE",
    # Kill switch for auto-registering a trader's wallet on the leaderboard
    # (separate from the invite message above - see jobs.py). Set to FALSE
    # in the Config tab to stop it without touching LEADERBOARD_API_URL/
    # LEADERBOARD_ADMIN_TOKEN. Defaults to TRUE - has no effect at all
    # unless those two env vars are also set, since registration is already
    # skipped whenever they're blank.
    "leaderboard_registration_enabled": "TRUE",
    # Optional: a standing Telegram invite link to a separate "prize
    # participants" channel/group. Appended to the leaderboard invite
    # message (see LEADERBOARD_CHANNEL_INVITE_LINE in messages.py) only
    # when this is non-empty - leave it blank to send the plain invite with
    # no channel line at all, e.g. before that channel exists yet.
    "leaderboard_channel_invite_link": "",
    # How long a claim can sit with no Verify/Reject tap before the mod
    # group gets a reminder nudge - see poll_sheet in jobs.py.
    "claim_reminder_delay_hours": "24",
}

# Column layout in the worksheet. Row 1 must be a header row with exactly
# these names (any order - the bot looks columns up by header, not position).
#
# LeaderboardRegistered is new - if you're upgrading an existing sheet, add
# this column to the header row BEFORE deploying this version, or the bot
# will refuse to start (same RuntimeError FundedAt caused when that one was
# added). LeaderboardInviteSent, ClaimRequestedAt, and ClaimReminderSent
# were the previous round of additions.
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
    "LeaderboardRegistered",  # TRUE once this row's wallet has been POSTed to the leaderboard's /api/wallets
    "LeaderboardInviteSent",  # TRUE once the weekly-leaderboard invite has gone out for this row
    "ClaimStatus",       # "", "REQUESTED", "VERIFIED", "REJECTED"
    "ClaimRequestedAt",  # ISO UTC timestamp, stamped when a claim is confirmed - used for the 24h stale-claim reminder
    "ClaimReminderSent",  # TRUE once the mod group has been nudged about a stale REQUESTED claim
    "ClaimInstructionsSent",
    "Notes",
]
