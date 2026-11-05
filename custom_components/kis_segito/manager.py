# SPDX-License-Identifier: AGPL-3.0-only
"""Kis Segito business logic on top of the stored data.

Everything that changes data goes through this class: configuration edits
from the panel, token transactions (ledger), routine progress from the knobs
or from Home Assistant actions. After each change listeners are notified
(knobs get a new state snapshot, the panel refreshes).
"""

from __future__ import annotations

import hmac
import logging
import re
import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import ledger as lg
from .const import EVENT_KIS_SEGITO
from .icons import stored_icon
from .logic import (
    applies_to,
    at,
    interest_for,
    reward_for,
    routine_runs_on,
    routine_window,
    routine_with_override,
    child_on_device,
)
from .themes import DEFAULT_THEME, has_file
from .themes import theme as theme_of
from .store import AUDIT_KEPT, DEFAULT_AVATAR, DEFAULT_SETTINGS, KisSegitoStore

_LOGGER = logging.getLogger(__name__)

# Device action ids are remembered this long (duplicate retries are ignored).
ACTION_TTL = timedelta(days=7)
ACTION_KEPT = 2000
# Daily progress is kept this long.
DAYS_KEPT = 31
# Events without a token movement kept for the statistics (a few years).
EVENTS_KEPT = 50000

COLLECTIONS = ("children", "routines", "rewards", "templates", "routine_templates")
# Built-in backgrounds (frontend/backgrounds/bg_<n>.jpg).
# Knob screen power settings, in the order the knob protocol sends them.
SCREEN_KEYS = ("saver_after", "dim_after", "dim_level", "blank_after", "off_after")
# Sensor-driven screen settings and their short names in the knob protocol.
SENSOR_KEYS = {
    "presence_wake": "pw",
    "presence_saver": "ps",
    "night_light": "nl",
    "night_lux": "nlx",
    "night_brightness": "nb",
    "night_kelvin": "nk",
    "night_off_after": "noff",
    "near_cm": "near",
    "ambient": "amb",
    "ambient_min": "amin",
    "ambient_max": "amax",
    "light_factor": "lf",
}
# Sensor inputs a knob can take from Home Assistant entities.
INPUT_KINDS = ("presence", "distance", "illuminance")
BACKGROUND_PRESETS = tuple(f"bg_{n}" for n in range(1, 7))
# The background: "" (none), a preset or an uploaded picture.
BACKGROUND_VALUE = r"^(|bg_[1-6]|[a-z0-9]{1,64})$"


class KisSegitoError(Exception):
    """A request was refused; ``code`` is stable and translatable."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class KisSegitoManager:
    """Owns the data and the rules."""

    def __init__(self, hass: HomeAssistant, store: KisSegitoStore) -> None:
        self.hass = hass
        self.store = store
        self._listeners: list[Callable[[], None]] = []
        # Sends notifications for an event (set up by the integration).
        self.notifier: Callable[[dict[str, Any]], None] | None = None

    # ------------------------------------------------------------ listeners

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call ``listener`` after every change."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def async_notify_listeners(self) -> None:
        """Tell the listeners (panels, knobs) about a change stored elsewhere."""
        for listener in list(self._listeners):
            listener()

    async def _changed(self, *, ledger: bool = False) -> None:
        if ledger:
            await self.store.async_save_ledger()
        await self.store.async_save()
        for listener in list(self._listeners):
            listener()

    def _fire(self, event_type: str, child_id: str | None, **data: Any) -> None:
        payload: dict[str, Any] = {"event_type": event_type}
        if child_id:
            child = self.child(child_id)
            bal = self.balances(child_id)
            payload |= {
                "child_id": child_id,
                "child_name": child.get("name", "") if child else "",
                "wallet_balance": bal[lg.WALLET],
                "piggy_balance": bal[lg.PIGGY],
            }
        payload |= data
        payload["timestamp"] = _iso(dt_util.now())
        self.hass.bus.async_fire(EVENT_KIS_SEGITO, payload)
        if self.notifier is not None:
            self.notifier(payload)

    # ------------------------------------------------------------ data access

    @property
    def data(self) -> dict[str, Any]:
        """The configuration document."""
        return self.store.data

    @property
    def settings(self) -> dict[str, Any]:
        """Global settings."""
        return self.store.settings

    def children(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        """Children in display order."""
        items = sorted(self.data["children"], key=lambda c: c.get("sort_order", 0))
        return [c for c in items if c.get("active", True)] if active_only else items

    def child(self, child_id: str) -> dict[str, Any] | None:
        """One child by id."""
        return next((c for c in self.data["children"] if c["id"] == child_id), None)

    def routine(self, routine_id: str) -> dict[str, Any] | None:
        """One routine by id."""
        return next((r for r in self.data["routines"] if r["id"] == routine_id), None)

    def override(self, day: date, routine_id: str) -> dict[str, Any] | None:
        """The one-day change of a routine ("Modify today"), if any."""
        return self.data["overrides"].get(day.isoformat(), {}).get(routine_id)

    def routine_on_day(
        self, routine: dict[str, Any], day: date
    ) -> dict[str, Any] | None:
        """The routine as it runs on ``day`` (None: not scheduled or skipped).

        With a day template for ``day`` the template decides which routines
        run; without one each routine's own weekdays do.
        """
        template = self.template_for_day(day)
        if template is not None:
            if not routine.get("active", True) or routine["id"] not in template.get(
                "routines", []
            ):
                return None
        elif not routine_runs_on(routine, day):
            return None
        override = self.override(day, routine["id"])
        if override and override.get("routine"):
            # Edited for this day only: the day's copy replaces the routine.
            routine = override["routine"] | {"id": routine["id"]}
        return routine_with_override(routine, override)

    def template_for_day(self, day: date) -> dict[str, Any] | None:
        """The day template of ``day``: chosen for the date, else the weekday's."""
        template_id = self.data["date_templates"].get(day.isoformat())
        if template_id is None:
            template_id = self.data["weekday_templates"].get(str(day.weekday()))
        if not template_id:
            return None
        return next((t for t in self.data["templates"] if t["id"] == template_id), None)

    async def async_set_day_template(
        self,
        *,
        day: date | None = None,
        weekday: int | None = None,
        template_id: str | None,
        who: str = "parent",
    ) -> None:
        """Choose the template of a date, or the default of a weekday.

        ``template_id`` None removes the choice ("" for a date means: no
        template that day, routines follow their own weekdays).
        """
        if template_id and not any(
            t["id"] == template_id for t in self.data["templates"]
        ):
            raise KisSegitoError("unknown_template")
        if day is not None:
            key, store = day.isoformat(), self.data["date_templates"]
        elif weekday is not None:
            key, store = str(int(weekday) % 7), self.data["weekday_templates"]
        else:
            raise KisSegitoError("unknown_item")
        old = store.get(key)
        if template_id is None:
            store.pop(key, None)
        else:
            store[key] = template_id
        self._audit(who, f"template.{key}", old, template_id)
        await self._changed()

    def routines_on_day(self, day: date) -> list[dict[str, Any]]:
        """Routines running on ``day`` with that day's changes, by start time."""
        result = [
            r
            for r in (self.routine_on_day(r, day) for r in self.data["routines"])
            if r is not None
        ]
        # Routines added for this day only.
        for routine_id, override in (
            self.data["overrides"].get(day.isoformat(), {}).items()
        ):
            if override.get("one_day") and not override.get("skip"):
                result.append(override["routine"] | {"id": routine_id, "one_day": True})
        return sorted(result, key=lambda r: r.get("start", ""))

    def routine_for_day(self, routine_id: str, day: date) -> dict[str, Any] | None:
        """A routine (also a one-day one) as it runs on ``day``."""
        return next(
            (r for r in self.routines_on_day(day) if r["id"] == routine_id), None
        )

    def reward(self, reward_id: str) -> dict[str, Any] | None:
        """One reward by id."""
        return next((r for r in self.data["rewards"] if r["id"] == reward_id), None)

    def has_piggy_unlock_reward(self) -> bool:
        """Whether an active reward unlocks the piggy bank."""
        return any(
            r.get("kind") == "piggy_unlock" and r.get("active", True)
            for r in self.data["rewards"]
        )

    def _require_child(self, child_id: str) -> dict[str, Any]:
        child = self.child(child_id)
        if child is None:
            raise KisSegitoError("unknown_child")
        return child

    # ------------------------------------------------------------ configuration

    async def async_save_item(
        self, collection: str, item: dict[str, Any]
    ) -> dict[str, Any]:
        """Create (no id) or replace (with id) a child, routine or reward."""
        if collection not in COLLECTIONS:
            raise KisSegitoError("unknown_collection")
        items: list[dict[str, Any]] = self.data[collection]
        item = dict(item)
        if collection == "children":
            item.pop("background", None)  # one background for all children

        if not item.get("id"):
            item["id"] = lg.new_id()
            item.setdefault("sort_order", len(items))
            if collection == "children" and "piggy_unlocked" not in item:
                # Locked when it can be bought; open when nothing unlocks it.
                item["piggy_unlocked"] = not self.has_piggy_unlock_reward()
            items.append(item)
        else:
            for index, existing in enumerate(items):
                if existing["id"] == item["id"]:
                    items[index] = existing | item
                    item = items[index]
                    break
            else:
                raise KisSegitoError("unknown_item")
        if collection == "routines":
            self._normalise_routine(item)
        await self._changed()
        return item

    async def async_delete_item(self, collection: str, item_id: str) -> None:
        """Delete a child, routine or reward (ledger history stays)."""
        if collection not in COLLECTIONS:
            raise KisSegitoError("unknown_collection")
        before = len(self.data[collection])
        self.data[collection] = [i for i in self.data[collection] if i["id"] != item_id]
        if len(self.data[collection]) == before:
            raise KisSegitoError("unknown_item")
        await self._changed()

    async def async_reorder(self, collection: str, ids: list[str]) -> None:
        """Set the display order of a collection."""
        order = {item_id: index for index, item_id in enumerate(ids)}
        for item in self.data[collection]:
            if item["id"] in order:
                item["sort_order"] = order[item["id"]]
        await self._changed()

    def _audit(self, who: str, what: str, old: Any, new: Any) -> None:
        """Record a configuration change: who, when, old and new value."""
        audit = self.data["audit"]
        audit.append(
            {"at": _iso(dt_util.now()), "by": who, "what": what, "old": old, "new": new}
        )
        del audit[:-AUDIT_KEPT]

    async def async_update_settings(
        self, changes: dict[str, Any], *, who: str = "parent"
    ) -> None:
        """Change global settings."""
        for key, value in changes.items():
            if self.settings.get(key) != value:
                self._audit(who, f"settings.{key}", self.settings.get(key), value)
        if "background" in changes and changes["background"] != self.settings.get(
            "background"
        ):
            # Counts every change: the knobs restart to show the new picture
            # after each one (choosing the current one again changes nothing).
            changes = changes | {
                "background_seq": int(self.settings.get("background_seq", 0)) + 1
            }
        self.settings.update(changes)
        await self._changed()

    async def async_set_background(
        self,
        background: str,
        *,
        device_id: str | None = None,
        who: str = "automation",
    ) -> None:
        """Choose the background of one knob, or of every knob (the common
        one, and no knob keeps its own)."""
        if not re.match(BACKGROUND_VALUE, background):
            raise KisSegitoError("invalid_background")
        if device_id is not None:
            await self._set_device_background(device_id, background, who=who)
            return
        for device in self.data["devices"].values():
            if "background" in device:
                # Its own picture was shown: the counter moves on with it.
                seq = int(device.get("background_seq", 0))
                device["background_seq"] = seq + int(device["background"] != background)
                device["background"] = background
        await self.async_update_settings({"background": background}, who=who)

    async def async_set_override(
        self,
        day: date,
        routine_id: str,
        *,
        skip: bool = False,
        shift_min: int = 0,
        who: str = "parent",
    ) -> None:
        """Change a routine for one day only (skip it or shift its times)."""
        if self.routine(routine_id) is None and not self.override(day, routine_id):
            raise KisSegitoError("unknown_routine")
        day_overrides = self.data["overrides"].setdefault(day.isoformat(), {})
        old = day_overrides.get(routine_id)
        new = dict(old or {}) | {
            "skip": bool(skip),
            "shift_min": int(shift_min),
            "by": who,
            "at": _iso(dt_util.now()),
        }
        if old and old.get("moved") and not skip:
            # Back on its own day: the moved copy goes.
            self._drop_moved_copies(day.isoformat(), routine_id)
            new.pop("moved", None)
        if not skip and not shift_min and not new.get("routine"):
            day_overrides.pop(routine_id, None)
            new = None
        else:
            day_overrides[routine_id] = new
        self._audit(who, f"override.{day.isoformat()}.{routine_id}", old, new)
        await self._changed()

    async def async_set_day_routine(
        self,
        day: date,
        routine_id: str | None,
        routine: dict[str, Any] | None,
        *,
        target_day: date | None = None,
        who: str = "parent",
    ) -> str | None:
        """Edit a routine for one day only, add a one-day routine, or restore.

        ``routine_id`` None with a routine adds a one-day routine; a routine of
        None restores the original: the day's copy, its time shift and a move
        to another day are all dropped (a one-day routine is removed). With
        ``target_day`` the occurrence moves to that day. The source routine is
        never changed. Past days are read-only.
        """
        target_day = target_day or day
        if day < self.today() or target_day < self.today():
            raise KisSegitoError("past_day")
        if routine is not None:
            routine = {
                k: v
                for k, v in routine.items()
                if k not in ("id", "weekdays", "active", "one_day")
            }
            self._normalise_routine(routine)
        day_overrides = self.data["overrides"].setdefault(day.isoformat(), {})
        if routine_id is None:
            if routine is None:
                raise KisSegitoError("unknown_routine")
            return await self._add_one_day(target_day, routine, None, who)
        old = day_overrides.get(routine_id)
        one_day = bool(old and old.get("one_day"))
        if not one_day and self.routine(routine_id) is None:
            raise KisSegitoError("unknown_routine")
        if routine is None:
            self._restore_occurrence(day, routine_id, who)
            await self._changed()
            return None
        if target_day != day:
            # Moved: the copy goes to the other day; a routine of the series
            # is skipped on its own day, a one-day routine leaves it.
            origin = (old or {}).get("moved_from") or (
                None if one_day else {"date": day.isoformat(), "routine_id": routine_id}
            )
            if one_day:
                day_overrides.pop(routine_id, None)
            else:
                day_overrides[routine_id] = dict(old or {}) | {
                    "skip": True,
                    "moved": True,
                    "by": who,
                    "at": _iso(dt_util.now()),
                }
            self._audit(who, f"day_routine.{day.isoformat()}.{routine_id}", old, None)
            return await self._add_one_day(target_day, routine, origin, who)
        new = {k: v for k, v in (old or {}).items() if k != "shift_min"} | {
            "routine": routine,
            "by": who,
            "at": _iso(dt_util.now()),
        }
        day_overrides[routine_id] = new
        self._audit(who, f"day_routine.{day.isoformat()}.{routine_id}", old, new)
        await self._changed()
        return routine_id

    async def _add_one_day(
        self,
        day: date,
        routine: dict[str, Any],
        origin: dict[str, Any] | None,
        who: str,
    ) -> str:
        """Add a routine for one day only (``origin``: where it was moved from)."""
        routine_id = "d" + lg.new_id()
        new: dict[str, Any] = {
            "one_day": True,
            "routine": routine,
            "by": who,
            "at": _iso(dt_util.now()),
        }
        if origin:
            new["moved_from"] = origin
        self.data["overrides"].setdefault(day.isoformat(), {})[routine_id] = new
        self._audit(who, f"day_routine.{day.isoformat()}.{routine_id}", None, new)
        await self._changed()
        return routine_id

    def _restore_occurrence(self, day: date, routine_id: str, who: str) -> None:
        """Drop every change of one occurrence (a moved one goes back home)."""
        day_overrides = self.data["overrides"].get(day.isoformat(), {})
        old = day_overrides.pop(routine_id, None)
        self._audit(who, f"day_routine.{day.isoformat()}.{routine_id}", old, None)
        origin = (old or {}).get("moved_from")
        if origin:
            home = self.data["overrides"].get(origin["date"], {})
            back = home.get(origin["routine_id"])
            if back and back.get("moved"):
                home.pop(origin["routine_id"], None)
        elif old and old.get("moved"):
            self._drop_moved_copies(day.isoformat(), routine_id)

    def _drop_moved_copies(self, date_key: str, routine_id: str) -> None:
        """Remove the copies of an occurrence that was moved to other days."""
        origin = {"date": date_key, "routine_id": routine_id}
        for overrides in self.data["overrides"].values():
            for key in [
                k for k, o in overrides.items() if o.get("moved_from") == origin
            ]:
                del overrides[key]

    async def async_save_notifications(
        self, rules: list[dict[str, Any]], *, who: str = "parent"
    ) -> list[dict[str, Any]]:
        """Replace the notification rules."""
        for rule in rules:
            if not rule.get("id"):
                rule["id"] = lg.new_id()
        self._audit(who, "notifications", len(self.data["notifications"]), len(rules))
        self.data["notifications"] = rules
        await self._changed()
        return rules

    @staticmethod
    def child_devices(child: dict[str, Any]) -> list[str]:
        """The knobs a child is assigned to (none: every knob)."""
        if "device_ids" in child:
            return [str(d) for d in child.get("device_ids") or [] if d]
        return [child["device_id"]] if child.get("device_id") else []

    async def async_set_device_options(
        self,
        device_id: str,
        *,
        children: list[str] | None = None,
        hide_locked: bool | None = None,
        background: str | None = None,
        clear_background: bool = False,
        who: str = "parent",
    ) -> None:
        """A knob's own options: the children usable on it, whether the
        others are hidden (or shown locked), and its own background."""
        device = self.data["devices"].setdefault(device_id, {})
        if children is not None:
            allowed = set(children)
            old = sorted(self.device_children(device_id))
            # Stored as the children left out, so a new child can be used on
            # every knob.
            device["excluded"] = sorted(
                c["id"] for c in self.data["children"] if c["id"] not in allowed
            )
            self._audit(who, f"device_children.{device_id}", old, sorted(allowed))
        if hide_locked is not None:
            device["hide_locked"] = bool(hide_locked)
        if background is not None or clear_background:
            await self._set_device_background(
                device_id, None if clear_background else background, who=who
            )
            return
        await self._changed()

    async def async_theme_updated(self) -> None:
        """The chosen theme's pictures changed: every knob restarts to show
        them (like after a background change)."""
        self.settings["background_seq"] = int(self.settings.get("background_seq", 0)) + 1
        for device in self.data["devices"].values():
            if "background_seq" in device:
                device["background_seq"] = int(device["background_seq"]) + 1
        await self._changed()

    @property
    def theme(self) -> dict[str, Any]:
        """The chosen theme (the default one when it is not available)."""
        return theme_of(self.settings.get("theme"))

    def child_theme_id(self, child: dict[str, Any]) -> str:
        """A child's own theme, when it differs from the common one ("" otherwise
        or when that theme cannot be chosen any more)."""
        theme_id = str(child.get("theme") or "")
        if (
            not theme_id
            or theme_id == self.theme["id"]
            or theme_id in self.settings.get("themes_off", [])
        ):
            return ""
        return theme_id if theme_of(theme_id)["id"] == theme_id else ""

    def _themed_background(self, background: str) -> str:
        """A background preset in the chosen theme's style; uploaded pictures
        and the default theme stay as they are."""
        theme_id = self.theme["id"]
        if (
            theme_id == DEFAULT_THEME
            or not re.match(r"^bg_[1-6]$", background)
            or not has_file(theme_id, f"backgrounds/{background}.jpg")
        ):
            return background
        return f"t_{theme_id}__{background}"

    def device_background(self, device_id: str) -> tuple[str, int]:
        """A knob's background and its change counter (see "bgs")."""
        device = self.data["devices"].get(device_id, {})
        if "background" in device:
            return str(device["background"] or ""), int(device.get("background_seq", 0))
        return str(self.settings.get("background") or ""), int(
            self.settings.get("background_seq", 0)
        )

    async def _set_device_background(
        self, device_id: str, background: str | None, *, who: str
    ) -> None:
        """Set (a value) or clear (None: the common one) a knob's background."""
        if background is not None and not re.match(BACKGROUND_VALUE, background):
            raise KisSegitoError("invalid_background")
        old, seq = self.device_background(device_id)
        device = self.data["devices"].setdefault(device_id, {})
        if background is None:
            device.pop("background", None)
            device.pop("background_seq", None)
        else:
            device["background"] = background
            # Counts only real changes: choosing the shown one again changes
            # nothing on the knob.
            device["background_seq"] = seq if background == old else seq + 1
        self._audit(who, f"device_background.{device_id}", old, background)
        await self._changed()

    @staticmethod
    def _normalise_routine(routine: dict[str, Any]) -> None:
        for key in ("tasks", "checkpoints", "zones", "reward_bands", "children"):
            routine.setdefault(key, [])
        for item in routine["tasks"] + routine["checkpoints"]:
            if not item.get("id"):
                item["id"] = lg.new_id()

    # ------------------------------------------------------------ ledger

    @property
    def transactions(self) -> list[dict[str, Any]]:
        """All transactions, oldest first."""
        return self.store.ledger["transactions"]

    def balances(self, child_id: str) -> dict[str, int]:
        """Wallet and piggy balance, derived from the ledger."""
        return lg.balances(self.transactions, child_id)

    def transaction(self, tx_id: str) -> dict[str, Any] | None:
        """One transaction by id."""
        return next((t for t in self.transactions if t["id"] == tx_id), None)

    def corrections_of(self, tx_id: str) -> list[dict[str, Any]]:
        """Correction transactions of a transaction."""
        return [t for t in self.transactions if t.get("corrects") == tx_id]

    def _append(self, tx: dict[str, Any]) -> dict[str, Any]:
        self.transactions.append(tx)
        return tx

    def _new_tx(
        self,
        child_id: str,
        reason: str,
        lines: list[dict[str, Any]],
        *,
        source: str,
        creator: str,
        refs: dict[str, Any] | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        try:
            return lg.make_transaction(
                child_id,
                reason,
                lines,
                timestamp=_iso(dt_util.now()),
                source=source,
                creator=creator,
                refs=refs,
                note=note,
            )
        except lg.LedgerError as err:
            raise KisSegitoError(err.code) from err

    async def async_adjust(
        self,
        child_id: str,
        amount: int,
        *,
        account: str = lg.WALLET,
        note: str = "",
        creator: str = "parent",
        source: str = "panel",
    ) -> dict[str, Any]:
        """Manual bonus (positive) or debit (negative)."""
        self._require_child(child_id)
        if amount < 0 and self.balances(child_id)[account] + amount < 0:
            raise KisSegitoError("insufficient_balance")
        tx = self._append(
            self._new_tx(
                child_id,
                lg.REASON_MANUAL,
                [{"account": account, "amount": amount}],
                source=source,
                creator=creator,
                note=note,
            )
        )
        await self._changed(ledger=True)
        self._fire(
            "manual_adjustment", child_id, transaction_id=tx["id"], amount=amount
        )
        return tx

    async def async_redeem(
        self,
        child_id: str,
        reward_id: str,
        *,
        source: str = "device",
        creator: str = "child",
    ) -> dict[str, Any]:
        """Buy a reward: no approval, but the balance must cover it."""
        child = self._require_child(child_id)
        reward = self.reward(reward_id)
        if reward is None or not reward.get("active", True):
            raise KisSegitoError("unknown_reward")
        piggy_unlock = reward.get("kind") == "piggy_unlock"
        if piggy_unlock and child.get("piggy_unlocked"):
            raise KisSegitoError("already_unlocked")
        cost = int(reward.get("cost", 0))
        if self.balances(child_id)[lg.WALLET] < cost:
            raise KisSegitoError("insufficient_balance")
        if reward.get("needs_confirmation"):
            return await self._request_reward(child, reward, cost, source, creator)
        tx: dict[str, Any] | None = None
        if cost > 0:
            tx = self._append(
                self._new_tx(
                    child_id,
                    lg.REASON_REDEMPTION,
                    [{"account": lg.WALLET, "amount": -cost}],
                    source=source,
                    creator=creator,
                    refs={
                        "reward_id": reward_id,
                        "reward_name": reward.get("name", ""),
                    },
                )
            )
        if piggy_unlock:
            child["piggy_unlocked"] = True
        await self._changed(ledger=tx is not None)
        self._fire(
            "reward_redeemed",
            child_id,
            transaction_id=tx["id"] if tx else None,
            reward_id=reward_id,
            reward_name=reward.get("name", ""),
            amount=-cost,
        )
        return tx or {}

    async def async_piggy_transfer(
        self,
        child_id: str,
        amount: int,
        *,
        source: str = "device",
        creator: str = "child",
    ) -> dict[str, Any]:
        """Move tokens into (positive) or out of (negative) the piggy bank."""
        child = self._require_child(child_id)
        if not child.get("piggy_unlocked"):
            raise KisSegitoError("piggy_locked")
        bal = self.balances(child_id)
        if amount == 0:
            raise KisSegitoError("zero_amount")
        if (amount > 0 and bal[lg.WALLET] < amount) or (
            amount < 0 and bal[lg.PIGGY] < -amount
        ):
            raise KisSegitoError("insufficient_balance")
        tx = self._append(
            self._new_tx(
                child_id,
                lg.REASON_PIGGY_TRANSFER,
                [
                    {"account": lg.WALLET, "amount": -amount},
                    {"account": lg.PIGGY, "amount": amount},
                ],
                source=source,
                creator=creator,
            )
        )
        await self._changed(ledger=True)
        self._fire(
            "piggy_deposit" if amount > 0 else "piggy_withdrawal",
            child_id,
            transaction_id=tx["id"],
            amount=abs(amount),
        )
        return tx

    async def async_reverse(
        self, tx_id: str, *, creator: str = "parent"
    ) -> dict[str, Any]:
        """Cancel a transaction with a compensating one (nothing is deleted)."""
        original = self.transaction(tx_id)
        if original is None:
            raise KisSegitoError("unknown_transaction")
        try:
            reversal = lg.reversal_of(
                original,
                self.corrections_of(tx_id),
                timestamp=_iso(dt_util.now()),
                source="panel",
                creator=creator,
            )
        except lg.LedgerError as err:
            raise KisSegitoError(err.code) from err
        original["reversed_by"] = reversal["id"]
        self._append(reversal)
        await self._changed(ledger=True)
        self._fire(
            "transaction_reversed",
            original["child_id"],
            transaction_id=reversal["id"],
            reverses=tx_id,
        )
        return reversal

    async def async_correct(
        self,
        tx_id: str,
        account: str,
        new_amount: int,
        *,
        creator: str = "parent",
        note: str = "",
    ) -> dict[str, Any]:
        """Change the effective amount of a transaction with a correction."""
        original = self.transaction(tx_id)
        if original is None:
            raise KisSegitoError("unknown_transaction")
        if original.get("reversed_by") or original.get("reverses"):
            raise KisSegitoError("reversed")
        current = {
            line["account"]: line["amount"]
            for line in lg.effective_lines(original, self.corrections_of(tx_id))
        }
        delta = int(new_amount) - current.get(account, 0)
        if delta == 0:
            raise KisSegitoError("zero_amount")
        tx = self._new_tx(
            original["child_id"],
            lg.REASON_CORRECTION,
            [{"account": account, "amount": delta}],
            source="panel",
            creator=creator,
            refs=original.get("refs"),
            note=note,
        )
        tx["corrects"] = tx_id
        tx["old_amount"] = current.get(account, 0)
        tx["new_amount"] = int(new_amount)
        original.setdefault("corrections", []).append(tx["id"])
        self._append(tx)
        await self._changed(ledger=True)
        self._fire(
            "transaction_revised",
            original["child_id"],
            transaction_id=tx["id"],
            corrects=tx_id,
            amount=delta,
        )
        return tx

    # ------------------------------------------------------------ own icons

    @property
    def icon_settings(self) -> dict[str, Any]:
        """Own (uploaded) icons and the built-in icons switched off."""
        icons = self.data.setdefault("icons", {})
        icons.setdefault("own", [])
        icons.setdefault("disabled", [])
        return icons

    def own_icon(self, key: str) -> dict[str, Any] | None:
        """An own icon by its key (``own_…``)."""
        return next((i for i in self.icon_settings["own"] if i["key"] == key), None)

    async def async_add_icon(self, image_id: str, name: str = "", *, who: str = "parent") -> str:
        """Add an uploaded picture as an own icon; returns its key."""
        if not re.match(r"^[a-z0-9_]{1,64}$", image_id):
            raise KisSegitoError("invalid_image")
        key = f"own_{lg.new_id()[:16]}"
        self.icon_settings["own"].append(
            {"key": key, "image": image_id, "name": name.strip(), "active": True}
        )
        self._audit(who, f"icon.{key}", None, image_id)
        await self._changed()
        return key

    async def async_replace_icon(self, key: str, image_id: str, *, who: str = "parent") -> None:
        """Give an own icon a new picture; everything using it shows the new one."""
        icon = self.own_icon(key)
        if icon is None:
            raise KisSegitoError("unknown_icon")
        if not re.match(r"^[a-z0-9_]{1,64}$", image_id):
            raise KisSegitoError("invalid_image")
        old = icon["image"]
        icon["image"] = image_id
        self._audit(who, f"icon.{key}", old, image_id)
        await self._changed()

    async def async_set_icon_active(self, key: str, active: bool, *, who: str = "parent") -> None:
        """Offer (or stop offering) an icon in the pickers; used ones keep working."""
        icon = self.own_icon(key)
        if icon is not None:
            icon["active"] = bool(active)
        else:
            disabled = self.icon_settings["disabled"]
            if active and key in disabled:
                disabled.remove(key)
            elif not active and key not in disabled:
                disabled.append(key)
        self._audit(who, f"icon_active.{key}", not active, active)
        await self._changed()

    def icon_usage(self, key: str) -> list[dict[str, str]]:
        """Where an icon is used: routines, their tasks and checkpoints, rewards."""
        used = []
        for routine in self.data["routines"]:
            if routine.get("icon") == key:
                used.append({"kind": "routine", "name": routine.get("name", "")})
            for task in routine.get("tasks", []):
                if task.get("icon") == key:
                    used.append(
                        {"kind": "task", "name": task.get("label") or routine.get("name", "")}
                    )
            for cp in routine.get("checkpoints", []):
                if cp.get("icon") == key:
                    used.append({"kind": "checkpoint", "name": cp.get("name", "")})
        for reward in self.data["rewards"]:
            if reward.get("icon") == key:
                used.append({"kind": "reward", "name": reward.get("name", "")})
        return used

    async def async_delete_icon(self, key: str, *, who: str = "parent") -> int:
        """Delete an own icon; what used it gets a built-in icon. Returns how
        many places were changed."""
        icon = self.own_icon(key)
        if icon is None:
            raise KisSegitoError("unknown_icon")
        changed = 0

        def swap(item: dict[str, Any], fallback: str) -> None:
            nonlocal changed
            if item.get("icon") == key:
                item["icon"] = fallback
                changed += 1

        for routine in self.data["routines"]:
            swap(routine, "routine_generic")
            for task in routine.get("tasks", []):
                swap(task, "task_clothes")
            for cp in routine.get("checkpoints", []):
                swap(cp, "checkpoint_flag")
        for reward in self.data["rewards"]:
            swap(reward, "fn_rewards")
        for overrides in self.data["overrides"].values():
            for override in overrides.values() if isinstance(overrides, dict) else []:
                one_day = override.get("routine") if isinstance(override, dict) else None
                if isinstance(one_day, dict):
                    swap(one_day, "routine_generic")
                    for task in one_day.get("tasks", []):
                        swap(task, "task_clothes")
                    for cp in one_day.get("checkpoints", []):
                        swap(cp, "checkpoint_flag")
        self.icon_settings["own"].remove(icon)
        self._audit(who, f"icon.{key}", icon["image"], None)
        await self._changed()
        return changed

    # ------------------------------------------------------------ approvals

    @property
    def approvals(self) -> list[dict[str, Any]]:
        """Approval requests, oldest first."""
        return self.store.ledger.setdefault("approvals", [])

    def approval(self, approval_id: str) -> dict[str, Any] | None:
        """One approval request by id."""
        return next((a for a in self.approvals if a["id"] == approval_id), None)

    def pending_approvals(self) -> list[dict[str, Any]]:
        """Requests still waiting for a parent, oldest first."""
        return [a for a in self.approvals if a["status"] == "pending"]

    def _task_approval(
        self, day: date, routine_id: str, child_id: str, checkpoint_id: str | None
    ) -> dict[str, Any] | None:
        """The approval request of a checkpoint's tasks on a day, if any."""
        return next(
            (
                a
                for a in self.approvals
                if a["kind"] == "task"
                and a["day"] == day.isoformat()
                and a["routine_id"] == routine_id
                and a["child_id"] == child_id
                and a.get("checkpoint_id") == checkpoint_id
            ),
            None,
        )

    def _log_approval_event(
        self, approval: dict[str, Any], event_type: str, **extra: Any
    ) -> None:
        """An approval step in the event log (history page and statistics)."""
        self._log_event(
            {
                "timestamp": _iso(dt_util.now()),
                "day": dt_util.now().date().isoformat(),
                "child_id": approval["child_id"],
                "type": event_type,
                "approval_id": approval["id"],
                "kind": approval["kind"],
                "name": approval.get("reward_name")
                or ", ".join(approval.get("task_names", []))
                or approval.get("routine_name", ""),
                "icon": approval.get("icon", ""),
                "tokens": int(approval.get("amount", 0)),
                "by": approval.get("resolved_by") or approval.get("requested_by", ""),
            }
            | extra
        )

    def _request_task(
        self,
        child_id: str,
        routine: dict[str, Any],
        task: dict[str, Any],
        checkpoint: dict[str, Any] | None,
        day: date,
        source: str,
    ) -> None:
        """A task that needs approval was done: add it to its request."""
        checkpoint_id = checkpoint["id"] if checkpoint else None
        approval = self._task_approval(day, routine["id"], child_id, checkpoint_id)
        if approval is not None and approval["status"] == "pending":
            approval["task_ids"].append(task["id"])
            approval["task_names"].append(task.get("label", ""))
            return
        approval = {
            "id": lg.new_id(),
            "kind": "task",
            "status": "pending",
            "child_id": child_id,
            "day": day.isoformat(),
            "routine_id": routine["id"],
            "routine_name": routine.get("name", ""),
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": (checkpoint or {}).get("name", ""),
            "task_ids": [task["id"]],
            "task_names": [task.get("label", "")],
            "icon": task.get("icon", ""),
            "amount": 0,
            "requested_at": _iso(dt_util.now()),
            "requested_by": source,
        }
        self.approvals.append(approval)
        self._log_approval_event(approval, "approval_requested")
        self._audit(source, f"approval.{approval['id']}", None, "requested")
        self._fire(
            "approval_requested",
            child_id,
            approval_id=approval["id"],
            kind="task",
            routine_id=routine["id"],
            task_id=task["id"],
        )

    async def _request_reward(
        self,
        child: dict[str, Any],
        reward: dict[str, Any],
        cost: int,
        source: str,
        creator: str,
    ) -> dict[str, Any]:
        """A reward that needs confirmation: its price is set aside now."""
        child_id = child["id"]
        if reward.get("kind") == "piggy_unlock" and any(
            a["kind"] == "reward"
            and a["child_id"] == child_id
            and a["reward_id"] == reward["id"]
            for a in self.pending_approvals()
        ):
            raise KisSegitoError("already_requested")
        approval: dict[str, Any] = {
            "id": lg.new_id(),
            "kind": "reward",
            "status": "pending",
            "child_id": child_id,
            "reward_id": reward["id"],
            "reward_name": reward.get("name", ""),
            "icon": reward.get("icon", ""),
            "amount": cost,
            "requested_at": _iso(dt_util.now()),
            "requested_by": creator if creator != "child" else source,
        }
        tx: dict[str, Any] | None = None
        if cost > 0:
            tx = self._append(
                self._new_tx(
                    child_id,
                    lg.REASON_REDEMPTION,
                    [{"account": lg.WALLET, "amount": -cost}],
                    source=source,
                    creator=creator,
                    refs={
                        "reward_id": reward["id"],
                        "reward_name": reward.get("name", ""),
                        "approval_id": approval["id"],
                    },
                    note="reserved",
                )
            )
            approval["tx"] = tx["id"]
        self.approvals.append(approval)
        self._log_approval_event(approval, "approval_requested")
        self._audit(creator, f"approval.{approval['id']}", None, "requested")
        await self._changed(ledger=True)
        self._fire(
            "approval_requested",
            child_id,
            approval_id=approval["id"],
            kind="reward",
            reward_id=reward["id"],
            reward_name=reward.get("name", ""),
            amount=-cost,
        )
        return tx or {}

    async def async_resolve_approval(
        self, approval_id: str, approve: bool, *, who: str = "parent"
    ) -> dict[str, Any]:
        """Approve or reject a request (once)."""
        approval = self.approval(approval_id)
        if approval is None:
            raise KisSegitoError("unknown_approval")
        if approval["status"] != "pending":
            raise KisSegitoError("already_resolved")
        approval["status"] = "approved" if approve else "rejected"
        approval["resolved_at"] = _iso(dt_util.now())
        approval["resolved_by"] = who
        child_id = approval["child_id"]
        if approval["kind"] == "reward":
            if approve:
                reward = self.reward(approval["reward_id"]) or {}
                if reward.get("kind") == "piggy_unlock":
                    child = self.child(child_id)
                    if child is not None:
                        child["piggy_unlocked"] = True
            elif approval.get("tx"):
                # The set-aside price goes back to the wallet.
                original = self.transaction(approval["tx"])
                if original is not None and not original.get("reversed_by"):
                    back = lg.reversal_of(
                        original,
                        self.corrections_of(original["id"]),
                        timestamp=_iso(dt_util.now()),
                        source="approval",
                        creator=who,
                    )
                    original["reversed_by"] = back["id"]
                    self._append(back)
                    approval["return_tx"] = back["id"]
        elif approve and int(approval.get("amount", 0)) > 0 and not approval.get("tx"):
            # The checkpoint was reached: its reward is paid now.
            tx = self._append(
                self._new_tx(
                    child_id,
                    lg.REASON_CHECKPOINT,
                    [{"account": lg.WALLET, "amount": int(approval["amount"])}],
                    source="approval",
                    creator=who,
                    refs={
                        "routine_id": approval["routine_id"],
                        "checkpoint_id": approval.get("checkpoint_id"),
                        "checkpoint_name": approval.get("checkpoint_name", ""),
                        "approval_id": approval["id"],
                    },
                )
            )
            approval["tx"] = tx["id"]
        event = "approval_approved" if approve else "approval_rejected"
        self._log_approval_event(approval, event)
        self._audit(who, f"approval.{approval_id}", "pending", approval["status"])
        await self._changed(ledger=True)
        self._fire(
            event,
            child_id,
            approval_id=approval_id,
            kind=approval["kind"],
            amount=int(approval.get("amount", 0)),
        )
        if approve and approval["kind"] == "reward":
            self._fire(
                "reward_redeemed",
                child_id,
                transaction_id=approval.get("tx"),
                reward_id=approval["reward_id"],
                reward_name=approval.get("reward_name", ""),
                amount=-int(approval.get("amount", 0)),
            )
        return approval

    # ------------------------------------------------------------ events

    @property
    def events(self) -> list[dict[str, Any]]:
        """Events without a token movement (tasks, checkpoints), oldest first."""
        return self.store.ledger.setdefault("events", [])

    def _log_event(self, event: dict[str, Any]) -> None:
        """Record an event for the statistics and the history page."""
        self.events.append({"id": lg.new_id()} | event)
        del self.events[:-EVENTS_KEPT]

    def _task_event(
        self,
        child_id: str,
        routine: dict[str, Any],
        task: dict[str, Any],
        at: str,
        by: str | None = None,
    ) -> dict[str, Any]:
        event = {"by": by} if by else {}
        return event | {
            "timestamp": at,
            "day": at[:10],
            "child_id": child_id,
            "type": "task_done",
            "routine_id": routine["id"],
            "routine_name": routine.get("name", ""),
            "task_id": task["id"],
            "task_name": task.get("label", ""),
            "icon": task.get("icon", ""),
        }

    def _checkpoint_event(
        self,
        child_id: str,
        routine: dict[str, Any],
        checkpoint: dict[str, Any],
        day: date,
        record: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """A completed checkpoint (``record``), or a missed one (None)."""
        due = self.checkpoint_time(routine, checkpoint, day)
        event = {
            "day": day.isoformat(),
            "child_id": child_id,
            "routine_id": routine["id"],
            "routine_name": routine.get("name", ""),
            "checkpoint_id": checkpoint["id"],
            "checkpoint_name": checkpoint.get("name", ""),
            "icon": checkpoint.get("icon") or "checkpoint_flag",
            "due": _iso(due),
        }
        if record is None:
            return event | {
                "timestamp": _iso(due),
                "type": "checkpoint_missed",
                "tokens": 0,
                "on_time": False,
            }
        done = dt_util.parse_datetime(record.get("at", "")) or due
        return event | {
            "timestamp": record.get("at") or _iso(due),
            "type": "checkpoint_done",
            "tokens": int(record.get("tokens", 0)),
            "on_time": bool(record.get("on_time")),
            "early_s": int((due - done).total_seconds()),
        }

    def _missed_checkpoints(self, day: date, child_id: str) -> list[dict[str, Any]]:
        """Events for the checkpoints a child did not reach on ``day``."""
        result = []
        for routine in self.routines_on_day(day):
            if not applies_to(routine, child_id):
                continue
            done = self.progress(day, routine["id"], child_id)["checkpoints"]
            for checkpoint in routine.get("checkpoints", []):
                if applies_to(checkpoint, child_id) and checkpoint["id"] not in done:
                    result.append(
                        self._checkpoint_event(child_id, routine, checkpoint, day, None)
                    )
        return result

    async def async_backfill_events(self) -> None:
        """Build the event log from the kept daily progress (first start)."""
        if self.events or not self.data["days"]:
            return
        today = self.today()
        found: list[dict[str, Any]] = []
        for key, routines in sorted(self.data["days"].items()):
            day = date.fromisoformat(key)
            for routine_id, by_child in routines.items():
                routine = self.routine_for_day(routine_id, day) or self.routine(
                    routine_id
                )
                if routine is None:
                    continue
                tasks = {t["id"]: t for t in routine.get("tasks", [])}
                cps = {c["id"]: c for c in routine.get("checkpoints", [])}
                for child_id, progress in by_child.items():
                    for task_id, at in progress.get("tasks", {}).items():
                        if task_id in tasks:
                            found.append(
                                self._task_event(child_id, routine, tasks[task_id], at)
                            )
                    for cp_id, record in progress.get("checkpoints", {}).items():
                        if cp_id in cps:
                            found.append(
                                self._checkpoint_event(
                                    child_id, routine, cps[cp_id], day, record
                                )
                            )
            if day < today:
                for child in self.children(active_only=True):
                    found.extend(self._missed_checkpoints(day, child["id"]))
        for event in sorted(found, key=lambda e: e["timestamp"]):
            self._log_event(event)
        if found:
            await self.store.async_save_ledger()

    def event_list(
        self,
        child_id: str | None = None,
        limit: int = 500,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Events, newest first, filtered like the token history."""
        needle = (search or "").strip().casefold()
        result = []
        for event in reversed(self.events):
            if child_id and event["child_id"] != child_id:
                continue
            day = event.get("day") or event["timestamp"][:10]
            if (date_from and day < date_from) or (date_to and day > date_to):
                continue
            if needle:
                child = self.child(event["child_id"]) or {}
                text = " ".join(
                    str(v)
                    for v in (
                        child.get("name"),
                        event.get("routine_name"),
                        event.get("task_name"),
                        event.get("checkpoint_name"),
                    )
                    if v
                ).casefold()
                if needle not in text:
                    continue
            result.append(event)
            if len(result) >= limit:
                break
        return result

    def history(
        self,
        child_id: str | None = None,
        limit: int = 200,
        *,
        reasons: list[str] | None = None,
        account: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Newest transactions first, each with its sequence number.

        Reversals and corrections are entries of their own that point to the
        original (``target_seq``); the original lists them (``revision_seqs``)
        and shows its effective amount.
        """
        seq = {tx["id"]: index + 1 for index, tx in enumerate(self.transactions)}
        revisions: dict[str, list[int]] = {}
        for tx in self.transactions:
            target = tx.get("corrects") or tx.get("reverses")
            if target:
                revisions.setdefault(target, []).append(seq[tx["id"]])
        result = []
        # Old and new effective amount of each correction, computed from the
        # ledger (corrections made before 0.3.1 did not store them, #14).
        before: dict[str, tuple[int, int]] = {}
        running: dict[tuple[str, str], int] = {}
        by_id = {tx["id"]: tx for tx in self.transactions}
        for tx in self.transactions:
            target = tx.get("corrects")
            if not target or target not in by_id:
                continue
            line = tx["lines"][0]
            key = (target, line["account"])
            if key not in running:
                running[key] = sum(
                    li["amount"]
                    for li in by_id[target]["lines"]
                    if li["account"] == line["account"]
                )
            old = running[key]
            running[key] = old + line["amount"]
            before[tx["id"]] = (old, running[key])
        needle = (search or "").strip().casefold()
        for tx in reversed(self.transactions):
            if child_id and tx["child_id"] != child_id:
                continue
            if reasons and tx["reason"] not in reasons:
                continue
            if account and not any(line["account"] == account for line in tx["lines"]):
                continue
            day = tx["timestamp"][:10]
            if (date_from and day < date_from) or (date_to and day > date_to):
                continue
            if needle:
                child = self.child(tx["child_id"]) or {}
                text = " ".join(
                    str(v)
                    for v in (
                        tx.get("note"),
                        tx.get("creator"),
                        child.get("name"),
                        *(tx.get("refs") or {}).values(),
                    )
                    if v
                ).casefold()
                if needle not in text and needle.lstrip("#") != str(seq[tx["id"]]):
                    continue
            item = dict(tx)
            item["seq"] = seq[tx["id"]]
            if tx["id"] in before:
                item["old_amount"], item["new_amount"] = before[tx["id"]]
            target = tx.get("corrects") or tx.get("reverses")
            item["target_seq"] = seq.get(target) if target else None
            item["revision_seqs"] = revisions.get(tx["id"], [])
            item["correction_seqs"] = [
                seq[c["id"]] for c in self.corrections_of(tx["id"])
            ]
            item["reversal_seq"] = seq.get(tx.get("reversed_by") or "")
            item["effective_lines"] = lg.effective_lines(
                tx, [] if target else self.corrections_of(tx["id"])
            )
            result.append(item)
            if len(result) >= limit:
                break
        return result

    # ------------------------------------------------------------ device actions

    def action_seen(self, action_id: str) -> dict[str, Any] | None:
        """The stored result of an already processed device action."""
        return self.store.ledger["actions"].get(action_id)

    async def async_device_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Run an action sent by a knob, at most once per action id."""
        action_id = str(action.get("id") or "")
        if action_id:
            previous = self.action_seen(action_id)
            if previous is not None:
                return previous
        kind = action.get("a")
        child_id = str(action.get("c") or "")
        try:
            if kind == "redeem":
                await self.async_redeem(child_id, str(action.get("r")))
            elif kind == "task":
                await self.async_complete_task(
                    child_id,
                    str(action.get("r")),
                    str(action.get("t")),
                    source="device",
                )
            elif kind == "piggy":
                await self.async_piggy_transfer(child_id, int(action.get("n", 0)))
            elif kind == "seen":
                # The child opened the piggy bank: the interest was shown.
                child = self._require_child(child_id)
                if child.pop("pending_interest", None):
                    await self._changed()
            else:
                raise KisSegitoError("unknown_action")
            result: dict[str, Any] = {"ok": True}
        except KisSegitoError as err:
            _LOGGER.info("Knob action %s refused: %s", kind, err.code)
            result = {"ok": False, "error": err.code}
        if action_id:
            self.store.ledger["actions"][action_id] = result | {
                "at": _iso(dt_util.now())
            }
            self._prune_actions()
            await self.store.async_save_ledger()
        return result

    def _prune_actions(self) -> None:
        """Forget processed action ids older than ACTION_TTL, keep at most ACTION_KEPT."""
        limit = dt_util.now() - ACTION_TTL
        actions = self.store.ledger["actions"]
        for key in [
            k
            for k, v in actions.items()
            if (parsed := dt_util.parse_datetime(v.get("at", ""))) is None
            or parsed < limit
        ]:
            del actions[key]
        # Insertion order is processing order: drop the oldest beyond the cap.
        for key in list(actions)[: max(0, len(actions) - ACTION_KEPT)]:
            del actions[key]

    # ------------------------------------------------------------ routines today

    def today(self) -> date:
        """The local calendar date."""
        return dt_util.now().date()

    def _progress(self, day: date, routine_id: str, child_id: str) -> dict[str, Any]:
        days = self.data["days"]
        key = day.isoformat()
        entry = days.setdefault(key, {}).setdefault(routine_id, {})
        return entry.setdefault(child_id, {"tasks": {}, "checkpoints": {}})

    def progress(self, day: date, routine_id: str, child_id: str) -> dict[str, Any]:
        """Read-only progress of a child in a routine on a day."""
        return (
            self.data["days"]
            .get(day.isoformat(), {})
            .get(routine_id, {})
            .get(child_id, {"tasks": {}, "checkpoints": {}})
        )

    def checkpoint_time(
        self, routine: dict[str, Any], checkpoint: dict[str, Any], day: date
    ) -> datetime:
        """When a checkpoint is due on ``day``."""
        tz = dt_util.get_default_time_zone()
        if checkpoint.get("time"):
            return at(day, checkpoint["time"], tz)
        return routine_window(routine, day, tz)[1]

    def task_checkpoint(
        self, routine: dict[str, Any], task: dict[str, Any]
    ) -> dict[str, Any] | None:
        """The checkpoint a task leads to (explicit, or the routine's last one)."""
        cps = routine.get("checkpoints", [])
        if task.get("checkpoint_id"):
            return next((c for c in cps if c["id"] == task["checkpoint_id"]), None)
        if not cps:
            return None
        day = self.today()
        return max(cps, key=lambda c: self.checkpoint_time(routine, c, day))

    async def async_complete_task(
        self,
        child_id: str,
        routine_id: str,
        task_id: str,
        *,
        source: str = "service",
        by: str | None = None,
    ) -> None:
        """Mark a task done; finishing a checkpoint's tasks completes it.

        ``by`` names the person who ticked it for the child (a parent)."""
        self._require_child(child_id)
        routine = self.routine_for_day(routine_id, self.today()) or self.routine(
            routine_id
        )
        if routine is None:
            raise KisSegitoError("unknown_routine")
        task = next((t for t in routine.get("tasks", []) if t["id"] == task_id), None)
        if task is None:
            raise KisSegitoError("unknown_task")
        day = self.today()
        progress = self._progress(day, routine_id, child_id)
        if task_id in progress["tasks"]:
            return
        progress["tasks"][task_id] = _iso(dt_util.now())
        self._log_event(
            self._task_event(
                child_id, routine, task, progress["tasks"][task_id], by
            )
        )
        self._fire("task_completed", child_id, routine_id=routine_id, task_id=task_id)
        checkpoint = self.task_checkpoint(routine, task)
        if task.get("needs_approval"):
            self._request_task(child_id, routine, task, checkpoint, day, source)
        if checkpoint is not None and applies_to(checkpoint, child_id):
            linked = [
                t
                for t in routine.get("tasks", [])
                if (self.task_checkpoint(routine, t) or {}).get("id")
                == checkpoint["id"]
            ]
            if all(t["id"] in progress["tasks"] for t in linked):
                self._complete_checkpoint(child_id, routine, checkpoint, day, source)
        self._prune_days()
        await self._changed(ledger=True)

    async def async_complete_checkpoint(
        self,
        child_id: str,
        routine_id: str,
        checkpoint_id: str,
        *,
        source: str = "service",
    ) -> None:
        """Complete a checkpoint directly (e.g. from an automation)."""
        self._require_child(child_id)
        routine = self.routine_for_day(routine_id, self.today()) or self.routine(
            routine_id
        )
        if routine is None:
            raise KisSegitoError("unknown_routine")
        checkpoint = next(
            (c for c in routine.get("checkpoints", []) if c["id"] == checkpoint_id),
            None,
        )
        if checkpoint is None:
            raise KisSegitoError("unknown_checkpoint")
        self._complete_checkpoint(child_id, routine, checkpoint, self.today(), source)
        await self._changed(ledger=True)

    def _complete_checkpoint(
        self,
        child_id: str,
        routine: dict[str, Any],
        checkpoint: dict[str, Any],
        day: date,
        source: str,
    ) -> bool:
        """Record a checkpoint and pay its time-based reward; True if paid."""
        progress = self._progress(day, routine["id"], child_id)
        if checkpoint["id"] in progress["checkpoints"]:
            return False
        now = dt_util.now()
        due = self.checkpoint_time(routine, checkpoint, day)
        tokens = reward_for(
            checkpoint.get("reward_bands", []), (due - now).total_seconds()
        )
        record: dict[str, Any] = {
            "at": _iso(now),
            "tokens": tokens,
            "on_time": now <= due,
        }
        approval = self._task_approval(day, routine["id"], child_id, checkpoint["id"])
        if approval is not None and approval["status"] != "approved":
            # Tasks of this checkpoint wait for a parent: the reward is worked
            # out now and paid on approval (or not at all when rejected).
            approval["amount"] = tokens
            record["approval"] = approval["id"]
            tokens_paid = 0
        else:
            tokens_paid = tokens
        if tokens_paid > 0:
            tx = self._append(
                self._new_tx(
                    child_id,
                    lg.REASON_CHECKPOINT,
                    [{"account": lg.WALLET, "amount": tokens}],
                    source=source,
                    creator="system",
                    refs={
                        "routine_id": routine["id"],
                        "checkpoint_id": checkpoint["id"],
                        "checkpoint_name": checkpoint.get("name", ""),
                    },
                )
            )
            record["tx"] = tx["id"]
            if approval is not None:
                approval["tx"] = tx["id"]
                approval["amount"] = tokens
        progress["checkpoints"][checkpoint["id"]] = record
        self._log_event(
            self._checkpoint_event(child_id, routine, checkpoint, day, record)
        )
        self._fire(
            "checkpoint_completed",
            child_id,
            routine_id=routine["id"],
            checkpoint_id=checkpoint["id"],
            amount=tokens,
        )
        return tokens_paid > 0

    def _prune_days(self) -> None:
        keep = (self.today() - timedelta(days=DAYS_KEPT)).isoformat()
        for key in [k for k in self.data["days"] if k < keep]:
            del self.data["days"][key]
        for key in [k for k in self.data["overrides"] if k < keep]:
            del self.data["overrides"][key]
        for key in [k for k in self.data["date_templates"] if k < keep]:
            del self.data["date_templates"][key]

    # ------------------------------------------------------------ streaks & interest

    def day_success(self, child_id: str, day: date) -> bool | None:
        """Whether a child met every streak-required checkpoint on ``day``.

        None when nothing was required that day (the streak is unchanged).
        """
        required = 0
        for routine in self.routines_on_day(day):
            if not applies_to(routine, child_id):
                continue
            done = self.progress(day, routine["id"], child_id)["checkpoints"]
            for checkpoint in routine.get("checkpoints", []):
                if not checkpoint.get("required_for_streak") or not applies_to(
                    checkpoint, child_id
                ):
                    continue
                required += 1
                if not done.get(checkpoint["id"], {}).get("on_time"):
                    return False
        return None if required == 0 else True

    async def async_evaluate_day(self, day: date) -> None:
        """Update streaks for a finished day (called after midnight)."""
        target = int(self.settings.get("streak_target", 7))
        reward = int(self.settings.get("streak_reward", 0))
        ledger_changed = False
        for child in self.children(active_only=True):
            streak = self.data["streaks"].setdefault(
                child["id"], {"current": 0, "last_day": None}
            )
            if streak.get("last_day") and streak["last_day"] >= day.isoformat():
                continue  # already evaluated
            for event in self._missed_checkpoints(day, child["id"]):
                self._log_event(event)
                ledger_changed = True
            success = self.day_success(child["id"], day)
            streak["last_day"] = day.isoformat()
            if success is None:
                continue
            if not success:
                streak["current"] = 0
                continue
            streak["current"] += 1
            if streak["current"] >= target > 0:
                streak["current"] = 0
                if reward > 0:
                    tx = self._append(
                        self._new_tx(
                            child["id"],
                            lg.REASON_STREAK,
                            [{"account": lg.WALLET, "amount": reward}],
                            source="system",
                            creator="system",
                        )
                    )
                    ledger_changed = True
                    self._fire(
                        "streak_completed",
                        child["id"],
                        transaction_id=tx["id"],
                        amount=reward,
                    )
        await self._changed(ledger=ledger_changed)

    async def async_pay_interest(self) -> None:
        """Weekly piggy-bank interest for every unlocked piggy bank."""
        paid = False
        for child in self.children(active_only=True):
            if not child.get("piggy_unlocked"):
                continue
            amount = interest_for(
                self.balances(child["id"])[lg.PIGGY],
                float(self.settings.get("piggy_interest_percent", 0)),
                self.settings.get("piggy_interest_min"),
                self.settings.get("piggy_interest_max"),
            )
            if amount <= 0:
                continue
            tx = self._append(
                self._new_tx(
                    child["id"],
                    lg.REASON_INTEREST,
                    [{"account": lg.PIGGY, "amount": amount}],
                    source="system",
                    creator="system",
                )
            )
            paid = True
            # Shown on the knob until the child opens the piggy bank.
            child["pending_interest"] = int(child.get("pending_interest", 0)) + amount
            self._fire(
                "piggy_interest", child["id"], transaction_id=tx["id"], amount=amount
            )
        if paid:
            await self._changed(ledger=True)

    def week_stats(self, child_id: str, last_day: date) -> dict[str, Any]:
        """Tasks done of the tasks due on the 7 days up to ``last_day``: per
        day and per routine (percent is None where nothing was due)."""

        def percent(done: int, total: int) -> int | None:
            return round(done * 100 / total) if total else None

        days = []
        routines: dict[str, dict[str, Any]] = {}
        for offset in range(6, -1, -1):
            day = last_day - timedelta(days=offset)
            done_day = total_day = 0
            for routine in self.routines_on_day(day):
                if not applies_to(routine, child_id):
                    continue
                tasks = routine.get("tasks", [])
                done = self.progress(day, routine["id"], child_id)["tasks"]
                count = sum(1 for t in tasks if t["id"] in done)
                done_day += count
                total_day += len(tasks)
                entry = routines.setdefault(
                    routine["id"],
                    {
                        "id": routine["id"],
                        "name": routine.get("name", ""),
                        "icon": routine.get("icon", "routine_generic"),
                        "done": 0,
                        "total": 0,
                    },
                )
                entry["done"] += count
                entry["total"] += len(tasks)
            days.append(
                {
                    "date": day.isoformat(),
                    "done": done_day,
                    "total": total_day,
                    "percent": percent(done_day, total_day),
                }
            )
        done_all = sum(d["done"] for d in days)
        total_all = sum(d["total"] for d in days)
        return {
            "days": days,
            "routines": [
                r | {"percent": percent(r["done"], r["total"])}
                for r in routines.values()
            ],
            "percent": percent(done_all, total_all),
        }

    def streak(self, child_id: str) -> int:
        """Current streak length of a child."""
        return int(self.data["streaks"].get(child_id, {}).get("current", 0))

    # ------------------------------------------------------------ device snapshot

    def device_token(self, device_id: str) -> str:
        """The knob's own secret for downloading pictures (created on demand)."""
        device = self.data["devices"].setdefault(device_id, {})
        if not device.get("token"):
            device["token"] = secrets.token_urlsafe(18)
            self.hass.async_create_task(self.store.async_save())
        return str(device["token"])

    def device_tokens(self) -> set[str]:
        """Every knob's picture secret."""
        return {d["token"] for d in self.data["devices"].values() if d.get("token")}

    def valid_device_token(self, token: str) -> bool:
        """Whether ``token`` is a knob's picture secret (constant-time compare)."""
        if not token:
            return False
        found = False
        for known in self.device_tokens():
            found |= hmac.compare_digest(token.encode(), known.encode())
        return found

    async def async_rotate_device_token(
        self, device_id: str, *, who: str = "parent"
    ) -> None:
        """Replace a knob's picture secret; the old one stops working at once."""
        device = self.data["devices"].setdefault(device_id, {})
        device["token"] = secrets.token_urlsafe(18)
        self._audit(who, f"device_token.{device_id}", None, None)
        await self._changed()

    def screen_settings(self, device_id: str) -> dict[str, Any]:
        """A knob's screen power settings: its own values over the general ones."""
        general = DEFAULT_SETTINGS["screen"] | (self.settings.get("screen") or {})
        own = self.data["devices"].get(device_id, {}).get("screen") or {}
        return general | {k: v for k, v in own.items() if v is not None}

    async def async_set_device_screen(
        self, device_id: str, values: dict[str, Any], *, who: str = "parent"
    ) -> None:
        """Override (a number) or clear (None) a knob's screen power settings."""
        device = self.data["devices"].setdefault(device_id, {})
        old = dict(device.get("screen") or {})
        new = {
            k: v
            for k, v in (old | values).items()
            if v is not None
            and (k in SCREEN_KEYS or k in SENSOR_KEYS or k == "saver_type")
        }
        device["screen"] = new
        self._audit(who, f"device_screen.{device_id}", old, new)
        await self._changed()

    # ------------------------------------------------------------ virtual knobs

    def virtual_knobs(self) -> list[dict[str, str]]:
        """Virtual knobs (the knob screen as a dashboard card), by name."""
        knobs = [
            {"id": device_id, "name": str(device.get("name") or "")}
            for device_id, device in self.data["devices"].items()
            if device.get("virtual")
        ]
        return sorted(knobs, key=lambda k: k["name"].lower())

    def is_virtual_knob(self, device_id: str) -> bool:
        """Whether a device id is a virtual knob."""
        return bool(self.data["devices"].get(device_id, {}).get("virtual"))

    async def async_save_virtual_knob(
        self, device_id: str | None, name: str, *, who: str = "parent"
    ) -> str:
        """Create (no id) or rename a virtual knob; returns its id."""
        name = name.strip()
        if not name:
            raise KisSegitoError("name_required")
        if device_id is None:
            device_id = f"virtual_{lg.new_id()}"
            self.data["devices"][device_id] = {"virtual": True}
        elif not self.is_virtual_knob(device_id):
            raise KisSegitoError("unknown_device")
        device = self.data["devices"][device_id]
        old = device.get("name")
        device["name"] = name
        self._audit(who, f"virtual_knob.{device_id}", old, name)
        await self._changed()
        return device_id

    async def async_delete_virtual_knob(
        self, device_id: str, *, who: str = "parent"
    ) -> None:
        """Remove a virtual knob; its children are no longer assigned to it."""
        if not self.is_virtual_knob(device_id):
            raise KisSegitoError("unknown_device")
        old = self.data["devices"].pop(device_id)
        self._audit(who, f"virtual_knob.{device_id}", old.get("name"), None)
        await self._changed()

    async def async_virtual_action(
        self, device_id: str, action: dict[str, Any]
    ) -> dict[str, Any]:
        """Run an action from a virtual knob, for a child selectable there."""
        if not self.is_virtual_knob(device_id):
            return {"ok": False, "error": "unknown_device"}
        if str(action.get("c") or "") not in self.device_children(device_id):
            return {"ok": False, "error": "not_selectable"}
        return await self.async_device_action(action)

    def device_inputs(self, device_id: str) -> dict[str, str]:
        """Home Assistant entities forwarded to a knob's sensor inputs."""
        inputs = self.data["devices"].get(device_id, {}).get("inputs") or {}
        return {k: v for k, v in inputs.items() if k in INPUT_KINDS and v}

    async def async_set_device_inputs(
        self, device_id: str, values: dict[str, str | None], *, who: str = "parent"
    ) -> None:
        """Choose (an entity id) or clear (None) a knob's forwarded inputs."""
        device = self.data["devices"].setdefault(device_id, {})
        old = dict(device.get("inputs") or {})
        new = {
            k: v for k, v in (old | values).items() if v and k in INPUT_KINDS
        }
        device["inputs"] = new
        self._audit(who, f"device_inputs.{device_id}", old, new)
        await self._changed()

    def _sensor_snapshot(self, device_id: str) -> dict[str, Any]:
        """The sensor-driven screen settings in the knob protocol's form."""
        values = self.screen_settings(device_id)
        result: dict[str, Any] = {}
        for key, short in SENSOR_KEYS.items():
            value = values.get(key, DEFAULT_SETTINGS["screen"][key])
            if isinstance(DEFAULT_SETTINGS["screen"][key], bool):
                result[short] = bool(value)
            elif key == "night_lux":
                result[short] = round(float(value), 1)
            elif key == "light_factor":
                result[short] = round(float(value), 2)
            else:
                result[short] = int(value)
        return result

    def device_children(self, device_id: str) -> set[str]:
        """Ids of the children usable on a knob: the ones ticked at the knob;
        until the knob's list is saved, the older per-child assignment (a
        child without a knob everywhere, an assigned child only there)."""
        children = self.children(active_only=True)
        device = self.data["devices"].get(device_id, {})
        if "excluded" in device:
            excluded = set(device["excluded"])
            return {c["id"] for c in children if c["id"] not in excluded}
        return {
            c["id"] for c in children if child_on_device(self.child_devices(c), device_id)
        }

    def device_hides_locked(self, device_id: str) -> bool:
        """Whether a knob hides the children not usable on it."""
        return bool(self.data["devices"].get(device_id, {}).get("hide_locked"))

    def snapshot(
        self, device_id: str, language: str, base_url: str | None = None
    ) -> dict[str, Any]:
        """The compact state a knob needs (schema 1, see docs/protocol.md)."""
        now = dt_util.now()
        day = now.date()
        tz = dt_util.get_default_time_zone()
        selectable = self.device_children(device_id)
        hide = self.device_hides_locked(device_id)
        children = []
        for child in self.children(active_only=True):
            if hide and child["id"] not in selectable:
                continue  # this knob hides the children not usable on it
            bal = self.balances(child["id"])
            children.append(
                {
                    "id": child["id"],
                    "a": child.get("avatar", DEFAULT_AVATAR),
                    "ai": child.get("avatar_image") or "",
                    "c": child.get("color", "#6CB8FF"),
                    "w": bal[lg.WALLET],
                    "p": bal[lg.PIGGY],
                    "pu": bool(child.get("piggy_unlocked")),
                    "pi": int(child.get("pending_interest", 0)),
                    "s": self.streak(child["id"]),
                    "st": int(self.settings.get("streak_target", 7)),
                    "sel": child["id"] in selectable,
                    # The child's own theme ("": the knob's theme).
                    "th": self.child_theme_id(child),
                }
            )
        rewards = [
            {
                "id": r["id"],
                "i": stored_icon(r.get("icon", "fn_rewards")),
                "ii": r.get("image") or "",
                "c": int(r.get("cost", 0)),
                "k": r.get("kind", "normal"),
            }
            for r in sorted(self.data["rewards"], key=lambda r: r.get("sort_order", 0))
            if r.get("active", True)
        ]
        routines = []
        for routine in self.routines_on_day(day):
            if not routine.get("on_device", True):
                continue
            start, end = routine_window(routine, day, tz)
            checkpoints = []
            for cp in routine.get("checkpoints", []):
                checkpoints.append(
                    {
                        "id": cp["id"],
                        "i": stored_icon(cp.get("icon", "checkpoint_flag")),
                        "t": int(self.checkpoint_time(routine, cp, day).timestamp()),
                        "ch": cp.get("children", []),
                        "b": [
                            [
                                int(float(b.get("min_early_min", 0)) * 60),
                                int(b.get("tokens", 0)),
                            ]
                            for b in cp.get("reward_bands", [])
                        ],
                    }
                )
            if checkpoints:
                end = max(
                    end, *(datetime.fromtimestamp(c["t"], tz) for c in checkpoints)
                )
            done = {
                child_id: sorted(entry.get("tasks", {}))
                for child_id, entry in self.data["days"]
                .get(day.isoformat(), {})
                .get(routine["id"], {})
                .items()
            }
            cps_done = {
                child_id: sorted(entry.get("checkpoints", {}))
                for child_id, entry in self.data["days"]
                .get(day.isoformat(), {})
                .get(routine["id"], {})
                .items()
            }
            # After its end the routine stays in the knob's menu while any task
            # is open for a child of the routine: as long as the last
            # checkpoint still pays late (a band with a negative threshold),
            # then for the "routine_menu_grace_s" setting longer.
            menu_until = int(end.timestamp())
            task_ids = {t["id"] for t in routine.get("tasks", [])}
            if any(
                not task_ids <= set(done.get(child["id"], []))
                for child in self.data["children"]
                if applies_to(routine, child["id"])
            ):
                if checkpoints:
                    last = max(checkpoints, key=lambda c: c["t"])
                    for early_s, _tokens in last["b"]:
                        menu_until = max(menu_until, last["t"] - min(early_s, 0))
                menu_until += int(self.settings.get("routine_menu_grace_s", 1800))
            routines.append(
                {
                    "id": routine["id"],
                    "i": stored_icon(routine.get("icon", "routine_generic")),
                    "s": int(start.timestamp()),
                    "e": int(end.timestamp()),
                    "m": menu_until,
                    "ch": routine.get("children", []),
                    "z": [
                        [
                            int(float(z.get("offset_min", 0)) * 60),
                            z.get("color", "#FF9F43"),
                        ]
                        for z in routine.get("zones", [])
                    ],
                    "base": routine.get("base_color", "#6BCB77"),
                    "cp": checkpoints,
                    "t": [
                        {
                            "id": t["id"],
                            "i": stored_icon(t.get("icon", "task_clothes")),
                            "cp": (self.task_checkpoint(routine, t) or {}).get(
                                "id", ""
                            ),
                        }
                        for t in routine.get("tasks", [])
                    ],
                    "done": done,
                    "cpd": cps_done,
                }
            )
        return {
            "v": 1,
            "now": int(now.timestamp()),
            "lang": language,
            "bg": self._themed_background(self.device_background(device_id)[0]),
            "bgs": self.device_background(device_id)[1],
            # The theme: its pictures come from Home Assistant ("t_<id>__…"),
            # its colours replace the knob's own (empty: the built-in look).
            "th": "" if self.theme["id"] == DEFAULT_THEME else self.theme["id"],
            "tc": self.theme["knob"],
            # Colours of the children's own themes.
            "tcs": {
                theme_id: theme_of(theme_id)["knob"]
                for theme_id in {
                    self.child_theme_id(c) for c in self.children(active_only=True)
                }
                if theme_id
            },
            "scr": {
                key: int(value)
                for key, value in zip(
                    ("saver", "dim", "lvl", "blank", "off"),
                    (self.screen_settings(device_id)[k] for k in SCREEN_KEYS),
                    strict=True,
                )
            }
            | {"ss": str(self.screen_settings(device_id).get("saver_type", "balls"))},
            "sen": self._sensor_snapshot(device_id),
            "anim": self.settings.get("animation_mode", "full"),
            "idle": int(self.settings.get("inactivity_s", 60)),
            "children": children,
            "rewards": rewards,
            "routines": routines,
            # Where the knob downloads uploaded pictures, and its secret.
            "img": {
                "u": base_url or "",
                "t": self.device_token(device_id) if base_url else "",
            },
        }
