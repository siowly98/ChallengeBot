# Veranta Challenge Bot

Automates the Telegram side of running the Veranta Challenge (formerly the
Avantis Challenge - see the rebrand note below): linking applicants to the
bot, sending approval/wallet-request/guide messages automatically, and
giving mods a single group chat with tap-to-act buttons instead of manually
DMing hundreds of people from a personal account.

**What this bot does not do:** decide who's eligible, send the actual testnet
USDC, or verify who won. Those stay human calls - the bot just carries every
message so a mod doesn't have to manually find and DM each trader.

## Rebrand notes (Avantis → Veranta)

- **Bot name/username:** Telegram doesn't let code change this - a mod with
  BotFather access has to do it manually. Message
  [@BotFather](https://t.me/BotFather), send `/mybots`, pick this bot, then
  **Edit Bot → Edit Name** for the display name and **Edit Bot → Edit
  Username** for the `@handle` (must still end in "bot", e.g.
  `VerantaChallengeBot`; only works if that username isn't taken). Old
  `t.me/OldUsername` links stop working the moment the username changes,
  so update anywhere that link is posted (pinned messages, the Google Form
  confirmation text, etc.) at the same time.
- **Mod contact link and testnet site:** both moved to the Config tab
  (`Mod Contact Link`, `Wallet Site URL` - see the table below) specifically
  so they don't need a code change or redeploy once the new Telegram group
  and domain exist. They still default to the old Avantis-era values until
  you fill in the new ones.
- **Everything else** (bot copy, this README) already says "Veranta."

## How it works (high level)

The Google Sheet your Form already writes responses to is the bot's entire
database. The bot never stores anything else in memory - every decision is
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
   bot replies with a confirm/cancel prompt and a blacklist warning (see
   below) → tapping **Confirm** is what actually posts a card in the mod
   group with **Verify** / **Reject** buttons.
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
WalletAddress | Funded | FundedAt | GuideSent | LeaderboardRegistered |
LeaderboardInviteSent | ClaimStatus | ClaimRequestedAt | ClaimReminderSent |
ClaimInstructionsSent | BroadcastSent | Notes
```

If your Google Form responses already land in a sheet, just add the
columns the bot manages (`TelegramUsername`, `ChatID`, `Eligible`,
`ApprovalSent`, `WalletAddress`, `Funded`, `FundedAt`, `GuideSent`,
`LeaderboardRegistered`, `LeaderboardInviteSent`, `ClaimStatus`,
`ClaimRequestedAt`, `ClaimReminderSent`, `ClaimInstructionsSent`,
`BroadcastSent`, `Notes`) to that same tab - `Timestamp` and
`Email Address` should already be there from the Form.

**Upgrading an existing sheet:** `BroadcastSent` is new. Add it to the
header row before deploying this version - a missing required column
makes the bot refuse to start with a `RuntimeError` naming it (same thing
that happened when `FundedAt` was added). `LeaderboardRegistered`,
`LeaderboardInviteSent`, `ClaimRequestedAt`, and `ClaimReminderSent` were
previous rounds of additions.
Note: `TelegramUsername` (bot-managed) is separate from any self-reported
"Your Telegram @username" column your form already has - keep both.

`Eligible` and `Funded` are the two columns a mod ticks by hand when
reviewing (checkbox format works fine - the bot reads TRUE/FALSE/YES/1 as
"true", anything else as "false"). Everything else the bot fills in itself,
including `FundedAt` - see "Per-participant challenge deadline" below for
what that drives. If you're adding this column to an existing sheet, the
bot won't start until it's there (it checks the header row on startup).

**Optional: letting someone repeat the challenge.** Add three questions to
the Google Form itself (word them however reads best to applicants), and
rename the resulting sheet columns to exactly these names:

- `TimesParticipatedBefore` - self-reported number, e.g. "0" for a
  first-timer, "1" for their second round, etc.
- `ReferralProof` - free text, e.g. the 5 friends' usernames/emails they
  referred.
- `SocialProofLink` - a link to their X/IG/TikTok post about the
  challenge.

These are entirely optional - the bot doesn't require them to exist, and
doesn't enforce anything on its own. They just give a mod reviewing an
application something to check before ticking `Eligible`: the rule itself
("repeat entrants need 5 referrals or a social post, mod approves either
way") is a review policy, not something the bot enforces. When
`TimesParticipatedBefore` is above 0, whatever's in `ReferralProof` or
`SocialProofLink` also shows up automatically on that trader's mod cards
(wallet submitted / claim requested) as a reminder during later-stage
review too.

Since these are self-reported on the Form and the sheet gets archived and
cleared each round (see "Starting a new round" below), there's no
automatic cross-round count - a mod trusts the applicant's stated number,
same as everything else reviewed manually here. **Repeat entrants must
resubmit the Form fresh every round, exactly like first-timers.** Never
reuse or reactivate an old row from a previous round - its `ApprovalSent`,
`WalletAddress`, `Funded`, `GuideSent`, and `ClaimStatus` columns are still
filled in from last time, which will make the bot think that round's steps
already happened and skip sending this round's messages entirely.

**Adding a Form question later.** If you add a new question to a Form
that's already linked to this sheet, Google appends a new response column
- fine, no restart needed. The bot always resolves which column to write
to from the sheet's current header row (not a cached position), so
existing columns don't need to be in any particular order and adding one
doesn't require redeploying. Just make sure the new question's column
header doesn't accidentally collide with one of the bot's own column
names in `bot/config.py`'s `COLUMNS` list.

**Mainnet EVM address.** Add a Form question asking for the wallet address
they trade with on mainnet (so you can later check whether they actually
came back and traded with real money) and name its sheet column
`MainnetEVMAddress`. This is optional, not in `COLUMNS` - the bot doesn't
require or act on it, it just shows up on `/check <row>` in the mod group
if present, purely for your own tracking.

### 3. Give the bot access to the sheet (Google service account)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project (or use an existing one) and enable the **Google Sheets API**.
2. Create a **Service Account**, then create a JSON key for it and download
   it.
3. Save that file as `credentials/service_account.json` (this path is
   already git-ignored - never commit it).
4. Open the JSON file, copy the `client_email` value, and **share your
   Google Sheet** with that email address (Editor access) - same as
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
every round - no code, no Terminal, no git required. Fill in a row for
each of these keys:

| Key | Example value |
| --- | --- |
| `Challenge Duration` | `3 days` |
| `Challenge Duration Hours` | `72` |
| `Start Amount` | `$5,000` |
| `Target Amount` | `$10,000` |
| `Prize Amount` | `$100` |
| `Wallet Site URL` | `testnet.avantisfi.com` (update once the Veranta domain exists) |
| `Withdrawal Address` | `0xBB4aD384eA26d0Ea59d01c9DB78D096b8e22b802` |
| `Guide Link` | link to your setup guide |
| `Claim Instructions Link` | link to your prize-claim instructions |
| `Google Form Link` | link to the Challenge application form |
| `Min Claim Delay Minutes` | `15` |
| `Mod Contact Link` | `https://t.me/AvantisChallenges/6/27` (update once the Veranta group/link exists) |
| `Leaderboard Invite Delay Hours` | `48` |
| `Leaderboard URL` | `https://veranta-challenges-leaderboard-production.up.railway.app/` |
| `Leaderboard Invite Enabled` | `TRUE` |
| `Leaderboard Registration Enabled` | `TRUE` |
| `Leaderboard Channel Invite Link` | (leave blank until that channel exists) |
| `Claim Reminder Delay Hours` | `24` |

Key names aren't case-sensitive and ignore spacing (`Prize Amount`,
`prize amount`, and `PRIZE_AMOUNT` all work) - use whatever's readable.
If you leave the whole tab out, or leave a row blank, the bot just uses
its built-in defaults for that value instead of breaking, so you can add
this gradually. Changes take effect on the very next message the bot
sends - no restart needed.

`Google Form Link` is shown when someone messages the bot an email that
isn't on the Applicants sheet - covers someone who found the bot before
ever filling out the form (as opposed to someone who already applied and
just mistyped their email; the bot can't tell those two cases apart, so
the message covers both).

`Withdrawal Address` is shown to every trader the moment they submit a
wallet (`WALLET_RECEIVED`), asking them to send back any leftover testnet
USDC before being funded. This exists because a repeat entrant's wallet
can still hold a balance from a previous round - funding them a fresh
`Start Amount` on top of that would let them start above the intended
balance, which isn't fair to everyone else starting from scratch. It's
shown unconditionally (not just to repeat entrants) since the bot has no
reliable way to tell who's reusing a wallet from before - first-timers
just see an instruction that doesn't apply to them.

The same message states the disqualification consequence: a wallet that
didn't start at exactly `Start Amount` gets disqualified even if the
trader hit the target. **This is a stated policy only** - like the
blacklist warning on `/claim`, the bot doesn't verify starting balances
itself (no on-chain polling exists anywhere in this codebase). Checking a
wallet's actual starting balance and enforcing this is a manual step for
whoever reviews the claim, same as verifying the target was genuinely hit.

`Challenge Duration` is just the wording used in trader-facing copy
("3 days"). `Challenge Duration Hours` is the number the bot actually
does deadline math with (`72`) - keep the two in sync by hand if you
change the round length. There's no `Challenge Start Date` key anymore:
see "Per-participant challenge deadline" below for why.

`Mod Contact Link` and `Wallet Site URL` both default to the old
Avantis-era values (see the rebrand note near the top) - update them here
once the new Veranta group and domain exist, no code change needed.

`Leaderboard Invite Delay Hours`, `Leaderboard URL`, `Leaderboard Invite
Enabled`, `Leaderboard Registration Enabled`, `Leaderboard Channel Invite
Link`, and `Claim Reminder Delay Hours` are covered in their own sections
below.

`Min Claim Delay Minutes` blocks `/claim` for that many minutes after a
trader gets funded - it exists because the funded message is also the
message that tells them `/claim` exists, and some traders tap it
immediately, before they've traded at all. This can't verify anyone
actually hit the target balance (that's still a manual mod check on the
claim card, same as before) - it just filters out claims that are
obviously too early, before a claim card is ever created, so mods don't
see them at all. Set it to `0` to disable the check entirely.

### Claim confirmation

Once past the delay above, `/claim` doesn't post a mod card right away -
it first replies with a confirm/cancel prompt (`bot/handlers/trader.py`,
`handle_claim_confirmation`) that spells out the consequence of a false
claim: "you'll be blacklisted immediately". This exists because people
were spamming `/claim` regardless of whether they'd actually hit the
target, in some cases even after their account had already been
liquidated. Nothing gets written to the sheet until they tap **Confirm** -
tapping **Cancel**, or just ignoring the prompt, leaves their row
untouched and they can `/claim` again later.

The warning is currently just words, not an enforced mechanism - there's
no `Blacklisted` column or automatic block on a repeat offender. A mod
still has to notice the pattern and decide what to do about it (e.g.
`REJECTED` isn't a dead end - the trader can just `/claim` again later),
the same way "false claim" itself is a human judgment call. If you want
an actual blacklist (e.g. a sheet column the bot checks before letting
someone link, submit a wallet, or claim at all), that's a separate
feature to build, not something this prompt does on its own.

### Claim cards standing out, and the stale-claim reminder

Claim cards look deliberately different from funding cards in the mod
group - "🚨 CLAIM REQUEST - NEEDS REVIEW 🚨" instead of "💰 Wallet
submitted" (`bot/mod_cards.py`) - because claim cards were getting missed
among other traffic in the group.

As a backstop for when a card still gets missed: if a claim sits with no
Verify/Reject tap for longer than `Claim Reminder Delay Hours` (default
24), the poll loop sends a follow-up nudge into the mod group naming the
row, email, and username, once per claim (`ClaimReminderSent` prevents
repeats). This uses `ClaimRequestedAt`, stamped the moment a claim is
confirmed - not `FundedAt` and not when `/claim` was first typed (which
might have been well before the confirmation prompt was tapped). A
resubmitted claim (e.g. after a `REJECTED` one) resets both
`ClaimRequestedAt` and `ClaimReminderSent`, so the 24h window restarts for
the new claim rather than reusing whatever's left from the old one.

### Leaderboard registration

The moment someone gets funded here, the poll loop also registers their
wallet on the separate Veranta Challenges Trading Leaderboard
(`POST /api/wallets` on that leaderboard, via `bot/leaderboard.py`) - using
the `WalletAddress` already on file in this sheet, so the trader is never
asked to submit it a second time. This fires once per row
(`LeaderboardRegistered`) and, deliberately, does **not** wait for
`Leaderboard Invite Delay Hours` below: an unregistered wallet earns
nothing on the leaderboard (its own eligibility gates hide any wallet with
no real trading volume), so registering early is harmless, and it means
whatever they trade shows up there from day one rather than only after the
invite delay.

Requires `LEADERBOARD_API_URL` and `LEADERBOARD_ADMIN_TOKEN` to be set as
env vars (see `.env.example`) - `LEADERBOARD_ADMIN_TOKEN` is the
leaderboard's own `ADMIN_TOKEN`. Leave either blank to run this bot with no
leaderboard integration at all - registration is skipped silently, not an
error, so upgrading to this version is safe even before the leaderboard
side is set up. With both set, `Leaderboard Registration Enabled` (Config
tab, defaults `TRUE`) is a second, code-free kill switch for just this
feature, independent of the invite message below.

A registration that fails (leaderboard briefly down, a handle already
registered to a different wallet, etc.) is logged and left unset, so it's
retried on the next poll instead of being silently lost - a handle
conflict specifically won't resolve itself and needs a mod to fix the
sheet or the leaderboard's own wallet registry by hand.

### Weekly leaderboard invite

Separately from this one-off challenge, `Leaderboard Invite Delay Hours`
(default 48, i.e. 2 days) after someone gets funded, the poll loop DMs
them an invite to a separate, ongoing weekly rolling leaderboard - top 3
PnL win cash, plus 10 raffle spots (`LEADERBOARD_INVITE` in
`bot/messages.py`, linking `Leaderboard URL`). This fires once per row
(`LeaderboardInviteSent`) and doesn't depend on whether they've claimed
anything on the challenge itself, or on whether registration above has
happened yet - it's about driving activity on the separate leaderboard,
not a reward for completing this challenge.

Set `Leaderboard Invite Enabled` to `FALSE` in the Config tab to stop
this going out entirely (e.g. the leaderboard site isn't ready yet) -
takes effect on the next poll, no redeploy. Defaults to `TRUE` if unset,
so existing setups keep sending it unless you turn it off.

If `Leaderboard Channel Invite Link` is set in the Config tab, the invite
message goes through the channel instead of linking the leaderboard
directly: it invites the trader to a separate Telegram channel/group and
gives *that* link, not the leaderboard's URL
(`LEADERBOARD_INVITE_VIA_CHANNEL` in `bot/messages.py`, in place of
`LEADERBOARD_INVITE`). The leaderboard link itself belongs **inside** that
channel - pin a message there explaining what the leaderboard is and
linking to it - so people join and read about it before ever seeing the
link, rather than the bot handing it straight to their DMs. Leave the key
blank (the default) to keep sending the plain invite with the leaderboard
link directly, no channel involved.

This is a single standing Telegram invite link you create once (e.g. a
group/channel with "unlimited" invite link usage) and paste in here - not
a unique per-trader link, since a shared link covers "anyone who wants to
try for prizes" without any new per-trader tracking.

### Per-participant challenge deadline

The challenge clock is per participant, not shared. It starts the moment
a mod taps **Mark Funded** on their card (or, if a mod ticks `Funded`
directly in the sheet instead, the moment the poll loop next picks that
up) - not on a fixed calendar date for everyone. That timestamp is
recorded in `FundedAt`, and the deadline shown to the trader and on
`/status` is just `FundedAt + Challenge Duration Hours`.

This is display-only: the bot shows the deadline everywhere a mod or
trader might need it - the funded message, `/status`, the mod card note
when a mod taps Fund, the claim card when a trader submits `/claim` (with
how early or late it was), and `/check` (below) - but never blocks a late
`/claim` itself. A mod still reviews and decides every claim, same as
before; the deadline is information for that decision, not an automatic
verdict. Funding someone on a Thursday, Friday, or a weekend day isn't
blocked either; the mod card just gets a "⚠️ Funded Thu-Sun" note as a
heads-up, since a 3-day window that starts Monday through Wednesday lands
entirely on weekdays, and one starting later in the week starts pulling
in weekend days. Whether that matters for your round is a call for mods,
not something the bot enforces - if you want a hard rule (e.g. "only fund
Mon-Wed"), that's a process rule for mods to follow, the same way
repeat-entrant approval already is.

## Deploying so it runs continuously

This bot uses long-polling (`run_polling()`), so it just needs to run as a
persistent process somewhere - no public URL/webhook needed. Cheapest
options: [Railway](https://railway.app), [Render](https://render.com), or
a small always-on VPS. Point the start command at `python3 -m bot.main`,
set the same env vars from `.env` in the platform's dashboard, and upload
`credentials/service_account.json` as a file/secret (don't commit it to
the repo).

## Editing trader-facing copy

All the messages traders see live in `bot/messages.py` as plain strings.
Anything that changes **every round** (dates, amounts, prize, links) is a
`{placeholder}` filled in from the Config tab - edit it in the sheet (see
step 6 above), not here. Anything else - actual wording, emoji, tone -
does live here as code, so editing it still means a code change + git
push + Railway redeploy.

## Mod commands (used inside the mod group)

- Tap the buttons on a card - this is the main interaction. These buttons
  are keyed on the trader's `ChatID`, not their sheet row number, so
  inserting, deleting, or sorting rows in the sheet afterwards is safe -
  an already-sent card still points at the right trader even if their row
  number changes. A card sent before this fix was shipped still encodes
  the old row-number format and will show "This button is from an old
  card format" if tapped after the row numbers have shifted - use `/check`
  and the sheet directly for those instead of re-tapping them.
- `/invite <sheet_row_number> <invite_link>` - DMs a trader their private
  group invite link. Look the row number up in the sheet itself (not
  the card - the card doesn't show it).
- `/check <sheet_row_number>` - read-only lookup of a trader's status and
  challenge deadline without leaving the group or opening the sheet.
  Doesn't change anything - use it to spot-check someone, or to double
  check a claim's timing beyond what's already on the claim card. Since
  this takes the row number you currently see in the sheet, it's always
  accurate regardless of past row shifts.
- `/broadcast <message>` then `/broadcastconfirm` - DMs every currently
  funded trader (anyone with `Funded=TRUE` and a linked `ChatID`) who
  hasn't already received a broadcast the same plain-text message. Every
  successful send marks that row's `BroadcastSent=TRUE`, so running
  `/broadcast` again later - e.g. daily, as new traders get funded - only
  reaches people who haven't gotten one yet; it never re-messages the same
  trader twice. That flag is shared across all broadcasts (not per
  distinct message), so if you ever need to send a genuinely different
  announcement to everyone again, clear the `BroadcastSent` column by hand
  in the sheet first (same as the "starting a new round" reset below). A
  failed send (blocked the bot, etc.) is deliberately left unmarked, so
  that trader is picked up again by the next broadcast instead of being
  silently skipped forever. `/broadcast` only stages the draft and replies
  with a preview plus the recipient count; nothing is sent until you follow up
  with `/broadcastconfirm` in the same chat - there's no per-recipient
  undo once it's out, so a wrong draft can't be walked back the way a
  single DM or a card edit can. Sends are throttled to about one message
  per second (well under Telegram's own bulk-notification limit) with a
  progress update in the mod group every 100 recipients and a final
  sent/failed count when it's done - at that pace, a broadcast to a few
  hundred traders takes several minutes, so it's meant for announcements,
  not anything time-critical. A trader who's funded but never linked
  their Telegram (no `ChatID` on their row) is skipped, not counted as a
  failure. Plain text only, deliberately - no Markdown/HTML parsing, since
  a mod's free-text announcement is exactly the kind of input likely to
  contain a stray `_` or `*` that would otherwise break formatting parsing
  for the whole message (see the note on the "verify" button above).

Trader-facing commands (`/start`, `/status`, `/claim`) and the plain-text
email/wallet flow are deliberately disabled inside the mod group - a mod
chatting normally in there won't get misread as a trader submitting an
email or wallet address (this is also why `/status` "doesn't work" if you
try it in the mod group - it's disabled there on purpose; use `/check` in
the group instead). Those trader commands only work in a 1:1 DM with the
bot.

## Starting a new round

The bot has no concept of "rounds" - the Applicants tab is just whatever
rows are currently in it. Reusing the same tab across rounds without
resetting it causes real problems: returning applicants' old rows still
have last round's `Eligible`/`Funded`/`ClaimStatus` etc. filled in, which
confuses both the bot (it thinks those steps already happened) and anyone
trying to read the sheet.

Before opening the Form to a new round's applicants:

1. Duplicate the current Applicants tab, or copy-paste its data into an
   archive tab (e.g. `Round 3 Archive`), so you keep the history.
2. Delete all the data rows in the live tab, keeping just the header row.
   `WORKSHEET_NAME` in `.env`/Railway doesn't need to change - the Form
   keeps writing to the same tab, which the bot now sees as empty.
3. Update the Config tab's values for the new round (duration, amounts,
   prize - see step 6 above).

Consequence: everyone's `ChatID` gets wiped too, so every trader -
including repeat entrants - has to `/start` and re-send their email to
relink for the new round. That's expected, not a bug.

## What's intentionally NOT automated yet (Phase 2 candidates)

- **Funding.** Sending the testnet USDC is still a manual mod action. If
  there's a scriptable faucet/contract for it, the "Mark Funded" button in
  `bot/handlers/admin.py` is the one place to wire that in - right now it
  only updates the sheet and messages the trader.
- **Win verification.** Checking whether someone actually doubled their
  account is a manual mod check. Automating this would mean reading their
  testnet account state via an API, which is a separate piece of work.
- **Winner group creation.** The Telegram Bot API can't create new group
  chats - a mod creates the 1:1 group by hand. Only worth automating (via
  a separate userbot/MTProto script) if this tier grows past a few dozen
  people per round.

## Repo layout

```
bot/
  config.py          # env vars + sheet column schema
  sheets.py           # Google Sheet read/write wrapper (the "database")
  leaderboard.py       # HTTP client for registering a wallet on the separate leaderboard
  messages.py         # all trader-facing copy
  mod_cards.py         # builds the inline-button cards posted to the mod group
  jobs.py              # poll loop - safety net for direct sheet edits
  main.py              # wires it all together, entry point
  handlers/
    trader.py          # /start, /status, /claim, and the email/wallet text flow
    admin.py            # mod group button taps + /invite, /check, /broadcast commands
```
