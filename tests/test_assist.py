# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the Assist answers about a child."""

from __future__ import annotations

import re

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from custom_components.kis_segito.assist import (
    INTENT_CHILD_STATUS,
    TOPICS,
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


@pytest.mark.parametrize("language", ["en", "hu", "de"])
@pytest.mark.parametrize("hour", [7, 9])
async def test_answers_are_spoken_words(
    manager: KisSegitoManager,
    freezer: FrozenDateTimeFactory,
    language: str,
    hour: int,
) -> None:
    """Numbers and times are words, without symbols, in every wording."""
    freezer.move_to(
        dt_util.now().replace(hour=hour, minute=20, second=0, microsecond=0)
    )
    kid, _ = await _setup(manager)
    await manager.async_save_item("children", {"id": kid, "piggy_unlocked": True})
    status = child_status(manager, kid)
    for _ in range(20):
        for topic in TOPICS:
            text = answer(status, topic, language)
            assert text
            assert not re.search(r"[0-9%/:]", text), text


async def test_answers(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid, _ = await _setup(manager)
    status = child_status(manager, kid)
    assert "seven tokens" in answer(status, "tokens", "en")
    assert "hét zseton" in answer(status, "tokens", "hu")
    assert "Eat" in answer(status, "task", "en")
    assert "még két feladat van hátra" in answer(status, "task", "hu")
    text = answer(status, "checkpoint", "hu").casefold()
    assert "fél óra múlva" in text
    assert "reggel hét óra ötven perckor" in text
    assert "at seven fifty in the morning" in answer(status, "checkpoint", "en")
    assert answer(status, "earnable", "hu").startswith(
        ("Áron ma még öt", "Áronnak ma még öt")
    )
    assert answer(status, "streak", "en").startswith("Áron has no streak")
    freezer.move_to(dt_util.now().replace(hour=9, minute=0))
    status = child_status(manager, kid)
    assert answer(status, "task", "hu").startswith("Áronnak most nincs")
    assert answer(status, "checkpoint", "en") == "Áron has no more checkpoints today."
    # Other languages are answered in English.
    assert answer(status, "checkpoint", "fr") == "Áron has no more checkpoints today."


async def test_intent(
    hass: HomeAssistant, manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    await _setup(manager)
    await manager.async_save_item("children", {"name": "Alex"})
    remove = async_setup_assist(hass, manager)
    response = await intent.async_handle(
        hass,
        "test",
        INTENT_CHILD_STATUS,
        {"name": {"value": "Ari"}, "topic": {"value": "tokens"}},
        language="en",
    )
    assert response.speech["plain"]["speech"].startswith("Áron has seven tokens")
    assert response.speech_slots["wallet"] == 7
    assert response.speech_slots["aliases"] == ["Ari", "Bogyó"]
    assert response.speech_slots["next_checkpoint_minutes"] == 30
    # Without a name: every child.
    response = await intent.async_handle(
        hass, "test", INTENT_CHILD_STATUS, {"topic": {"value": "tokens"}}, language="en"
    )
    speech = response.speech["plain"]["speech"]
    assert "Áron" in speech and "Alex" in speech
    assert [c["name"] for c in response.speech_slots["children"]] == ["Áron", "Alex"]
    response = await intent.async_handle(
        hass, "test", INTENT_CHILD_STATUS, {"name": {"value": "Xy"}}, language="hu"
    )
    assert "Xy" in response.speech["plain"]["speech"]
    remove()
    assert INTENT_CHILD_STATUS not in {h.intent_type for h in intent.async_get(hass)}


async def _converse(hass: HomeAssistant, sentence: str, language: str) -> str:
    from homeassistant.components import conversation

    result = await conversation.async_converse(
        hass, sentence, None, Context(), language
    )
    return result.response.speech.get("plain", {}).get("speech", "")


@pytest.fixture
async def assist(
    hass: HomeAssistant, manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> KisSegitoManager:
    from homeassistant.setup import async_setup_component

    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    await _setup(manager)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    async_setup_assist(hass, manager)
    await hass.async_block_till_done()
    return manager


@pytest.mark.parametrize(
    ("language", "sentence", "expected"),
    [
        ("en", "how many tokens does Áron have", "Áron has seven tokens"),
        ("en", "How many coins has aron got?", "seven tokens"),
        ("en", "what's Ari's balance", "seven tokens"),
        ("en", "does Ari have a task now", "two tasks to go"),
        ("en", "when is Bogyó's next checkpoint", "half an hour"),
        ("en", "how many coins can aron still get today", "Áron can still earn five"),
        ("en", "what is Áron's streak", "no streak"),
        ("hu", "hány zsetonja van Áronnak", "hét zseton"),
        ("hu", "Áronnak mennyi zsetonja van?", "hét zseton"),
        ("hu", "mennyei zsetonja van aronnak", "hét zseton"),
        ("hu", "hány jetonja van Bogyónak", "hét zseton"),
        ("hu", "mennyi pénze van Arinak", "hét zseton"),
        ("hu", "Áron egyenlege", "hét zseton"),
        ("hu", "van most feladata Áronnak", "Morning"),
        ("hu", "mi Áron feladata most", "Morning"),
        ("hu", "mit kell most csinálnia Arinak", "Morning"),
        ("hu", "mennyi idő van Áron következő ellenőrzőpontjáig", "fél óra"),
        ("hu", "mikor van Áron következő csekkpontja", "fél óra"),
        ("hu", "mikor jön Áronnak a következő check pontja", "fél óra"),
        ("hu", "hány zsetont kaphat még ma Áron", "öt zseton"),
        ("hu", "Áron hány zsetont szerezhet még", "öt zseton"),
        ("hu", "hány napos Áron sorozata", "sorozata"),
        ("hu", "hány napja hibátlan Áron", "sorozata"),
    ],
)
async def test_sentences(
    hass: HomeAssistant,
    assist: KisSegitoManager,
    language: str,
    sentence: str,
    expected: str,
) -> None:
    speech = await _converse(hass, sentence, language)
    assert expected.casefold() in speech.casefold()


@pytest.mark.parametrize(
    ("language", "sentence"),
    [
        ("hu", "kinek mennyi zsetonja van"),
        ("hu", "mennyi zseton van a gyerekeknek"),
        ("hu", "mikor van a következő ellenőrzőpont"),
        ("en", "how many tokens do the kids have"),
        ("en", "when is the next checkpoint"),
    ],
)
async def test_sentences_without_a_name(
    hass: HomeAssistant, assist: KisSegitoManager, language: str, sentence: str
) -> None:
    await assist.async_save_item("children", {"name": "Alex"})
    await hass.async_block_till_done()
    speech = await _converse(hass, sentence, language)
    assert "Áron" in speech and "Alex" in speech


async def test_unknown_name_is_not_answered(
    hass: HomeAssistant, assist: KisSegitoManager
) -> None:
    """A name Kis Segítő does not know is left to the other agents."""
    speech = await _converse(hass, "hány zsetonja van Zénónak", "hu")
    assert "zseton" not in speech
    assert "Áron" not in speech


async def test_sentences_follow_name_changes(
    hass: HomeAssistant, assist: KisSegitoManager
) -> None:
    kid = assist.children()[0]["id"]
    await assist.async_save_item("children", {"id": kid, "aliases": "Kid A"})
    await hass.async_block_till_done()
    assert "seven tokens" in await _converse(
        hass, "how many tokens does Kid A have", "en"
    )
    assert "seven tokens" not in await _converse(
        hass, "how many tokens does Bogyó have", "en"
    )


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


async def test_child_sensor_is_shared_with_assist_once(hass: HomeAssistant) -> None:
    from homeassistant.components.homeassistant.exposed_entities import (
        async_expose_entity,
        async_should_expose,
    )
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from homeassistant.setup import async_setup_component
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN

    assert await async_setup_component(hass, "homeassistant", {})
    esphome_entry = MockConfigEntry(domain="esphome", data={"host": "192.0.2.1"})
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:09")},
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager
    kid = (await manager.async_save_item("children", {"name": "Kid A"}))["id"]
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_child_{kid}"
    )
    assert entity_id
    assert async_should_expose(hass, "conversation", entity_id)

    # Turned off by the user: stays off after a reload.
    async_expose_entity(hass, "conversation", entity_id, False)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert not async_should_expose(hass, "conversation", entity_id)


DOCUMENTED = {
    "hu": [
        "hány zsetonja van Alexnek",
        "mennyi zsetonja van Alexnek",
        "Alexnek hány zsetonja van",
        "mennyi pénze van Alexnek",
        "mennyi pontja van Alexnek",
        "mennyi érméje van Alexnek",
        "Alex egyenlege",
        "van még zsetonja Alexnek",
        "kinek mennyi zsetonja van",
        "mennyi zseton van a gyerekeknek",
        "hogy állnak a gyerekek",
        "kinek mennyi van",
        "van most feladata Alexnek",
        "mi Alex feladata most",
        "mi a feladata Alexnek",
        "mit kell most csinálnia Alexnek",
        "mivel tart most Alex",
        "kinek van most feladata",
        "mik a feladatok most",
        "mikor van Alex következő ellenőrzőpontja",
        "mikor jön Alexnek a következő ellenőrzőpontja",
        "mennyi idő van még Alex következő ellenőrzőpontjáig",
        "meddig van még ideje Alexnek",
        "mikor van a következő ellenőrzőpont",
        "mennyi idő van még a következő ellenőrzőpontig",
        "hány zsetont kaphat még ma Alex",
        "hány zsetont szerezhet még ma Alex",
        "Alex mennyit kaphat még ma",
        "hány zsetont kaphatnak még ma a gyerekek",
        "ki hány zsetont kaphat még ma",
        "hány napos Alex sorozata",
        "hány napja hibátlan Alex",
        "hogy áll Alex sorozata",
        "milyen hosszú a sorozat",
        "hogy állnak a sorozatok",
        "mikor van Alex következő checkpointja",
        "mikor van Alex következő határideje",
        "hány tallérja van Alexnek",
        "mi Alex teendője most",
        "mi a dolga most Alexnek",
        "mi a dolga Alexnek",
        "mi a teendője most Alexnek",
        "mi most a dolga Alexnek",
        "Alexnek mi a dolga most",
        "mi következik Alexnél",
        "mi jön most Alexnek",
        "mi a következő feladata Alexnek",
        "Alexé mennyi zsetonja van",
        "mennyi zsetonja van Alexnél",
    ],
    "en": [
        "how many tokens does Alex have",
        "how many coins does Alex have",
        "how many points does Alex have",
        "how many coins has Alex got",
        "what's Alex's balance",
        "Alex's wallet",
        "how many tokens do the kids have",
        "who has how many coins",
        "how are the kids doing",
        "does Alex have a task now",
        "what's Alex's task",
        "what should Alex be doing now",
        "what is Alex doing now",
        "does anyone have a task now",
        "who has something to do now",
        "when is Alex's next checkpoint",
        "how long until Alex's next checkpoint",
        "how much time does Alex have left",
        "when is the next checkpoint",
        "how long until the next checkpoint",
        "how many tokens can Alex still earn today",
        "how much can Alex still get",
        "how many tokens can the kids still earn today",
        "what is Alex's streak",
        "how many perfect days does Alex have",
        "What does Alex have to do now?",
        "what does Alex have to do",
        "What's next for Alex?",
        "what are the streaks",
        "how are the streaks going",
    ],
}


@pytest.mark.parametrize(
    ("language", "sentence"),
    [(lang, s) for lang, sentences in DOCUMENTED.items() for s in sentences],
)
async def test_documented_sentences(
    hass: HomeAssistant, assist: KisSegitoManager, language: str, sentence: str
) -> None:
    await assist.async_save_item("children", {"name": "Alex"})
    await hass.async_block_till_done()
    speech = await _converse(hass, sentence, language)
    assert "Alex" in speech, speech


def test_times_say_the_part_of_the_day() -> None:
    from datetime import datetime

    from custom_components.kis_segito.assist_words import en_clock, hu_clock

    def at(h: int, m: int = 0) -> datetime:
        return datetime(2026, 1, 1, h, m)  # noqa: DTZ001 - a clock time only

    assert hu_clock(at(19)) == "este hét órakor"
    assert hu_clock(at(7, 30)) == "reggel fél nyolckor"
    assert hu_clock(at(15, 15)) == "délután negyed négykor"
    assert hu_clock(at(10, 5)) == "délelőtt tíz óra öt perckor"
    assert hu_clock(at(12)) == "délben"
    assert en_clock(at(19)) == "at seven in the evening"
    assert en_clock(at(7, 30)) == "at half past seven in the morning"
    assert en_clock(at(11, 45)) == "at quarter to twelve in the afternoon"
    assert en_clock(at(12)) == "at noon"


async def test_english_streak_says_days_once(manager: KisSegitoManager) -> None:
    kid, _ = await _setup(manager)
    status = child_status(manager, kid) | {"streak": 2, "streak_target": 7}
    for _ in range(10):
        text = answer(status, "streak", "en")
        assert "out of seven days" not in text, text


@pytest.mark.parametrize(
    ("language", "sentence", "expected"),
    [
        ("hu", "mennyi van még hátra a Morning rutinból", "két feladat"),
        ("hu", "hány feladat van még hátra a Morning rutinból", "a Morning rutinból"),
        ("en", "how many tasks are left in Morning", "Áron has two tasks left in Morning."),
    ],
)
async def test_routine_questions(
    hass: HomeAssistant, assist: KisSegitoManager, language: str, sentence: str, expected: str
) -> None:
    speech = await _converse(hass, sentence, language)
    assert expected in speech, speech


async def test_routine_name_is_not_doubled(
    manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    """A routine called "... rutin" is not said as "rutin rutin"."""
    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid, routine = await _setup(manager)
    await manager.async_save_item("routines", {"id": routine["id"], "name": "Esti rutin"})
    status = child_status(manager, kid)
    for _ in range(20):
        text = answer(status, "task", "hu")
        assert "rutin rutin" not in text and "Esti rutin" in text, text


def test_a_language_needs_only_files() -> None:
    """A language without its own grammar still answers, with digits."""
    from custom_components.kis_segito import assist_lang

    assist_lang._texts["xx"] = {"answers": {"tokens": {"some": ["{name}: {wallet:num}"]}}}
    try:
        assert assist_lang.say("xx", "tokens", "some", name="Kid A", wallet=7) == "Kid A: 7"
        # Missing texts fall back to English.
        assert assist_lang.say("xx", "tokens", "none", name="Kid A") == "Kid A has no tokens right now."
    finally:
        del assist_lang._texts["xx"]
