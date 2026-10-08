# SPDX-License-Identifier: AGPL-3.0-only
"""Summary sensors: one for Kis Segito, one per child.

Kept small on purpose (few entities, compact attributes); the panel reads the
details through its own API.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .entity_helpers import next_checkpoint, running_routines
from .manager import KisSegitoManager


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the summary sensor and one sensor per child (new children later too)."""
    manager: KisSegitoManager = hass.data[DOMAIN].manager
    known: set[str] = set()
    entities: list[SensorEntity] = [SummarySensor(manager)]

    def new_children() -> list[SensorEntity]:
        result: list[SensorEntity] = []
        for child in manager.children():
            if child["id"] not in known:
                known.add(child["id"])
                result.append(ChildSensor(manager, child["id"]))
        return result

    entities += new_children()
    async_add_entities(entities)

    @callback
    def changed() -> None:
        if added := new_children():
            async_add_entities(added)

    entry.async_on_unload(manager.async_add_listener(changed))


class _Base(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, manager: KisSegitoManager) -> None:
        self.manager = manager

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
        # Time moves routines along even without data changes.
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1))
        )

    @callback
    def _async_tick(self, _now: datetime) -> None:
        """Refresh the time-dependent state (runs in the event loop)."""
        self.async_write_ha_state()


class SummarySensor(_Base):
    """Overall state: "active" while a routine runs, "idle" otherwise."""

    _attr_name = "Kis Segítő"
    _attr_unique_id = f"{DOMAIN}_summary"
    _attr_icon = "mdi:hand-heart"

    @property
    def native_value(self) -> str:
        return "active" if running_routines(self.manager) else "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        template = self.manager.template_for_day(self.manager.today())
        return {
            "day_template": template.get("name") if template else None,
            "active_routines": [
                r.get("name", "") for r in running_routines(self.manager)
            ],
            "next_checkpoint": next_checkpoint(self.manager),
            "children": len(self.manager.children(active_only=True)),
        }


class ChildSensor(_Base):
    """A child's wallet balance, with compact progress attributes."""

    _attr_icon = "mdi:account-child-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "tokens"

    def __init__(self, manager: KisSegitoManager, child_id: str) -> None:
        super().__init__(manager)
        self.child_id = child_id
        self._attr_unique_id = f"{DOMAIN}_child_{child_id}"

    @property
    def _child(self) -> dict[str, Any] | None:
        return self.manager.child(self.child_id)

    @property
    def available(self) -> bool:
        return self._child is not None

    @property
    def name(self) -> str:
        child = self._child
        return f"Kis Segítő {child.get('name', '')}".strip() if child else "Kis Segítő"

    @property
    def native_value(self) -> int | None:
        if self._child is None:
            return None
        return self.manager.balances(self.child_id)["wallet"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        child = self._child
        if child is None:
            return {}
        day = self.manager.today()
        current = next(
            (
                r
                for r in running_routines(self.manager)
                if not r.get("children") or self.child_id in r["children"]
            ),
            None,
        )
        progress = None
        current_task = None
        if current is not None:
            done = self.manager.progress(day, current["id"], self.child_id)["tasks"]
            tasks = current.get("tasks", [])
            progress = f"{sum(1 for t in tasks if t['id'] in done)}/{len(tasks)}"
            current_task = next(
                (t.get("label") or t.get("icon") for t in tasks if t["id"] not in done),
                None,
            )
        last = next(
            (
                t
                for t in reversed(self.manager.transactions)
                if t["child_id"] == self.child_id
            ),
            None,
        )
        return {
            "child_id": self.child_id,
            "piggy_balance": self.manager.balances(self.child_id)["piggy"],
            "piggy_unlocked": bool(child.get("piggy_unlocked")),
            "streak": self.manager.streak(self.child_id),
            "streak_target": int(self.manager.settings.get("streak_target", 7)),
            "current_routine": current.get("name") if current else None,
            "current_task": current_task,
            "routine_progress": progress,
            "next_checkpoint": next_checkpoint(self.manager, self.child_id),
            "last_transaction": (
                {
                    "reason": last["reason"],
                    "amount": sum(li["amount"] for li in last["lines"]),
                    "at": last["timestamp"],
                }
                if last
                else None
            ),
        }
