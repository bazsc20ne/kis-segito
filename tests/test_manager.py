# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the manager: ledger operations, routines, device actions."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
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
    assert manager.snapshot("knob", "en")["children"][0]["pi"] == 1
    await manager.async_device_action({"a": "seen", "id": "s1", "c": kid})
    assert manager.snapshot("knob", "en")["children"][0]["pi"] == 0


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


def test_migrate_children_background_and_sample_avatars() -> None:
    data = _migrate_config(
        {
            "children": [
                {"id": "a", "avatar": "test_avatar_2", "background": "bg_3"},
                {"id": "b", "avatar": "avatar_05", "background": ""},
                {"id": "c", "avatar": "placeholder_avatar"},
            ]
        }
    )
    assert [c["avatar"] for c in data["children"]] == [
        "avatar_00",
        "avatar_05",
        "avatar_00",
    ]
    assert all("background" not in c for c in data["children"])


async def test_child_background_is_not_stored(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    child = await manager.async_save_item(
        "children", {"name": "A", "color": "#123456", "background": "bg_2"}
    )
    assert "background" not in child
    snapshot = manager.snapshot("knob", "en")
    assert all("bg" not in c for c in snapshot["children"])


async def test_override_and_history_filters(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    kid = await _child(manager, "Anna")
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Evening",
            "start": "19:00",
            "end": "20:00",
            "checkpoints": [{"name": "Bed", "time": "20:00"}],
        },
    )
    day = manager.today()
    await manager.async_set_override(day, routine["id"], shift_min=30, who="Mum")
    shifted = manager.routines_on_day(day)[0]
    assert (shifted["start"], shifted["end"]) == ("19:30", "20:30")
    assert shifted["checkpoints"][0]["time"] == "20:30"
    assert manager.routine(routine["id"])["start"] == "19:00"  # template unchanged
    await manager.async_set_override(day, routine["id"], skip=True)
    assert manager.routines_on_day(day) == []
    assert manager.data["audit"][-1]["what"].startswith("override.")

    await manager.async_adjust(kid, 4, note="garden")
    await manager.async_adjust(kid, 2, account="piggy")
    assert len(manager.history(account="piggy")) == 1
    assert len(manager.history(search="garden")) == 1
    assert len(manager.history(search="anna")) == 2
    assert len(manager.history(search="#1")) == 1
    assert len(manager.history(reasons=["reward_redemption"])) == 0
    assert len(manager.history(date_from="2999-01-01")) == 0


async def test_notification_rules(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    from custom_components.kis_segito.notify import Notifier

    sent: list[ServiceCall] = []

    async def _notify(call: ServiceCall) -> None:
        sent.append(call)

    hass.services.async_register("notify", "parent_phone", _notify)
    manager.notifier = Notifier(
        hass, lambda: manager.data["notifications"], lambda: "hu"
    )
    kid = await _child(manager, "Anna")
    other = await _child(manager, "Bence")
    await manager.async_save_notifications(
        [
            {
                "name": "Phone",
                "service": "notify.parent_phone",
                "events": ["manual_adjustment"],
                "children": [kid],
                "enabled": True,
            }
        ]
    )
    await manager.async_adjust(kid, 3)
    await manager.async_adjust(other, 3)  # other child: no notification
    await hass.async_block_till_done()
    assert len(sent) == 1
    assert sent[0].data["message"].startswith("Anna: +3")


async def test_old_correction_amounts_from_ledger(manager: KisSegitoManager) -> None:
    kid = await _child(manager)
    tx = await manager.async_adjust(kid, 1)
    correction = await manager.async_correct(tx["id"], "wallet", 2)
    # Corrections from before 0.3.1 did not store old/new amounts (#14).
    del correction["old_amount"], correction["new_amount"]
    entry = manager.history(kid)[0]
    assert (entry["old_amount"], entry["new_amount"]) == (1, 2)


async def test_day_templates(manager: KisSegitoManager) -> None:
    school = await manager.async_save_item(
        "routines", {"name": "School morning", "start": "07:00", "end": "07:45"}
    )
    free = await manager.async_save_item(
        "routines", {"name": "Free morning", "start": "08:30", "end": "09:30"}
    )
    weekday = await manager.async_save_item(
        "templates", {"name": "Weekday", "routines": [school["id"]]}
    )
    holiday = await manager.async_save_item(
        "templates", {"name": "Holiday", "routines": [free["id"]]}
    )
    day = manager.today()
    # Without templates both routines follow their own (all) weekdays.
    assert len(manager.routines_on_day(day)) == 2
    await manager.async_set_day_template(
        weekday=day.weekday(), template_id=weekday["id"]
    )
    assert [r["name"] for r in manager.routines_on_day(day)] == ["School morning"]
    await manager.async_set_day_template(day=day, template_id=holiday["id"])
    assert [r["name"] for r in manager.routines_on_day(day)] == ["Free morning"]
    await manager.async_set_day_template(day=day, template_id=None)
    assert manager.template_for_day(day)["name"] == "Weekday"
    with pytest.raises(KisSegitoError):
        await manager.async_set_day_template(day=day, template_id="nope")


async def test_script_notification_rule(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    from custom_components.kis_segito.notify import Notifier, rule_call

    rule = {
        "service": "script.send_imessage",
        "message_field": "text",
        "title_field": "",
        "extra": {"recipient": "parent", "empty": ""},
    }
    assert rule_call(rule, "Title", "Hello") == (
        "script",
        "send_imessage",
        {"recipient": "parent", "text": "Hello"},
    )
    calls: list[ServiceCall] = []

    async def _script(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("script", "send_imessage", _script)
    notifier = Notifier(hass, lambda: [], lambda: "en")
    await notifier.async_test(rule)
    assert calls[0].data["text"].startswith("Test message")


async def test_day_routine_edits(manager: KisSegitoManager) -> None:
    from datetime import timedelta

    kid = await _child(manager)
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Evening",
            "start": "19:00",
            "end": "20:00",
            "checkpoints": [{"name": "Bed", "time": "20:00"}],
            "tasks": [{"icon": "task_bath"}],
        },
    )
    day = manager.today()
    edited = dict(routine) | {"start": "18:30", "tasks": [{"icon": "task_story"}]}
    await manager.async_set_day_routine(day, routine["id"], edited)
    today = manager.routine_for_day(routine["id"], day)
    assert today["start"] == "18:30"
    assert today["tasks"][0]["icon"] == "task_story"
    assert manager.routine(routine["id"])["start"] == "19:00"  # source unchanged
    # A quick shift keeps the day's copy.
    await manager.async_set_override(day, routine["id"], shift_min=10)
    assert manager.routine_for_day(routine["id"], day)["start"] == "18:40"
    # Tasks of the day's copy can be completed.
    task_id = manager.routine_for_day(routine["id"], day)["tasks"][0]["id"]
    await manager.async_complete_task(kid, routine["id"], task_id)
    # Restore: back to the routine (the shift stays until removed).
    await manager.async_set_day_routine(day, routine["id"], None)
    assert manager.routine_for_day(routine["id"], day)["start"] == "19:10"

    one_day = await manager.async_set_day_routine(
        day + timedelta(days=1),
        None,
        {"name": "Party", "start": "16:00", "end": "18:00"},
    )
    tomorrow = manager.routines_on_day(day + timedelta(days=1))
    assert any(r["id"] == one_day and r["one_day"] for r in tomorrow)
    await manager.async_set_day_routine(day + timedelta(days=1), one_day, None)
    assert not any(
        r["id"] == one_day for r in manager.routines_on_day(day + timedelta(days=1))
    )
    with pytest.raises(KisSegitoError) as err:
        await manager.async_set_day_routine(
            day - timedelta(days=1), routine["id"], edited
        )
    assert err.value.code == "past_day"


async def test_processed_action_ids_are_bounded(
    manager: KisSegitoManager, monkeypatch
) -> None:
    from custom_components.kis_segito import manager as manager_module

    monkeypatch.setattr(manager_module, "ACTION_KEPT", 3)
    for i in range(5):
        await manager.async_device_action({"a": "nothing", "id": f"id{i}"})
    assert list(manager.store.ledger["actions"]) == ["id2", "id3", "id4"]


async def test_routine_template_round_trip(
    hass: HomeAssistant, manager: KisSegitoManager
) -> None:
    template = await manager.async_save_item(
        "routine_templates",
        {"name": "Our morning", "routine": {"name": "Morning", "tasks": []}},
    )
    assert manager.data["routine_templates"] == [template]
    await manager.async_delete_item("routine_templates", template["id"])
    assert manager.data["routine_templates"] == []
