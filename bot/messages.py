"""All trader-facing copy lives here so non-engineers can edit wording
without touching handler logic. Keep it plain — see ELI5 note in README.

Challenge settings (dates, amounts, prize, links) are NOT hardcoded here.
They live in the "Config" tab of the Google Sheet, so changing them each
round is just editing spreadsheet cells - no code, no git, no redeploy.
See bot/config.py for the full list of keys and bot/sheets.py's
get_config() for how they're read. Any template below with a {placeholder}
like {prize_amount} gets it filled in from that sheet via render()."""


def render(template: str, cfg: dict, **extra) -> str:
    """Fills a message template with the sheet's Config values, plus any
    per-call extras (like `reason` or `invite_link`) that are specific to
    that one message rather than a setting that repeats every round."""
    return template.format(**cfg, **extra)

WELCOME = (
    "Welcome to the Avantis Challenge bot! 👋\n\n"
    "This is how we'll reach you with updates about your application — approval, "
    "your testnet funds, and your challenge results all come through this chat.\n\n"
    "Step 1: reply here with the *exact email address* you used on the application form.\n\n"
    "Send /help anytime if you get stuck."
)

ALREADY_LINKED = "You're already linked. Send /status to check where you're at, or /help for a list of commands."

EMAIL_NOT_FOUND = (
    "We couldn't find that email in our applicant list.\n\n"
    "Double check it's typed exactly as you put it on the form (no extra spaces, "
    "correct capitalization isn't required but spelling is) and send it again.\n\n"
    "Still stuck after a couple tries? Message a mod directly for help — don't keep "
    "guessing emails."
)

HELP = (
    "Here's what I can do:\n\n"
    "/start — link your Telegram to your application (do this first)\n"
    "/status — check where you're at in the process\n"
    "/claim — tell us you've completed the challenge (only works once you're funded)\n"
    "/help — show this message\n\n"
    "Once you're linked, you don't need to do anything else — we'll message you here "
    "at each step. No need to keep checking in."
)

LINK_SUCCESS_NOT_YET_REVIEWED = (
    "Got it — you're linked. We haven't reviewed your application yet. "
    "We'll message you here as soon as there's an update. No need to do anything else for now."
)

APPROVAL_AND_WALLET_REQUEST = (
    "Gmgm 👋 You've been selected for the Avantis {start_amount} → {target_amount} Challenge! 🎉\n\n"
    "The challenge starts {challenge_start_date}. You'll get {start_amount} in practice funds and have "
    "{challenge_duration} to reach {target_amount}+ and win {prize_amount}. Trade any asset, any leverage.\n\n"
    "⚠️ First step — send us your wallet address:\n\n"
    "1. Go to {wallet_site_url}\n"
    "2. Log in using the same method you used when applying — Google, email, or phone.\n"
    "3. Your wallet is created automatically.\n"
    "4. Click your wallet/address in the top-right corner and copy the full address starting with \"0x\".\n"
    "5. Send that full address here.\n\n"
    "⚠️ When you trade, always log back in using that same method/account — otherwise you may end up "
    "trading from a different wallet than the one we fund."
)

WALLET_RECEIVED = (
    "Thanks, we've got your wallet address. We'll send your testnet funds shortly "
    "and message you here once it's done."
)

INVALID_WALLET_FORMAT = (
    "That doesn't look like a valid wallet address (expected something like 0x1234...). "
    "Please double check and send it again."
)

FUNDED_AND_GUIDE = (
    "{start_amount} USDC is in! 🐆🔥\n\n"
    "You're officially live in the {challenge_duration} {start_amount} → {target_amount} Challenge from "
    "this exact moment. ⏱️\n\n"
    "Reach a {target_amount}+ balance before time's up and win {prize_amount}. LFG! 🚀\n\n"
    "Setup guide, in case you need it:\n{guide_link}\n\n"
    "When you think you've hit the target, come back here and send /claim.\n\n"
    "Also — if you want to share your challenge journey on social media, send us the link, we'd love to "
    "support and amplify it! 🫡"
)

CLAIM_NOT_ELIGIBLE = (
    "We don't have you marked as funded yet, so there's nothing to claim yet. "
    "If you think this is a mistake, let a mod know."
)

CLAIM_RECEIVED = (
    "Claim received! We're manually checking your account now — this isn't instant, "
    "we'll message you here once it's confirmed."
)

CLAIM_ALREADY_SUBMITTED = (
    "You've already got a claim in for review. Sit tight, we'll message you once it's checked."
)

CLAIM_VERIFIED = (
    "Confirmed — you did it! Here's how to claim your {prize_amount} prize:\n{claim_instructions_link}"
)

CLAIM_REJECTED = (
    "We checked your account and couldn't confirm the challenge was completed. "
    "{reason}"
)

GROUP_INVITE = (
    "Congrats again! Here's your invite to a private chat with the team:\n{invite_link}"
)

STATUS_UNLINKED = "You haven't linked your Telegram yet — send /start first, then reply with your application email."

UNKNOWN_MESSAGE = "Not sure what to do with that. Send /status to check where you're at, or /help for commands."

STATUS_TEMPLATE = (
    "Your status:\n"
    "- Approved: {eligible}\n"
    "- Wallet on file: {has_wallet}\n"
    "- Funded: {funded}\n"
    "- Claim status: {claim_status}\n"
)
