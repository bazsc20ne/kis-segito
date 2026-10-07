# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the manager: ledger operations, routines, device actions."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from custom_components.kis_segito.const import EVENT_KIS_SEGITO
from custom_components.kis_segito.manager import KisSegitoError, KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore, _migrate_config


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


async def _child(manager: KisSegitoManager, name: str = "A") -> str:
    child = await manager.async_save_item(
        "children", {"name": name, "color": "#123456"}
    )
    return child["id"]


async def test_redeem_and_balance(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    events: list[Event] = []
    hass.bus.async_listen(EVENT_KIS_SEGITO, callback(lambda e: events.append(e)))
    kid = await _child(manager)
    reward = await manager.async_save_item("rewards", {"name": "Story", "cost": 8})
    with pytest.raises(KisSegitoError) as err:
        await manager.async_redeem(kid, reward["id"])
    assert err.value.code == "insufficient_balance"

    await manager.async_adjust(kid, 10, note="bonus")
    tx = await manager.async_redeem(kid, reward["id"])
    assert manager.balances(kid)["wallet"] == 2
    await hass.async_block_till_done()
    assert events[-1].data["event_type"] == "reward_redeemed"
    assert events[-1].data["wallet_balance"] == 2

    reversal = await manager.async_reverse(tx["id"])
    assert manager.balances(kid)["wallet"] == 10
    with pytest.raises(KisSegitoError):
        await manager.async_reverse(tx["id"])
    assert reversal["reverses"] == tx["id"]


async def test_correction_and_history(manager: KisSegitoManager) -> None:
    kid = await _child(manager)
    tx = await manager.async_adjust(kid, 2)
    await manager.async_correct(tx["id"], "wallet", 5)
    assert manager.balances(kid)["wallet"] == 5
    await manager.async_correct(tx["id"], "wallet", 6, note="typo")
    history = manager.history(kid)
    # Corrections are numbered entries of their own, pointing to the original.
    assert [h["seq"] for h in history] == [3, 2, 1]
    assert history[0]["target_seq"] == 1
    assert (history[0]["old_amount"], history[0]["new_amount"]) == (5, 6)
    assert history[0]["note"] == "typo"
    assert history[2]["correction_seqs"] == [2, 3]
    assert history[2]["effective_lines"] == [{"account": "wallet", "amount": 6}]
    # Reversing a corrected transaction cancels the effective amount.
    await manager.async_reverse(tx["id"])
    assert manager.balances(kid)["wallet"] == 0
    history = manager.history(kid)
    assert history[0]["target_seq"] == 1
    assert history[-1]["reversal_seq"] == 4


async def test_piggy(manager: KisSegitoManager) -> None:
    unlock = await manager.async_save_item(
        "rewards", {"name": "Piggy", "cost": 0, "kind": "piggy_unlock"}
    )
    # With an unlock reward a new child's piggy bank starts locked (#11).
    kid = await _child(manager)
    assert manager.child(kid)["piggy_unlocked"] is False
    await manager.async_adjust(kid, 20)
    with pytest.raises(KisSegitoError):
        await manager.async_piggy_transfer(kid, 5)
    await manager.async_redeem(kid, unlock["id"])
    with pytest.raises(KisSegitoError):
        await manager.async_redeem(kid, unlock["id"])
    await manager.async_piggy_transfer(kid, 15)
    assert manager.balances(kid) == {"wallet": 5, "piggy": 15}
    with pytest.raises(KisSegitoError):
        await manager.async_piggy_transfer(kid, -16)
    await manager.async_pay_interest()
    assert manager.balances(kid)["piggy"] == 16  # 10 % of 15, rounded down


async def test_routine_checkpoint_reward_and_device_action(
    hass: HomeAssistant, manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    now = dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)
    freezer.move_to(now)
    kid = await _child(manager)
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Morning",
            "start": "06:30",
            "checkpoints": [
                {
                    "name": "Door",
                    "time": "07:30",
                    "required_for_streak": True,
                    "reward_bands": [
                        {"min_early_min": 20, "tokens": 4},
                        {"min_early_min": 0, "tokens": 2},
                    ],
                }
            ],
            "tasks": [{"icon": "task_clothes"}, {"icon": "task_shoes"}],
        },
    )
    tasks = [t["id"] for t in routine["tasks"]]
    action = {"a": "task", "id": "x1", "c": kid, "r": routine["id"], "t": tasks[0]}
    assert (await manager.async_device_action(action))["ok"]
    assert manager.balances(kid)["wallet"] == 0
    # The same action id again (a retry) changes nothing.
    await manager.async_device_action(action)
    freezer.tick(timedelta(minutes=5))  # 07:05, 25 minutes early
    await manager.async_device_action({**action, "id": "x2", "t": tasks[1]})
    assert manager.balances(kid)["wallet"] == 4

    snap = manager.snapshot("device", "en")
    assert snap["children"][0]["w"] == 4
    assert snap["routines"][0]["done"][kid] == sorted(tasks)
    assert manager.day_success(kid, now.date()) is True

    refused = await manager.async_device_action(
        {"a": "redeem", "id": "x3", "c": kid, "r": "nope"}
    )
    assert refused == {"ok": False, "error": "unknown_reward"}


async def test_device_assignment(manager: KisSegitoManager) -> None:
    a, b = await _child(manager, "A"), await _child(manager, "B")
    assert manager.device_children("knob1") == {a, b}
    await manager.async_assign_device(a, "knob1")
    assert manager.device_children("knob1") == {a}
    assert manager.device_children("knob2") == {a, b}


def test_migrate_schema_1() -> None:
    data = _migrate_config({"settings": {"language": "hu"}, "devices": {"d": {}}})
    assert data["schema"] == 2
    assert data["settings"]["language"] == "hu"
    assert data["settings"]["streak_target"] == 7
    assert data["devices"] == {"d": {}}
    assert data["children"] == []
