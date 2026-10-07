# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers for the summary entities (sensors, calendar)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .logic import at, routine_window
from .manager import KisSegitoManager


def routine_times(
    manager: KisSegitoManager, routine: dict[str, Any], day
) -> tuple[datetime, datetime]:
    """Start and end of a routine on ``day``, including its checkpoints."""
    tz = dt_util.get_default_time_zone()
    start, end = routine_window(routine, day, tz)
    for cp in routine.get("checkpoints", []):
        if cp.get("time"):
            end = max(end, at(day, cp["time"], tz))
    return start, end


def running_routines(manager: KisSegitoManager) -> list[dict[str, Any]]:
    """Routines running right now."""
    now = dt_util.now()
    return [
        r
        for r in manager.routines_on_day(now.date())
        if routine_times(manager, r, now.date())[0]
        <= now
        < routine_times(manager, r, now.date())[1]
    ]


def next_checkpoint(
    manager: KisSegitoManager, child_id: str | None = None
) -> dict[str, Any] | None:
    """The next checkpoint today (for a child: one not reached yet)."""
    now = dt_util.now()
    day = now.date()
    best: tuple[datetime, dict[str, Any], dict[str, Any]] | None = None
    for routine in manager.routines_on_day(day):
        if child_id and routine.get("children") and child_id not in routine["children"]:
            continue
        done = (
            manager.progress(day, routine["id"], child_id)["checkpoints"]
            if child_id
            else {}
        )
        for cp in routine.get("checkpoints", []):
            if child_id and cp.get("children") and child_id not in cp["children"]:
                continue
            if cp["id"] in done:
                continue
            due = manager.checkpoint_time(routine, cp, day)
            if due >= now and (best is None or due < best[0]):
                best = (due, cp, routine)
    if best is None:
        return None
    due, cp, routine = best
    return {
        "name": cp.get("name", ""),
        "time": due.isoformat(),
        "routine": routine.get("name", ""),
    }
