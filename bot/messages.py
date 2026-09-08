"""All trader-facing copy lives here so non-engineers can edit wording
without touching handler logic. Keep it plain — see ELI5 note in README."""

# ── Challenge settings — edit these each round, nothing else needs to change ──
CHALLENGE_START_DATE = "Monday, August 31"   # e.g. "Monday, August 31"
CHALLENGE_DURATION = "3 days"                # e.g. "3 days" — the clock starts at funding
START_AMOUNT = "$5,000"
TARGET_AMOUNT = "$10,000"
PRIZE_AMOUNT = "$100"
WALLET_SITE_URL = "testnet.avantisfi.com"    # where traders log in to get their testnet wallet

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
    f"Gmgm 👋 You've been selected for the Avantis {START_AMOUNT} → {TARGET_AMOUNT} Challenge! 🎉\n\n"
    f"The challenge starts {CHALLENGE_START_DATE}. You'll get {START_AMOUNT} in practice funds and have "
    f"{CHALLENGE_DURATION} to reach {TARGET_AMOUNT}+ and win {PRIZE_AMOUNT}. Trade any asset, any leverage.\n\n"
    "⚠️ First step — send us your wallet address:\n\n"
    f"1. Go to {WALLET_SITE_URL}\n"
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
    f"{START_AMOUNT} USDC is in! 🐆🔥\n\n"
    f"You're officially live in the {CHALLENGE_DURATION} {START_AMOUNT} → {TARGET_AMOUNT} Challenge from "
    "this exact moment. ⏱️\n\n"
    f"Reach a {TARGET_AMOUNT}+ balance before time's up and win {PRIZE_AMOUNT}. LFG! 🚀\n\n"
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
    f"Confirmed — you did it! Here's how to claim your {PRIZE_AMOUNT} prize:\n" + "{claim_instructions}"
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
