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

# Funding on Monday, Tuesday or Wednesday keeps a 3-day (72h) window
# entirely on weekdays. Thursday onward starts pulling in a weekend day.
_LATE_WEEKDAY_CUTOFF = 3  # Monday=0 ... Thursday=3


def _parse_funded_at(funded_at_iso: str | None) -> datetime | None:
    """Shared parsing for a FundedAt cell value. Returns None if blank or
    unparseable (e.g. a row funded before this column existed), so callers
    can treat that as "unknown" instead of crashing. Always returns a
    tz-aware UTC datetime."""
    if not funded_at_iso:
        return None
    try:
        funded_at = datetime.fromisoformat(funded_at_iso)
    except ValueError:
        return None
    if funded_at.tzinfo is None:
        funded_at = funded_at.replace(tzinfo=timezone.utc)
    return funded_at


def compute_deadline(funded_at_iso: str | None, duration_hours) -> datetime | None:
    """Returns the UTC deadline for a row given its FundedAt timestamp and
    the Config tab's challenge_duration_hours. Returns None if funded_at_iso
    is blank or unparseable, so callers can treat the deadline as "unknown"
    (e.g. a row funded before this feature existed) instead of crashing."""
    funded_at = _parse_funded_at(funded_at_iso)
    if funded_at is None:
        return None
    try:
        hours = float(duration_hours)
    except (TypeError, ValueError):
        hours = DEFAULT_DURATION_HOURS
    return funded_at + timedelta(hours=hours)


def time_since_funded(funded_at_iso: str | None, now: datetime) -> timedelta | None:
    """How long ago a row's FundedAt was, relative to `now` (pass your own
    so callers stay testable the same way as everything else here - see
    claim_too_soon in bot/handlers/trader.py, the one caller). Returns None
    if FundedAt is blank or unparseable."""
    funded_at = _parse_funded_at(funded_at_iso)
    if funded_at is None:
        return None
    return now - funded_at


def format_deadline(deadline: datetime) -> str:
    return deadline.strftime("%a %b %d, %H:%M UTC")


def funded_late_in_week(funded_at: datetime) -> bool:
    """True if funding at this moment means the challenge window will
    likely include a weekend day - a heads-up for mods, never enforced."""
    return funded_at.weekday() >= _LATE_WEEKDAY_CUTOFF


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
