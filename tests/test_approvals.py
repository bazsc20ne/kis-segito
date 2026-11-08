# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for approvals: rewards that need confirmation, tasks that need approval."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from custom_components.kis_segito.const import EVENT_KIS_SEGITO
from custom_components.kis_segito.manager import KisSegitoError, KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


async def test_reward_needs_confirmation(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    events: list[Event] = []
    hass.bus.async_listen(EVENT_KIS_SEGITO, callback(lambda e: events.append(e)))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    reward = await manager.async_save_item(
        "rewards", {"name": "Film", "cost": 4, "needs_confirmation": True}
    )
    await manager.async_adjust(kid, 6)

    # The price is set aside at once: the same tokens cannot be spent twice.
    await manager.async_redeem(kid, reward["id"])
    assert manager.balances(kid)["wallet"] == 2
    with pytest.raises(KisSegitoError):
        await manager.async_redeem(kid, reward["id"])
    pending = manager.pending_approvals()
    assert [(a["kind"], a["amount"]) for a in pending] == [("reward", 4)]
    await hass.async_block_till_done()
    assert events[-1].data["event_type"] == "approval_requested"

    # Rejected: the price goes back.
    await manager.async_resolve_approval(pending[0]["id"], False, who="Parent")
    assert manager.balances(kid)["wallet"] == 6
    assert manager.pending_approvals() == []
    with pytest.raises(KisSegitoError) as err:
        await manager.async_resolve_approval(pending[0]["id"], True)
    assert err.value.code == "already_resolved"

    # Approved: the set-aside tokens stay spent.
    await manager.async_redeem(kid, reward["id"])
    second = manager.pending_approvals()[0]
    await manager.async_resolve_approval(second["id"], True, who="Parent")
    assert manager.balances(kid)["wallet"] == 2
    await hass.async_block_till_done()
    assert [e.data["event_type"] for e in events[-2:]] == [
        "approval_approved",
        "reward_redeemed",
    ]
    # Every step is logged: requests and decisions, with who.
    steps = [e["type"] for e in manager.events if e["type"].startswith("approval_")]
    assert steps == [
        "approval_requested",
        "approval_rejected",
        "approval_requested",
        "approval_approved",
    ]
    assert manager.events[-1]["by"] == "Parent"
    assert any(a["what"].startswith("approval.") for a in manager.data["audit"])


async def test_piggy_unlock_waits_for_confirmation(manager: KisSegitoManager) -> None:
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    child = manager.child(kid)
    child["piggy_unlocked"] = False
    unlock = await manager.async_save_item(
        "rewards",
        {"name": "Piggy", "cost": 1, "kind": "piggy_unlock", "needs_confirmation": True},
    )
    await manager.async_adjust(kid, 5)
    await manager.async_redeem(kid, unlock["id"])
    assert not manager.child(kid).get("piggy_unlocked")
    with pytest.raises(KisSegitoError) as err:
        await manager.async_redeem(kid, unlock["id"])
    assert err.value.code == "already_requested"
    await manager.async_resolve_approval(manager.pending_approvals()[0]["id"], True)
    assert manager.child(kid)["piggy_unlocked"]


async def _routine(manager: KisSegitoManager, needs_approval: bool) -> dict:
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Morning",
            "start": "07:00",
            "end": "08:00",
            "checkpoints": [
                {
                    "name": "Ready",
                    "time": "07:50",
                    "reward_bands": [{"min_early_min": 0, "tokens": 3}],
                }
            ],
            "tasks": [
                {"icon": "task_breakfast", "label": "Eat"},
                {"icon": "task_shoes", "label": "Shoes", "needs_approval": needs_approval},
            ],
        },
    )
    cp = routine["checkpoints"][0]["id"]
    for task in routine["tasks"]:
        task["checkpoint_id"] = cp
    return await manager.async_save_item("routines", routine)


@pytest.mark.parametrize("approve", [True, False])
async def test_task_needs_approval(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory, approve: bool
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, True)
    eat, shoes = (t["id"] for t in routine["tasks"])
    await manager.async_complete_task(kid, routine["id"], shoes)
    # Done at once (the knob shows it ticked), waiting for a parent.
    assert shoes in manager.progress(manager.today(), routine["id"], kid)["tasks"]
    pending = manager.pending_approvals()
    assert [(a["kind"], a["task_names"], a["amount"]) for a in pending] == [
        ("task", ["Shoes"], 3)
    ]
    # The checkpoint is reached: its reward (worked out now) waits too.
    await manager.async_complete_task(kid, routine["id"], eat)
    assert manager.balances(kid)["wallet"] == 0
    assert manager.pending_approvals()[0]["amount"] == 3
    freezer.tick(3600)  # approved much later: the amount stays as it was
    await manager.async_resolve_approval(pending[0]["id"], approve, who="Parent")
    assert manager.balances(kid)["wallet"] == (3 if approve else 0)
    # Either way the task and the checkpoint stay done.
    done = manager.progress(manager.today(), routine["id"], kid)
    assert shoes in done["tasks"]
    assert routine["checkpoints"][0]["id"] in done["checkpoints"]


async def test_task_approved_before_checkpoint(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, True)
    eat, shoes = (t["id"] for t in routine["tasks"])
    await manager.async_complete_task(kid, routine["id"], shoes)
    await manager.async_resolve_approval(manager.pending_approvals()[0]["id"], True)
    # Approved already: the checkpoint pays as usual when it is reached.
    await manager.async_complete_task(kid, routine["id"], eat)
    assert manager.balances(kid)["wallet"] == 3


async def test_task_without_approval_pays_at_once(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, False)
    for task in routine["tasks"]:
        await manager.async_complete_task(kid, routine["id"], task["id"])
    assert manager.balances(kid)["wallet"] == 3
    assert manager.pending_approvals() == []


async def _both_need_approval(manager: KisSegitoManager) -> dict:
    routine = await _routine(manager, True)
    routine["tasks"][0]["needs_approval"] = True
    return await manager.async_save_item("routines", routine)


@pytest.mark.parametrize("approve_last", [True, False])
async def test_checkpoint_waits_for_every_request(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory, approve_last: bool
) -> None:
    """Two tasks of a checkpoint need approval, the first is approved before
    the second is done: the checkpoint pays only when the second one is
    approved, and nothing when it is rejected (#53)."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _both_need_approval(manager)
    eat, shoes = (t["id"] for t in routine["tasks"])
    await manager.async_complete_task(kid, routine["id"], eat)
    first = manager.pending_approvals()[0]
    await manager.async_resolve_approval(first["id"], True)
    assert manager.balances(kid)["wallet"] == 0
    # The last task reaches the checkpoint: still nothing paid, and the
    # request shows what it would bring.
    await manager.async_complete_task(kid, routine["id"], shoes)
    assert manager.balances(kid)["wallet"] == 0
    second = manager.pending_approvals()[0]
    assert second["id"] != first["id"] and second["amount"] == 3
    await manager.async_resolve_approval(second["id"], approve_last)
    assert manager.balances(kid)["wallet"] == (3 if approve_last else 0)
    # Both tasks and the checkpoint stay done; paid once at most.
    done = manager.progress(manager.today(), routine["id"], kid)
    assert {eat, shoes} <= set(done["tasks"])
    paid = [
        tx for tx in manager.transactions if tx["reason"] == "checkpoint_reward"
    ]
    assert len(paid) == (1 if approve_last else 0)


async def test_checkpoint_with_two_pending_requests(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """Both requests wait when the checkpoint is reached: it pays once, when
    the last one is approved; a rejection of either withholds it."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _both_need_approval(manager)
    for task in routine["tasks"]:
        await manager.async_complete_task(kid, routine["id"], task["id"])
    # One request for the checkpoint's tasks (they are grouped).
    pending = manager.pending_approvals()
    assert len(pending) == 1 and pending[0]["amount"] == 3
    await manager.async_resolve_approval(pending[0]["id"], True)
    assert manager.balances(kid)["wallet"] == 3
    # Already paid: nothing more happens.
    assert len([t for t in manager.transactions if t["reason"] == "checkpoint_reward"]) == 1


async def test_rejected_before_checkpoint(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """A rejected task: the checkpoint reached later pays nothing."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, True)
    eat, shoes = (t["id"] for t in routine["tasks"])
    await manager.async_complete_task(kid, routine["id"], shoes)
    await manager.async_resolve_approval(manager.pending_approvals()[0]["id"], False)
    await manager.async_complete_task(kid, routine["id"], eat)
    assert manager.balances(kid)["wallet"] == 0
    cp = routine["checkpoints"][0]["id"]
    assert manager.progress(manager.today(), routine["id"], kid)["checkpoints"][cp][
        "withheld"
    ]


async def test_request_shows_tokens_before_the_checkpoint(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """A request that holds only some tasks of a checkpoint already shows
    the tokens the checkpoint would bring (#57)."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, True)
    await manager.async_complete_task(kid, routine["id"], routine["tasks"][1]["id"])
    assert manager.pending_approvals()[0]["amount"] == 3


async def test_rejected_checkpoint_records_no_tokens(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """After a rejection the checkpoint is recorded with no tokens, in the
    day progress and in the event log (#57)."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _both_need_approval(manager)
    for task in routine["tasks"]:
        await manager.async_complete_task(kid, routine["id"], task["id"])
    await manager.async_resolve_approval(manager.pending_approvals()[0]["id"], False)
    cp = routine["checkpoints"][0]["id"]
    record = manager.progress(manager.today(), routine["id"], kid)["checkpoints"][cp]
    assert record["tokens"] == 0 and record["withheld"]
    events = [e for e in manager.events if e["type"] == "checkpoint_done"]
    assert [e["tokens"] for e in events] == [0]
