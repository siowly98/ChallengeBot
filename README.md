# Avantis Challenge Bot

Automates the Telegram side of running the Avantis Challenge: linking applicants
to the bot, sending approval/wallet-request/guide messages automatically, and
giving mods a single group chat with tap-to-act buttons instead of manually
DMing hundreds of people from a personal account.

**What this bot does not do:** decide who's eligible, send the actual testnet
USDC, or verify who won. Those stay human calls — the bot just carries every
message so a mod doesn't have to manually find and DM each trader.

## How it works (high level)

The Google Sheet your Form already writes responses to is the bot's entire
database. The bot never stores anything else in memory — every decision is
read fresh from the sheet, every action writes straight back to it. That
means a mod can also just edit the sheet by hand and the bot will notice
and act on it within `POLL_INTERVAL_SECONDS`.

1. Applicant fills the Google Form (unchanged).
2. Applicant messages the bot, sends `/start`, replies with their email →
   bot matches it to their form row and stores their Telegram chat ID.
3. A mod ticks `Eligible = TRUE` on their row (in the sheet, however you're
   already reviewing responses) → bot auto-DMs approval + asks for wallet.
4. Applicant replies with a wallet address → bot saves it and posts a card
   in the mod group with a **Mark Funded** button.
5. Mod sends the actual testnet USDC (still manual) and taps the button →
   bot auto-DMs the funded confirmation + setup guide.
6. Trader sends `/claim` when they think they've doubled their account →
   bot posts a card in the mod group with **Verify** / **Reject** buttons.
7. Mod manually checks the account (still manual, still a human call) and
   taps a button → bot auto-DMs claim instructions or a rejection.
8. For winners: a mod manually creates the 1:1 private group (low volume,
   not worth automating) and sends the invite link through the bot with
   `/invite <sheet_row> <link>` instead of hunting the trader down.

## Setup

### 1. Create the bot

Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`,
follow the prompts. Copy the token it gives you into `.env` as `BOT_TOKEN`.

### 2. Set up the Google Sheet

Use (or create) a Google Sheet with a tab whose **first row** has exactly
these column headers (order doesn't matter, spelling does):

```
Timestamp | Email Address | TelegramUsername | ChatID | Eligible | ApprovalSent |
WalletAddress | Funded | GuideSent | ClaimStatus | ClaimInstructionsSent | Notes
```

If your Google Form responses already land in a sheet, just add the
columns the bot manages (`TelegramUsername`, `ChatID`, `Eligible`,
`ApprovalSent`, `WalletAddress`, `Funded`, `GuideSent`, `ClaimStatus`,
`ClaimInstructionsSent`, `Notes`) to that same tab — `Timestamp` and
`Email Address` should already be there from the Form. Note:
`TelegramUsername` (bot-managed) is separate from any self-reported
"Your Telegram @username" column your form already has — keep both.

`Eligible` and `Funded` are the two columns a mod ticks by hand when
reviewing (checkbox format works fine — the bot reads TRUE/FALSE/YES/1 as
"true", anything else as "false"). Everything else the bot fills in itself.

### 3. Give the bot access to the sheet (Google service account)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project (or use an existing one) and enable the **Google Sheets API**.
2. Create a **Service Account**, then create a JSON key for it and download
   it.
3. Save that file as `credentials/service_account.json` (this path is
   already git-ignored — never commit it).
4. Open the JSON file, copy the `client_email` value, and **share your
   Google Sheet** with that email address (Editor access) — same as
   sharing with a person.

### 4. Create the mod group

Create a private Telegram group with just your mods in it, add the bot to
it. To find the group's chat ID: temporarily add
[@userinfobot](https://t.me/userinfobot) to the group, it'll post the
group's ID (a negative number like `-1001234567890`), then remove it.
Put that number in `.env` as `MOD_GROUP_CHAT_ID`.

### 5. Configure and run

```bash
cp .env.example .env
# fill in BOT_TOKEN, SHEET_ID (from your sheet's URL), MOD_GROUP_CHAT_ID

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 -m bot.main
```

If it starts without errors, message your bot `/start` to test the flow.

### 6. Add the Config tab (challenge settings)

Add a second tab to the same Google Sheet, named exactly `Config`, with two
columns: `Key` and `Value`. This is where you set the things that change
every round — no code, no Terminal, no git required. Fill in a row for
each of these keys:

| Key | Example value |
| --- | --- |
| `Challenge Start Date` | `Monday, August 31` |
| `Challenge Duration` | `3 days` |
| `Start Amount` | `$5,000` |
| `Target Amount` | `$10,000` |
| `Prize Amount` | `$100` |
| `Wallet Site URL` | `testnet.avantisfi.com` |
| `Guide Link` | link to your setup guide |
| `Claim Instructions Link` | link to your prize-claim instructions |

Key names aren't case-sensitive and ignore spacing (`Prize Amount`,
`prize amount`, and `PRIZE_AMOUNT` all work) — use whatever's readable.
If you leave the whole tab out, or leave a row blank, the bot just uses
its built-in defaults for that value instead of breaking, so you can add
this gradually. Changes take effect on the very next message the bot
sends — no restart needed.

## Deploying so it runs continuously

This bot uses long-polling (`run_polling()`), so it just needs to run as a
persistent process somewhere — no public URL/webhook needed. Cheapest
options: [Railway](https://railway.app), [Render](https://render.com), or
a small always-on VPS. Point the start command at `python3 -m bot.main`,
set the same env vars from `.env` in the platform's dashboard, and upload
`credentials/service_account.json` as a file/secret (don't commit it to
the repo).

## Editing trader-facing copy

All the messages traders see live in `bot/messages.py` as plain strings.
Anything that changes **every round** (dates, amounts, prize, links) is a
`{placeholder}` filled in from the Config tab — edit it in the sheet (see
step 6 above), not here. Anything else — actual wording, emoji, tone —
does live here as code, so editing it still means a code change + git
push + Railway redeploy.

## Mod commands (used inside the mod group)

- Tap the buttons on a card — this is the main interaction.
- `/invite <sheet_row_number> <invite_link>` — DMs a trader their private
  group invite link. The row number is visible on their card in this
  group.

## What's intentionally NOT automated yet (Phase 2 candidates)

- **Funding.** Sending the testnet USDC is still a manual mod action. If
  there's a scriptable faucet/contract for it, the "Mark Funded" button in
  `bot/handlers/admin.py` is the one place to wire that in — right now it
  only updates the sheet and messages the trader.
- **Win verification.** Checking whether someone actually doubled their
  account is a manual mod check. Automating this would mean reading their
  testnet account state via an API, which is a separate piece of work.
- **Winner group creation.** The Telegram Bot API can't create new group
  chats — a mod creates the 1:1 group by hand. Only worth automating (via
  a separate userbot/MTProto script) if this tier grows past a few dozen
  people per round.

## Repo layout

```
bot/
  config.py          # env vars + sheet column schema
  sheets.py           # Google Sheet read/write wrapper (the "database")
  messages.py         # all trader-facing copy
  mod_cards.py         # builds the inline-button cards posted to the mod group
  jobs.py              # poll loop - safety net for direct sheet edits
  main.py              # wires it all together, entry point
  handlers/
    trader.py          # /start, /status, /claim, and the email/wallet text flow
    admin.py            # mod group button taps + /invite command
```
