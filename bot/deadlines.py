"""Per-participant challenge deadline math.

The challenge clock starts when a mod funds someone's wallet, not on a
shared calendar date - see the FundedAt column (written by admin.py's
"fund" action) and the Config tab's challenge_duration_hours key (the
numeric twin of the human-readable challenge_duration string used in
message copy).

This is display-only: nothing here blocks a late /claim or stops a mod
from funding someone on a Thursday. It just gives mods and traders an
actual deadline to look at instead of a vague "before time's up".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_DURATION_HOURS = 72.0


def _resolve_hours(duration_hours) -> float:
    """Shared parsing for a Config tab hours value (challenge_duration_hours),
    falling back to the 72h default if it's missing or not a real number."""
    try:
        return float(duration_hours)
    except (TypeError, ValueError):
        return DEFAULT_DURATION_HOURS


def _parse_iso_utc(timestamp_iso: str | None) -> datetime | None:
    """Shared parsing for an ISO UTC timestamp cell (FundedAt,
    ClaimRequestedAt, ...). Returns None if blank or unparseable (e.g. a
    row from before that column existed), so callers can treat that as
    "unknown" instead of crashing. Always returns a tz-aware UTC datetime."""
    if not timestamp_iso:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp_iso)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def compute_deadline(funded_at_iso: str | None, duration_hours) -> datetime | None:
    """Returns the UTC deadline for a row given its FundedAt timestamp and
    the Config tab's challenge_duration_hours. Returns None if funded_at_iso
    is blank or unparseable, so callers can treat the deadline as "unknown"
    (e.g. a row funded before this feature existed) instead of crashing."""
    funded_at = _parse_iso_utc(funded_at_iso)
    if funded_at is None:
        return None
    return funded_at + timedelta(hours=_resolve_hours(duration_hours))


def elapsed_since_iso(timestamp_iso: str | None, now: datetime) -> timedelta | None:
    """How long ago an ISO UTC timestamp was, relative to `now` (pass your
    own so callers stay testable the same way as everything else here).
    Generic - used for FundedAt (the /claim delay check in
    bot/handlers/trader.py) and for ClaimRequestedAt (the stale-claim
    reminder in bot/jobs.py) alike. Returns None if the timestamp is blank
    or unparseable."""
    parsed = _parse_iso_utc(timestamp_iso)
    if parsed is None:
        return None
    return now - parsed


def format_deadline(deadline: datetime) -> str:
    return deadline.strftime("%a %b %d, %H:%M UTC")


def funded_late_in_week(funded_at: datetime, duration_hours) -> bool:
    """True if the challenge window (funded_at through funded_at +
    duration_hours) includes any Saturday or Sunday - a heads-up for mods,
    never enforced. Duration-aware on purpose: a fixed "funded Thu-Sun"
    cutoff only makes sense for a ~3-day window. A 5-day-or-longer window
    crosses a weekend almost regardless of which day it starts, so this
    checks the actual span instead of assuming a duration - it stays
    correct no matter what challenge_duration_hours is set to in the
    Config tab."""
    hours = _resolve_hours(duration_hours)
    deadline = funded_at + timedelta(hours=hours)
    # Half-open interval [funded_at, deadline) - a deadline landing exactly
    # at midnight shouldn't count that calendar day, since none of it is
    # actually inside the window (e.g. Wed 00:00 + 72h = Sat 00:00 on the
    # dot - the window closes the instant Saturday begins, so it never
    # actually includes any Saturday trading time).
    day = funded_at.date()
    end = (deadline - timedelta(microseconds=1)).date()
    while day <= end:
        if day.weekday() >= 5:  # Saturday=5, Sunday=6
            return True
        day += timedelta(days=1)
    return False


def format_timedelta(delta: timedelta) -> str:
    """Compact human string for a small gap around a deadline, e.g. "4h 12m"
    or "35m". Callers should only ever pass a non-negative delta (how early
    or how late something was relative to the deadline) - this doesn't
    handle calendar-scale spans or negative values meaningfully."""
    total_minutes = max(int(delta.total_seconds() // 60), 0)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
