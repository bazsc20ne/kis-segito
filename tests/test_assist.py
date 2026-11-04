# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the Assist answers about a child."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from custom_components.kis_segito.assist import (
    INTENT_CHILD_STATUS,
    answer,
    async_setup_assist,
    child_status,
    find_child,
)
from custom_components.kis_segito.manager import KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


async def _setup(manager: KisSegitoManager) -> tuple[str, dict]:
    kid = (
        await manager.async_save_item(
            "children", {"name": "Áron", "aliases": "Ari, Bogyó"}
        )
    )["id"]
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
                    "reward_bands": [
                        {"min_early_min": 0, "tokens": 2},
                        {"min_early_min": 15, "tokens": 5},
                    ],
                }
            ],
            "tasks": [
                {"icon": "task_breakfast", "label": "Eat"},
                {"icon": "task_shoes", "label": "Shoes"},
            ],
        },
    )
    await manager.async_adjust(kid, 7)
    return kid, routine


async def test_child_status(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid, routine = await _setup(manager)
    status = child_status(manager, kid)
    assert status["wallet"] == 7
    assert status["task_status"] == "task"
    assert status["current_routine"] == "Morning"
    assert status["current_task"] == "Eat"
    assert status["tasks_left"] == ["Eat", "Shoes"]
    assert status["next_checkpoint"] == "Ready"
    assert status["next_checkpoint_minutes"] == 30
    assert status["tokens_earnable_now"] == 5
    assert status["tokens_earnable_today"] == 5

    await manager.async_complete_task(kid, routine["id"], routine["tasks"][0]["id"])
    assert child_status(manager, kid)["tasks_left"] == ["Shoes"]

    # Later: only the smaller reward is left.
    freezer.move_to(dt_util.now().replace(hour=7, minute=45))
    assert child_status(manager, kid)["tokens_earnable_now"] == 2

    # After the routine: no task, nothing more today.
    freezer.move_to(dt_util.now().replace(hour=9, minute=0))
    status = child_status(manager, kid)
    assert status["task_status"] == "none"
    assert status["current_task"] is None
    assert status["next_checkpoint_minutes"] is None
    assert status["tokens_earnable_today"] == 0


async def test_find_child(manager: KisSegitoManager) -> None:
    kid, _ = await _setup(manager)
    other = (await manager.async_save_item("children", {"name": "Ari Kis"}))["id"]
    assert find_child(manager, "Áron")["id"] == kid
    assert find_child(manager, "aron")["id"] == kid
    # Hungarian case endings and possessives.
    assert find_child(manager, "Áronnak")["id"] == kid
    assert find_child(manager, "Áronnál?")["id"] == kid
    assert find_child(manager, "Bogyónak")["id"] == kid
    assert find_child(manager, "ari kis")["id"] == other
    assert find_child(manager, "Ari")["id"] == kid
    assert find_child(manager, "Nobody") is None


async def test_answers(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid, _ = await _setup(manager)
    status = child_status(manager, kid)
    assert (
        answer(status, "tokens", "en") == "Áron has 7 tokens. The piggy bank holds 0."
    )
    assert "Eat" in answer(status, "task", "en")
    assert "30" in answer(status, "checkpoint", "hu")
    assert answer(status, "earnable", "hu").startswith("Áron ma még 5 zsetont")
    freezer.move_to(dt_util.now().replace(hour=9, minute=0))
    status = child_status(manager, kid)
    assert answer(status, "task", "hu") == "Áron feladata most nincs."
    assert answer(status, "checkpoint", "en") == "Áron has no more checkpoints today."


async def test_intent(
    hass: HomeAssistant, manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    await _setup(manager)
    remove = async_setup_assist(hass, manager)
    response = await intent.async_handle(
        hass,
        "test",
        INTENT_CHILD_STATUS,
        {"name": {"value": "Ari"}, "topic": {"value": "tokens"}},
        language="en",
    )
    assert response.speech["plain"]["speech"].startswith("Áron has 7 tokens.")
    response = await intent.async_handle(
        hass, "test", INTENT_CHILD_STATUS, {"name": {"value": "Xy"}}, language="hu"
    )
    assert "Xy" in response.speech["plain"]["speech"]
    remove()
    assert INTENT_CHILD_STATUS not in {h.intent_type for h in intent.async_get(hass)}


@pytest.mark.parametrize(
    ("language", "sentence", "expected"),
    [
        ("en", "how many tokens does Áron have", "Áron has 7 tokens."),
        ("en", "does Ari have a task now", "Áron is doing Morning now"),
        ("en", "how many coins can aron still get today", "Áron can still earn 5"),
        ("hu", "hány zsetonja van Áronnak", "Áron zsetonjai: 7."),
        ("hu", "van most feladata Áronnak", "Áron most a(z) Morning"),
        ("hu", "mennyi idő van Áron következő checkpointjáig", "30 perc"),
        ("hu", "hány zsetont kaphat még ma Áron", "Áron ma még 5"),
    ],
)
async def test_sentences(
    hass: HomeAssistant,
    manager: KisSegitoManager,
    freezer: FrozenDateTimeFactory,
    language: str,
    sentence: str,
    expected: str,
) -> None:
    from homeassistant.components import conversation
    from homeassistant.setup import async_setup_component

    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    await _setup(manager)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    async_setup_assist(hass, manager)
    await hass.async_block_till_done()
    result = await conversation.async_converse(
        hass, sentence, None, Context(), language
    )
    assert expected in result.response.speech["plain"]["speech"]


async def test_llm_tool(hass: HomeAssistant, manager: KisSegitoManager) -> None:
    from homeassistant.components.homeassistant.exposed_entities import (
        async_expose_entity,
    )
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers import llm
    from homeassistant.setup import async_setup_component

    from custom_components.kis_segito import llm as ks_llm

    assert await async_setup_component(hass, "homeassistant", {})
    async_setup_assist(hass, manager)
    context = llm.LLMContext(
        platform="test",
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )
    assert ks_llm.async_get_tools(hass, context, llm.LLM_API_ASSIST) is None
    entry = er.async_get(hass).async_get_or_create("sensor", "kis_segito", "child_1")
    async_expose_entity(hass, "conversation", entry.entity_id, True)
    tools = ks_llm.async_get_tools(hass, context, llm.LLM_API_ASSIST)
    assert [t.name for t in tools.tools] == ["kis_segito__KisSegitoChildStatus"]
    assert tools.tools[0].annotations.read_only
    assert ks_llm.async_get_tools(hass, context, "other") is None
