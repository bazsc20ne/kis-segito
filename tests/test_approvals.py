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
async def test_checkpoint_needs_approval(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory, approve: bool
) -> None:
    """A checkpoint that needs approval asks once, when it is reached; its
    reward is paid on approval and withheld on rejection."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, True)
    cp = routine["checkpoints"][0]["id"]
    # The task's approval setting moved to its checkpoint.
    assert routine["checkpoints"][0]["needs_approval"]
    assert not any("needs_approval" in t for t in routine["tasks"])
    eat, shoes = (t["id"] for t in routine["tasks"])
    await manager.async_complete_task(kid, routine["id"], shoes)
    assert manager.pending_approvals() == []  # tasks are not approved
    await manager.async_complete_task(kid, routine["id"], eat)
    pending = manager.pending_approvals()
    assert [(a["kind"], a["checkpoint_name"], a["amount"]) for a in pending] == [
        ("checkpoint", "Ready", 3)
    ]
    assert manager.balances(kid)["wallet"] == 0
    freezer.tick(3600)  # decided much later: the amount stays as it was
    await manager.async_resolve_approval(pending[0]["id"], approve, who="Parent")
    assert manager.balances(kid)["wallet"] == (3 if approve else 0)
    record = manager.progress(manager.today(), routine["id"], kid)["checkpoints"][cp]
    assert {shoes, eat} <= set(manager.progress(manager.today(), routine["id"], kid)["tasks"])
    if approve:
        assert record["tx"] and record["tokens"] == 3
    else:
        assert record["withheld"] and record["tokens"] == 0
        events = [e for e in manager.events if e["type"] == "checkpoint_done"]
        assert [e["tokens"] for e in events] == [0]
    # Decided once.
    with pytest.raises(KisSegitoError):
        await manager.async_resolve_approval(pending[0]["id"], True)


async def test_checkpoint_without_tokens_asks_nothing(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """Reached too late for any reward: nothing to approve."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=55, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, True)
    for task in routine["tasks"]:
        await manager.async_complete_task(kid, routine["id"], task["id"])
    assert manager.pending_approvals() == []


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


async def test_waiting_task_request_from_before(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """A task request made before the change still settles its checkpoint."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "A"}))["id"]
    routine = await _routine(manager, False)
    cp = routine["checkpoints"][0]["id"]
    manager.approvals.append(
        {
            "id": "old1", "kind": "task", "status": "pending", "child_id": kid,
            "day": manager.today().isoformat(), "routine_id": routine["id"],
            "checkpoint_id": cp, "task_ids": [routine["tasks"][1]["id"]],
            "task_names": ["Shoes"], "amount": 0,
            "requested_at": dt_util.now().isoformat(),
        }
    )
    for task in routine["tasks"]:
        await manager.async_complete_task(kid, routine["id"], task["id"])
    assert manager.balances(kid)["wallet"] == 0
    await manager.async_resolve_approval("old1", True)
    assert manager.balances(kid)["wallet"] == 3


async def test_old_task_setting_moves_on_start(manager: KisSegitoManager) -> None:
    manager.data["routines"] = [
        {
            "id": "r1", "name": "Morning", "start": "07:00", "end": "08:00",
            "checkpoints": [{"id": "c1", "name": "Ready", "time": "07:50"}],
            "tasks": [{"id": "t1", "label": "Shoes", "needs_approval": True}],
        }
    ]
    await manager.async_fix_task_approvals()
    routine = manager.data["routines"][0]
    assert routine["checkpoints"][0]["needs_approval"]
    assert "needs_approval" not in routine["tasks"][0]
