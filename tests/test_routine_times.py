# SPDX-License-Identifier: AGPL-3.0-only
"""A routine's checkpoints always lie inside its times."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.kis_segito.manager import KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


async def test_a_checkpoint_after_the_end_moves_the_end(manager: KisSegitoManager) -> None:
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Morning",
            "start": "06:30",
            "end": "09:25",
            "checkpoints": [{"name": "Out", "time": "16:30"}, {"name": "Dressed", "time": "06:00"}],
        },
    )
    assert routine["end"] == "16:30"
    assert routine["start"] == "06:00"


async def test_stored_routines_are_fixed(manager: KisSegitoManager) -> None:
    manager.data["routines"].append(
        {"id": "r1", "name": "Morning", "start": "06:30", "end": "09:25",
         "checkpoints": [{"id": "c1", "name": "Out", "time": "16:30"}], "tasks": []}
    )
    manager.data["overrides"]["2026-11-15"] = {
        "r1": {"routine": {"name": "Morning", "start": "06:30", "end": "09:25",
                           "checkpoints": [{"id": "c1", "time": "16:30"}, {"id": "c2", "time": "08:30"}]}}
    }
    await manager.async_fix_checkpoint_times()
    assert manager.data["routines"][-1]["end"] == "16:30"
    assert manager.data["overrides"]["2026-11-15"]["r1"]["routine"]["end"] == "16:30"
