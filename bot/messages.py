"""All trader-facing copy lives here so non-engineers can edit wording
without touching handler logic. Keep it plain — see ELI5 note in README."""

WELCOME = (
    "Welcome to the Avantis Challenge bot!\n\n"
    "Please reply with the email address you used on the application form."
)

EMAIL_NOT_FOUND = (
    "We couldn't find that email in our applicant list. "
    "Double check it matches exactly what you put on the form, and try again."
)

LINK_SUCCESS_NOT_YET_REVIEWED = (
    "Got it — you're linked. We haven't reviewed your application yet. "
    "We'll message you here as soon as there's an update. No need to do anything else for now."
)

APPROVAL_AND_WALLET_REQUEST = (
    "Good news — you've been approved for the Avantis Challenge!\n\n"
    "Reply here with your wallet address so we can send your $5,000 testnet USDC."
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
    "You're funded! $5,000 testnet USDC has been sent to your wallet.\n\n"
    "Here's your setup guide:\n{guide_link}\n\n"
    "Goal: turn $5,000 into $10,000. When you think you've done it, come back here and send /claim."
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
    "Confirmed — you did it! Here's how to claim your $100 prize:\n{claim_instructions}"
)

CLAIM_REJECTED = (
    "We checked your account and couldn't confirm the challenge was completed. "
    "{reason}"
)

GROUP_INVITE = (
    "Congrats again! Here's your invite to a private chat with the team:\n{invite_link}"
)

STATUS_UNLINKED = "You haven't linked your Telegram yet — send /start first."

STATUS_TEMPLATE = (
    "Your status:\n"
    "- Approved: {eligible}\n"
    "- Wallet on file: {has_wallet}\n"
    "- Funded: {funded}\n"
    "- Claim status: {claim_status}\n"
)
