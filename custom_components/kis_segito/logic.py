# SPDX-License-Identifier: AGPL-3.0-only
"""Pure business rules (no Home Assistant objects), easy to unit test."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta
from typing import Any


def reward_for(bands: Iterable[Mapping[str, Any]], seconds_early: float) -> int:
    """Tokens for completing ``seconds_early`` before the target.

    Each band is ``{"min_early_min": minutes, "tokens": n}``; the best band whose
    threshold is reached wins (bands never stack). Late completion matches only a
    band with a negative threshold, otherwise it is worth 0. Never negative.
    """
    best: int | None = None
    best_threshold: float | None = None
    for band in bands:
        threshold = float(band.get("min_early_min", 0)) * 60
        tokens = max(0, int(band.get("tokens", 0)))
        if seconds_early >= threshold and (
            best_threshold is None or threshold > best_threshold
        ):
            best, best_threshold = tokens, threshold
    return best or 0


def interest_for(
    balance: int,
    rate_percent: float,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Weekly piggy-bank interest in whole tokens (rounded down, then clamped)."""
    if balance <= 0 or rate_percent <= 0:
        return 0
    interest = int(balance * rate_percent // 100)
    if minimum is not None:
        interest = max(interest, minimum)
    if maximum is not None:
        interest = min(interest, maximum)
    return max(0, interest)


def parse_hhmm(value: str) -> time:
    """Parse "HH:MM" into a time."""
    hours, minutes = value.split(":")[:2]
    return time(int(hours), int(minutes))


def at(day: date, hhmm: str, tz: Any) -> datetime:
    """The datetime of "HH:MM" on ``day`` in time zone ``tz``."""
    return datetime.combine(day, parse_hhmm(hhmm), tzinfo=tz)


def routine_runs_on(routine: Mapping[str, Any], day: date) -> bool:
    """Whether an active routine is scheduled on ``day`` (weekday 0 = Monday)."""
    weekdays = routine.get("weekdays")
    return bool(routine.get("active", True)) and (
        not weekdays or day.weekday() in weekdays
    )


def routine_window(
    routine: Mapping[str, Any], day: date, tz: Any
) -> tuple[datetime, datetime]:
    """Start and end (target) of a routine on ``day``; the end is at least 1 min later."""
    start = at(day, routine.get("start", "07:00"), tz)
    end = at(day, routine.get("end", "08:00"), tz)
    if end <= start:
        end = start + timedelta(minutes=1)
    return start, end


def applies_to(item: Mapping[str, Any], child_id: str) -> bool:
    """Whether a routine/checkpoint applies to a child (empty list = everyone)."""
    children = item.get("children") or []
    return not children or child_id in children


def selectable_children(
    all_children: Iterable[str], assigned: Iterable[str]
) -> set[str]:
    """Children selectable on a device.

    A device assigned to nobody, or to every child, works for everyone;
    otherwise only the assigned children can be selected there.
    """
    everyone = set(all_children)
    chosen = set(assigned) & everyone
    if not chosen or chosen == everyone:
        return everyone
    return chosen


def shift_hhmm(value: str, minutes: int) -> str:
    """Move "HH:MM" by ``minutes`` within the same day (clamped to 00:00-23:59)."""
    t = parse_hhmm(value)
    total = min(max(t.hour * 60 + t.minute + int(minutes), 0), 23 * 60 + 59)
    return f"{total // 60:02d}:{total % 60:02d}"


def routine_with_override(
    routine: Mapping[str, Any], override: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """A routine as it runs on one day: None when skipped, times shifted.

    ``override`` is the one-day change from "Modify today":
    ``{"skip": bool, "shift_min": minutes}``; the routine itself is unchanged.
    """
    if override and override.get("skip"):
        return None
    result = dict(routine)
    shift = int((override or {}).get("shift_min", 0) or 0)
    if shift:
        for key in ("start", "end"):
            if result.get(key):
                result[key] = shift_hhmm(result[key], shift)
        result["checkpoints"] = [
            cp | ({"time": shift_hhmm(cp["time"], shift)} if cp.get("time") else {})
            for cp in routine.get("checkpoints", [])
        ]
    return result
