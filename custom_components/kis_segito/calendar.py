# SPDX-License-Identifier: AGPL-3.0-only
"""calendar.kis_segito: the routines as calendar events."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity_helpers import routine_times
from .manager import KisSegitoManager

MAX_DAYS = 400  # longest range answered at once


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the routines calendar."""
    async_add_entities([RoutinesCalendar(hass.data[DOMAIN].manager)])


class RoutinesCalendar(CalendarEntity):
    """Routines as they run each day (day templates and one-day changes applied)."""

    _attr_name = "Kis Segítő"
    _attr_unique_id = f"{DOMAIN}_calendar"
    _attr_icon = "mdi:calendar-clock"
    _attr_should_poll = False

    def __init__(self, manager: KisSegitoManager) -> None:
        self.manager = manager

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        events = []
        day = dt_util.as_local(start).date()
        last = dt_util.as_local(end).date()
        for _ in range(MAX_DAYS):
            if day > last:
                break
            for routine in self.manager.routines_on_day(day):
                begin, finish = routine_times(self.manager, routine, day)
                if finish <= start or begin >= end:
                    continue
                checkpoints = ", ".join(
                    f"{cp.get('name') or ''} {cp.get('time') or ''}".strip()
                    for cp in routine.get("checkpoints", [])
                )
                events.append(
                    CalendarEvent(
                        start=begin,
                        end=finish,
                        summary=routine.get("name") or "Kis Segítő",
                        description=checkpoints or None,
                        uid=f"{routine['id']}-{day.isoformat()}",
                    )
                )
            day += timedelta(days=1)
        return sorted(events, key=lambda e: e.start)

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next routine (today or tomorrow)."""
        now = dt_util.now()
        upcoming = [
            e for e in self._events(now, now + timedelta(days=2)) if e.end > now
        ]
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Events in a range (for the calendar view and automations)."""
        return self._events(start_date, end_date)
