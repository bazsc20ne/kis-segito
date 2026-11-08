# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for corrections of entries without tokens, and for import."""

from __future__ import annotations

import copy
import json

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.kis_segito.manager import KisSegitoError, KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


async def _setup(manager: KisSegitoManager) -> tuple[str, dict]:
    kid = (await manager.async_save_item("children", {"name": "Kid A"}))["id"]
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Morning",
            "start": "07:00",
            "end": "08:00",
            "checkpoints": [
                {"name": "Ready", "time": "07:50",
                 "reward_bands": [{"min_early_min": 0, "tokens": 3}, {"min_early_min": 20, "tokens": 5}]}
            ],
            "tasks": [{"icon": "task_shoes", "label": "Shoes"}],
        },
    )
    return kid, routine


def _events(manager: KisSegitoManager, kind: str) -> list[dict]:
    return [e for e in manager.event_list() if e["type"] == kind]


async def test_remove_a_task(manager: KisSegitoManager, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=55, second=0, microsecond=0))
    kid, routine = await _setup(manager)
    task = routine["tasks"][0]["id"]
    await manager.async_complete_task(kid, routine["id"], task)
    event = _events(manager, "task_done")[0]
    await manager.async_remove_event(event["id"], who="Parent")
    assert task not in manager.progress(manager.today(), routine["id"], kid)["tasks"]
    assert _events(manager, "task_removed")[0]["removes"] == event["id"]
    with pytest.raises(KisSegitoError):
        await manager.async_remove_event(event["id"])


async def test_remove_a_paid_checkpoint(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=40, second=0, microsecond=0))
    kid, routine = await _setup(manager)
    await manager.async_complete_task(kid, routine["id"], routine["tasks"][0]["id"])
    assert manager.balances(kid)["wallet"] == 3
    event = next(e for e in manager.events if e["type"] == "checkpoint_done")
    await manager.async_remove_event(event["id"])
    assert manager.balances(kid)["wallet"] == 0
    cp = routine["checkpoints"][0]["id"]
    assert cp not in manager.progress(manager.today(), routine["id"], kid)["checkpoints"]


async def test_give_tokens_for_a_late_checkpoint(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=55, second=0, microsecond=0))
    kid, routine = await _setup(manager)
    await manager.async_complete_task(kid, routine["id"], routine["tasks"][0]["id"])
    assert manager.balances(kid)["wallet"] == 0
    event = _events(manager, "checkpoint_done")[0]
    assert event["credit_suggestion"] == 5
    tx = await manager.async_credit_event(event["id"], 4)
    assert manager.balances(kid)["wallet"] == 4
    assert tx["refs"]["event_id"] == event["id"]
    assert "credit_suggestion" not in _events(manager, "checkpoint_done")[0]
    # A normal entry: it can be reversed in the history.
    await manager.async_reverse(tx["id"])
    assert manager.balances(kid)["wallet"] == 0


async def test_import_replaces_everything(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=40, second=0, microsecond=0))
    kid, routine = await _setup(manager)
    await manager.async_complete_task(kid, routine["id"], routine["tasks"][0]["id"])
    document = manager.export("test")

    saved = json.loads(json.dumps(document))
    await manager.async_adjust(kid, 10)
    await manager.async_save_item("children", {"name": "Kid B"})
    await manager.async_import(saved)
    assert [c["name"] for c in manager.children()] == ["Kid A"]
    assert manager.balances(kid)["wallet"] == 3
    assert len(manager.events) == len(saved["events"])
    for bad in ({}, {"kis_segito_export": 2, "config": {}, "ledger": [{"id": 1}]}, "x"):
        with pytest.raises(KisSegitoError):
            await manager.async_import(copy.deepcopy(bad))
    assert manager.balances(kid)["wallet"] == 3
