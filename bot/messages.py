"""All trader-facing copy lives here so non-engineers can edit wording
without touching handler logic. Keep it plain - see ELI5 note in README.

Challenge settings (duration, amounts, prize, links) are NOT hardcoded
here. They live in the "Config" tab of the Google Sheet, so changing them
each round is just editing spreadsheet cells - no code, no git, no
redeploy. See bot/config.py for the full list of keys and bot/sheets.py's
get_config() for how they're read. Any template below with a {placeholder}
like {prize_amount} gets it filled in from that sheet via render().

One exception: {deadline} in FUNDED_AND_GUIDE isn't a Config value - it's
computed per participant from their own FundedAt timestamp (see
bot/deadlines.py), since the challenge clock starts when THEY get funded,
not on a shared date. It's passed in as a render() extra by whichever
handler sends that message (the Fund button in admin.py, or the poll
loop in jobs.py for hand-ticked rows)."""

# Where to send someone who needs a human - linked from every message that
# tells a trader to "message a mod".
CONTACT_LINK = "https://t.me/AvantisChallenges/6/27"


def render(template: str, cfg: dict, **extra) -> str:
    """Fills a message template with the sheet's Config values, plus any
    per-call extras (like `reason` or `invite_link`) that are specific to
    that one message rather than a setting that repeats every round."""
    return template.format(**cfg, **extra)

WELCOME = (
    "Welcome to the Avantis Challenge bot! 👋\n\n"
    "This is how we'll reach you with updates about your application - approval, "
    "your testnet funds, and your challenge results all come through this chat.\n\n"
    "Step 1: reply here with the *exact email address* you used on the application form.\n\n"
    "Send /help anytime if you get stuck."
)

ALREADY_LINKED = "You're already linked. Send /status to check where you're at, or /help for a list of commands."

EMAIL_NOT_FOUND = (
    "We couldn't find that email in our applicant list.\n\n"
    "Double check it's typed exactly as you put it on the form (no extra spaces, "
    "correct capitalization isn't required but spelling is) and send it again.\n\n"
    f"Still stuck after a couple tries? Message a mod directly for help: {CONTACT_LINK}"
)

DUPLICATE_EMAIL = (
    "That email is already linked to a different Telegram account.\n\n"
    "Each application can only be linked once. If this is your email and you think "
    f"something's wrong, message a mod here: {CONTACT_LINK}"
)

DUPLICATE_WALLET = (
    "That wallet address is already registered under a different application.\n\n"
    "Each wallet can only be used once - but you're not stuck. Just send a different "
    "wallet address here and we'll use that one instead. (If you logged in with the "
    "wrong account, log back in with the right one and copy that address.)\n\n"
    f"Don't have another wallet, or think this is a mistake? Message a mod: {CONTACT_LINK}"
)

HELP = (
    "Here's what I can do:\n\n"
    "/start - link your Telegram to your application (do this first)\n"
    "/status - check where you're at in the process\n"
    "/wallet - show the steps to get your testnet wallet address again\n"
    "/claim - tell us you've completed the challenge (only works once you're funded)\n"
    "/help - show this message\n\n"
    "Once you're linked, you don't need to do anything else - we'll message you here "
    "at each step. No need to keep checking in.\n\n"
    f"Need a human? Message a mod: {CONTACT_LINK}"
)

LINK_SUCCESS_NOT_YET_REVIEWED = (
    "Got it - you're linked. We haven't reviewed your application yet. "
    "We'll message you here as soon as there's an update. No need to do anything else for now."
)

# The wallet-acquisition steps, kept on their own so they can be re-sent via
# /wallet (or when a waiting trader types a question instead of an address)
# without repeating the "you've been selected" preamble each time. Written to
# read correctly both standalone and appended after the approval preamble.
WALLET_GUIDE = (
    "⚠️ Send us your wallet address. Here's how to get it:\n\n"
    "1. Go to {wallet_site_url}\n"
    "2. Log in using the same method you used when applying - Google, email, or phone.\n"
    "3. Your wallet is created automatically.\n"
    "4. Click your wallet/address in the top-right corner and copy the full address starting with \"0x\".\n"
    "5. Send that full address here.\n\n"
    "⚠️ When you trade, always log back in using that same method/account - otherwise you may end up "
    "trading from a different wallet than the one we fund."
)

APPROVAL_AND_WALLET_REQUEST = (
    "Gmgm 👋 You've been selected for the Avantis {start_amount} → {target_amount} Challenge! 🎉\n\n"
    "Your {challenge_duration} clock starts the moment we fund your wallet, not before - so there's no rush "
    "right now. You'll get {start_amount} in practice funds and have to reach {target_amount}+ to win "
    "{prize_amount}. Trade any asset, any leverage.\n\n"
    + WALLET_GUIDE
)

WALLET_NOT_APPROVED_YET = (
    "You're linked, but you haven't been approved for this round yet - so there's no wallet to submit "
    "just yet. We'll message you here the moment you're selected, with the steps to get your wallet. "
    "Send /status anytime to check where you're at."
)

WALLET_ALREADY_ON_FILE = (
    "We've already got your wallet address on file - nothing more to do on your end. "
    "Send /status to check where you're at."
)

WALLET_RECEIVED = (
    "Thanks, we've got your wallet address. We'll send your testnet funds shortly "
    "and message you here once it's done."
)

WALLET_SUBMIT_RETRY = (
    "Hmm, something went wrong on our end saving that and we couldn't log it properly. "
    "Nothing's lost - please send your wallet address here again in a moment.\n\n"
    f"If it keeps failing, message a mod: {CONTACT_LINK}"
)

INVALID_WALLET_FORMAT = (
    "That doesn't look like a valid wallet address (expected something like 0x1234...). "
    "Please double check and send it again."
)

FUNDED_AND_GUIDE = (
    "{start_amount} USDC is in! 🐆🔥\n\n"
    "You're officially live in the {challenge_duration} {start_amount} → {target_amount} Challenge from "
    "this exact moment. ⏱️\n\n"
    "Reach a {target_amount}+ balance before {deadline} and win {prize_amount}. LFG! 🚀\n\n"
    "Read the full rules and details here:\n{guide_link}\n\n"
    "When you think you've hit the target, come back here and send /claim.\n\n"
    "Also - if you want to share your challenge journey on social media, send us the link, we'd love to "
    "support and amplify it! 🫡"
)

CLAIM_NOT_ELIGIBLE = (
    "We don't have you marked as funded yet, so there's nothing to claim yet. "
    f"If you think this is a mistake, let a mod know: {CONTACT_LINK}"
)

CLAIM_RECEIVED = (
    "Claim received! We're manually checking your account now - this isn't instant, "
    "we'll message you here once it's confirmed."
)

CLAIM_SUBMIT_RETRY = (
    "Hmm, something went wrong on our end submitting that claim and we couldn't log it "
    "properly. Nothing's lost - please send /claim again in a moment.\n\n"
    f"If it keeps failing, message a mod: {CONTACT_LINK}"
)

CLAIM_ALREADY_SUBMITTED = (
    "You've already got a claim in for review. Sit tight, we'll message you once it's checked."
)

CLAIM_VERIFIED = (
    "Confirmed - you did it! Here's how to claim your {prize_amount} prize:\n{claim_instructions_link}"
)

CLAIM_REJECTED = (
    "We checked your account and couldn't confirm the challenge was completed. "
    "{reason}"
)

GROUP_INVITE = (
    "Congrats again! Here's your invite to a private chat with the team:\n{invite_link}"
)

STATUS_UNLINKED = "You haven't linked your Telegram yet - send /start first, then reply with your application email."

UNKNOWN_MESSAGE = "Not sure what to do with that. Send /status to check where you're at, or /help for commands."

STATUS_TEMPLATE = (
    "Your status:\n"
    "- Approved: {eligible}\n"
    "- Wallet on file: {has_wallet}\n"
    "- Funded: {funded}\n"
    "{deadline_line}"
    "- Claim status: {claim_status}\n"
)
