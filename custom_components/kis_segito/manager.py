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
import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import ledger as lg
from .const import EVENT_KIS_SEGITO
from .logic import (
    applies_to,
    at,
    interest_for,
    reward_for,
    routine_runs_on,
    routine_window,
    routine_with_override,
    selectable_children,
)
from .store import AUDIT_KEPT, KisSegitoStore

_LOGGER = logging.getLogger(__name__)

# Device action ids are remembered this long (duplicate retries are ignored).
ACTION_TTL = timedelta(days=7)
ACTION_KEPT = 2000
# Daily progress is kept this long.
DAYS_KEPT = 31

COLLECTIONS = ("children", "routines", "rewards", "templates")


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
        self.settings.update(changes)
        await self._changed()

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
        who: str = "parent",
    ) -> str | None:
        """Edit a routine for one day only, add a one-day routine, or restore.

        ``routine_id`` None with a routine adds a one-day routine; a routine of
        None restores the original (or removes a one-day routine). The source
        routine is never changed. Past days are read-only.
        """
        if day < self.today():
            raise KisSegitoError("past_day")
        day_overrides = self.data["overrides"].setdefault(day.isoformat(), {})
        if routine is not None:
            routine = {
                k: v
                for k, v in routine.items()
                if k not in ("id", "weekdays", "active", "one_day")
            }
            self._normalise_routine(routine)
        if routine_id is None:
            if routine is None:
                raise KisSegitoError("unknown_routine")
            routine_id = "d" + lg.new_id()
            new: dict[str, Any] | None = {"one_day": True, "routine": routine}
            old = None
        else:
            old = day_overrides.get(routine_id)
            one_day = bool(old and old.get("one_day"))
            if not one_day and self.routine(routine_id) is None:
                raise KisSegitoError("unknown_routine")
            if routine is None:
                new = (
                    None
                    if one_day
                    else {k: v for k, v in (old or {}).items() if k != "routine"}
                )
                if new is not None and not (new.get("skip") or new.get("shift_min")):
                    new = None
            else:
                new = dict(old or {}) | {"routine": routine}
        if new is None:
            day_overrides.pop(routine_id, None)
        else:
            new |= {"by": who, "at": _iso(dt_util.now())}
            day_overrides[routine_id] = new
        self._audit(who, f"day_routine.{day.isoformat()}.{routine_id}", old, new)
        await self._changed()
        return routine_id if new is not None else None

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

    async def async_assign_device(self, child_id: str, device_id: str | None) -> None:
        """Assign a child to a knob (a child has at most one knob)."""
        child = self._require_child(child_id)
        child["device_id"] = device_id or None
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
    ) -> None:
        """Mark a task done; finishing a checkpoint's tasks completes it."""
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
        self._fire("task_completed", child_id, routine_id=routine_id, task_id=task_id)
        checkpoint = self.task_checkpoint(routine, task)
        ledger_changed = False
        if checkpoint is not None and applies_to(checkpoint, child_id):
            linked = [
                t
                for t in routine.get("tasks", [])
                if (self.task_checkpoint(routine, t) or {}).get("id")
                == checkpoint["id"]
            ]
            if all(t["id"] in progress["tasks"] for t in linked):
                ledger_changed = self._complete_checkpoint(
                    child_id, routine, checkpoint, day, source
                )
        self._prune_days()
        await self._changed(ledger=ledger_changed)

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
        changed = self._complete_checkpoint(
            child_id, routine, checkpoint, self.today(), source
        )
        await self._changed(ledger=changed)

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
        if tokens > 0:
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
        progress["checkpoints"][checkpoint["id"]] = record
        self._fire(
            "checkpoint_completed",
            child_id,
            routine_id=routine["id"],
            checkpoint_id=checkpoint["id"],
            amount=tokens,
        )
        return tokens > 0

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

    def device_children(self, device_id: str) -> set[str]:
        """Ids of the children selectable on a knob."""
        children = self.children(active_only=True)
        assigned = [c["id"] for c in children if c.get("device_id") == device_id]
        return selectable_children([c["id"] for c in children], assigned)

    def snapshot(
        self, device_id: str, language: str, base_url: str | None = None
    ) -> dict[str, Any]:
        """The compact state a knob needs (schema 1, see docs/protocol.md)."""
        now = dt_util.now()
        day = now.date()
        tz = dt_util.get_default_time_zone()
        selectable = self.device_children(device_id)
        children = []
        for child in self.children(active_only=True):
            bal = self.balances(child["id"])
            children.append(
                {
                    "id": child["id"],
                    "a": child.get("avatar", "test_avatar_1"),
                    "ai": child.get("avatar_image") or "",
                    "c": child.get("color", "#6CB8FF"),
                    "w": bal[lg.WALLET],
                    "p": bal[lg.PIGGY],
                    "pu": bool(child.get("piggy_unlocked")),
                    "pi": int(child.get("pending_interest", 0)),
                    "s": self.streak(child["id"]),
                    "st": int(self.settings.get("streak_target", 7)),
                    "sel": child["id"] in selectable,
                }
            )
        rewards = [
            {
                "id": r["id"],
                "i": r.get("icon", "fn_rewards"),
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
                        "i": cp.get("icon", "checkpoint_flag"),
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
            routines.append(
                {
                    "id": routine["id"],
                    "i": routine.get("icon", "routine_generic"),
                    "s": int(start.timestamp()),
                    "e": int(end.timestamp()),
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
                            "i": t.get("icon", "task_generic"),
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
