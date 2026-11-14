# SPDX-License-Identifier: AGPL-3.0-only
"""Assist: first person, follow-ups, every child at once, what is left,
the next routine, a checkpoint's tasks, and sentences that never overlap."""

from __future__ import annotations

import random
import sys
import types
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito import assist_lang
from custom_components.kis_segito.assist import (
    INTENT_CHILD_STATUS,
    async_setup_assist,
    checkpoint_tasks,
)
from custom_components.kis_segito.assist_sentences import (
    all_sentences,
    checkpoint_sentences,
    child_sentences,
    followup_sentences,
    routine_sentences,
    speaker_sentences,
)
from custom_components.kis_segito.manager import KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


async def _setup(manager: KisSegitoManager) -> dict[str, str]:
    kid_a = (await manager.async_save_item("children", {"name": "Áron", "aliases": "Ari"}))["id"]
    kid_b = (await manager.async_save_item("children", {"name": "Emese"}))["id"]
    await manager.async_save_item(
        "routines",
        {
            "name": "Esti rutin",
            "start": "19:00",
            "end": "20:30",
            "checkpoints": [
                {
                    "name": "vacsora",
                    "time": "19:45",
                    "reward_bands": [{"min_early_min": 0, "tokens": 2}],
                },
                {
                    "name": "lefekvés",
                    "time": "20:30",
                    "reward_bands": [{"min_early_min": 0, "tokens": 1}],
                },
            ],
            "tasks": [
                {"icon": "task_tidy", "label": "játékok elpakolása"},
                {"icon": "task_dinner", "label": "vacsora"},
                {"icon": "task_teeth", "label": "fogmosás"},
                {"icon": "task_pyjamas", "label": "pizsama"},
            ],
        },
    )
    await manager.async_save_item(
        "routines",
        {"name": "Reggel", "start": "07:00", "end": "08:00", "tasks": []},
    )
    # The first two tasks lead to the dinner checkpoint.
    routine = next(r for r in manager.data["routines"] if r["name"] == "Esti rutin")
    first = routine["checkpoints"][0]["id"]
    for task in routine["tasks"][:2]:
        task["checkpoint_id"] = first
    await manager.async_adjust(kid_a, 5)
    await manager.async_adjust(kid_b, 2)
    return {"a": kid_a, "b": kid_b}


@pytest.fixture
async def assist(
    hass: HomeAssistant, manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> dict[str, str]:
    from homeassistant.setup import async_setup_component

    freezer.move_to(dt_util.now().replace(hour=19, minute=21, second=0, microsecond=0))
    kids = await _setup(manager)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    async_setup_assist(hass, manager)
    await hass.async_block_till_done()
    return kids


async def _ask(hass: HomeAssistant, text: str, language: str = "hu", **kwargs: Any) -> str:
    from homeassistant.components import conversation

    result = await conversation.async_converse(
        hass, text, kwargs.pop("conversation_id", None), Context(), language, **kwargs
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE, text
    return result.response.speech["plain"]["speech"]


def _satellite(hass: HomeAssistant, area: str | None = None) -> str:
    entry = MockConfigEntry(domain="esphome")
    entry.add_to_hass(hass)
    area_id = ar.async_get(hass).async_get_or_create(area).id if area else None
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, f"00:00:00:00:00:{len(hass.data) % 99:02d}")},
    )
    if area_id:
        dr.async_get(hass).async_update_device(device.id, area_id=area_id)
    return device.id


# ---------------------------------------------------------------- first person


async def test_first_person_without_an_assignment_answers_for_every_child(
    hass: HomeAssistant, assist: dict[str, str]
) -> None:
    speech = await _ask(hass, "mennyi zsetonom van")
    assert "Áron" in speech and "Emes" in speech


async def test_a_satellite_with_one_child(
    hass: HomeAssistant, manager: KisSegitoManager, assist: dict[str, str]
) -> None:
    device_id = _satellite(hass)
    manager.settings["assist_speakers"] = [{"device_id": device_id, "children": [assist["b"]]}]
    speech = await _ask(hass, "nekem mennyi zsetonom van", device_id=device_id)
    assert "két" in speech and "Áron" not in speech
    speech = await _ask(hass, "what's my next task", "en", device_id=device_id)
    assert "játékok elpakolása" in speech and "Áron" not in speech


async def test_a_satellite_by_area_with_several_children(
    hass: HomeAssistant, manager: KisSegitoManager, assist: dict[str, str]
) -> None:
    device_id = _satellite(hass, "Kids room")
    area_id = dr.async_get(hass).async_get(device_id).area_id
    manager.settings["assist_speakers"] = [
        {"area_id": area_id, "children": [assist["a"], assist["b"]]}
    ]
    speech = await _ask(hass, "mennyi zsetonom van", device_id=device_id)
    # Never one guessed: both, largest first.
    assert speech.index("Áron") < speech.index("Emes")


async def test_speaker_recognition_is_used_when_installed(
    hass: HomeAssistant, manager: KisSegitoManager, assist: dict[str, str]
) -> None:
    heard: dict[str, Any] = {"name": None}

    async def async_get_turn_result(hass: HomeAssistant, conversation_id: str, timeout: float) -> Any:
        assert conversation_id == "conv-1"
        return {"name": heard["name"], "verified": heard["name"] is not None, "score": 0.9}

    module = types.ModuleType("custom_components.voice_test")
    module.async_get_turn_result = async_get_turn_result
    sys.modules[module.__name__] = module
    hass.config.components.add("voice_test")
    try:
        heard["name"] = "Ari"
        speech = await _ask(hass, "mennyi zsetonom van", conversation_id="conv-1")
        assert "öt" in speech and "Emese" not in speech
        # Not recognised: ask who it is; the name then answers the question.
        heard["name"] = None
        speech = await _ask(hass, "mi a következő feladatom", conversation_id="conv-1")
        assert "elpakolás" not in speech
        speech = await _ask(hass, "Emese vagyok", conversation_id="conv-1")
        assert "játékok elpakolása" in speech
    finally:
        del sys.modules[module.__name__]
        hass.config.components.remove("voice_test")


# ---------------------------------------------------------------- follow-ups


async def test_follow_ups_reuse_the_topic(
    hass: HomeAssistant, assist: dict[str, str], freezer: FrozenDateTimeFactory
) -> None:
    await _ask(hass, "mikor van Áron következő ellenőrzőpontja")
    speech = await _ask(hass, "és Emesének?")
    assert "Emes" in speech and "vacsora" in speech
    speech = await _ask(hass, "and the kids", "en")
    assert "dinner" not in speech and "vacsora" in speech
    # After a minute a follow-up has nothing to refer to.
    freezer.tick(90)
    speech = await _ask(hass, "és Emesének?")
    assert "zseton" in speech or "feladat" in speech
    # "How many" without a question before: tokens.
    freezer.tick(90)
    speech = await _ask(hass, "és Emesének mennyi?")
    assert "két zseton" in speech


# ---------------------------------------------------------------- new topics


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        ("hu", "mi van még hátra Áronnak", ["fogmosás", "pizsama"]),
        ("hu", "hogy állnak a gyerekek a mai feladatokkal", ["fogmosás"]),
        ("en", "what's left for Áron today", ["Áron", "pizsama"]),
        ("hu", "mikor kezdődik Áron következő rutinja", ["nincs több rutin"]),
        ("hu", "milyen lépések vannak a vacsorában", ["a játékok elpakolása", "a vacsora"]),
        ("en", "what are the steps of vacsora", ["játékok elpakolása"]),
    ],
)
async def test_new_topics(
    hass: HomeAssistant,
    assist: dict[str, str],
    language: str,
    text: str,
    expected: list[str],
) -> None:
    speech = await _ask(hass, text, language)
    for part in expected:
        assert part in speech, speech


async def test_next_routine(
    hass: HomeAssistant, manager: KisSegitoManager, freezer: FrozenDateTimeFactory
) -> None:
    from homeassistant.setup import async_setup_component

    freezer.move_to(dt_util.now().replace(hour=6, minute=30, second=0, microsecond=0))
    await _setup(manager)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    async_setup_assist(hass, manager)
    await hass.async_block_till_done()
    speech = await _ask(hass, "mikor indul a következő rutin")
    assert "reggel hét órakor" in speech or "fél óra múlva" in speech.casefold()
    speech = await _ask(hass, "when does the next routine start", "en")
    assert "Reggel" in speech


async def test_checkpoint_tasks(manager: KisSegitoManager) -> None:
    await _setup(manager)
    assert checkpoint_tasks(manager, "Vacsora") == ["játékok elpakolása", "vacsora"]
    assert checkpoint_tasks(manager, "lefekvés") == ["fogmosás", "pizsama"]
    assert checkpoint_tasks(manager, "nincs ilyen") == []


# ---------------------------------------------------------------- answers


async def test_a_wording_is_not_used_twice_in_a_row() -> None:
    last = None
    for _ in range(30):
        text = assist_lang.say("hu", "system", "no_previous_topic")
        assert text != last
        last = text


async def test_zero_has_its_own_wording(
    hass: HomeAssistant, manager: KisSegitoManager, assist: dict[str, str]
) -> None:
    await manager.async_adjust(assist["b"], -2)
    for _ in range(10):
        speech = await _ask(hass, "mennyi zsetonja van Emesének")
        assert "nulla" not in speech


async def test_llm_first_person(
    hass: HomeAssistant, manager: KisSegitoManager, assist: dict[str, str]
) -> None:
    device_id = _satellite(hass)
    manager.settings["assist_speakers"] = [{"device_id": device_id, "children": [assist["a"]]}]
    response = await intent.async_handle(
        hass,
        "test",
        INTENT_CHILD_STATUS,
        {"speaker": {"value": True}, "topic": {"value": "checkpoint"}},
        language="hu",
        device_id=device_id,
    )
    assert response.speech_slots["name"] == "Áron"
    assert response.speech_slots["next_checkpoint_time_spoken"] == "este háromnegyed nyolckor"


async def test_deleting_a_child_removes_it_from_the_satellites(
    manager: KisSegitoManager,
) -> None:
    kids = await _setup(manager)
    manager.settings["assist_speakers"] = [{"device_id": "x", "children": [kids["a"], kids["b"]]}]
    await manager.async_delete_item("children", kids["a"])
    assert manager.settings["assist_speakers"][0]["children"] == [kids["b"]]


# ---------------------------------------------------------------- sentences


def _sample(expression: Any, rnd: random.Random) -> str:
    from hassil.expression import Alternative, Permutation, Sequence, TextChunk

    if isinstance(expression, TextChunk):
        return expression.text
    if isinstance(expression, Permutation):
        items = list(expression.items)
        rnd.shuffle(items)
        return " ".join(_sample(i, rnd) for i in items)
    if isinstance(expression, Alternative):
        return _sample(rnd.choice(expression.items), rnd)
    if isinstance(expression, Sequence):
        return "".join(_sample(i, rnd) for i in expression.items)
    return ""


@pytest.mark.parametrize("language", ["hu", "en"])
def test_sentences_never_overlap(language: str) -> None:
    """A sentence of one topic never also matches another topic: every
    question gets exactly one answer."""
    from hassil import Intents, recognize_all
    from hassil.parse_expression import parse_sentence

    groups: dict[str, list[str]] = {}
    for name, names in (("Áron", ["Áron", "Ari"]), ("Emese", ["Emese"])):
        for topic, items in child_sentences(names, language).items():
            groups[f"child.{topic}.{name}"] = items
        for kind, items in followup_sentences(language, names).items():
            groups[f"followup.{kind}.{name}"] = items
    for scope, build in (("all", all_sentences), ("speaker", speaker_sentences)):
        for topic, items in build(language).items():
            groups[f"{scope}.{topic}"] = items
    for kind, items in followup_sentences(language).items():
        groups[f"followup.{kind}"] = items
    for routine in ("Esti rutin", "Reggel"):
        for items in routine_sentences([routine], language).values():
            groups[f"routine.{routine}"] = items
    for cp in ("vacsora", "lefekvés"):
        for items in checkpoint_sentences([cp], language).values():
            groups[f"checkpoint.{cp}"] = items
    intents = Intents.from_dict(
        {
            "language": language,
            "intents": {k: {"data": [{"sentences": v}]} for k, v in groups.items()},
        }
    )
    rnd = random.Random(7)
    overlaps = []
    for name, items in groups.items():
        for template in items:
            expression = parse_sentence(template).expression
            for _ in range(6):
                text = " ".join(_sample(expression, rnd).split())
                matched = {r.intent.name for r in recognize_all(text, intents)}
                if matched - {name}:
                    overlaps.append((text, name, sorted(matched - {name})))
    assert not overlaps, overlaps[:5]


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("hu", "Őőő mennyi zsetonja van Áronnak"),
        ("hu", "Hé, mi a következő feladat a gyerekeknek?"),
        ("hu", "Mennyi idő van a gyerekeknek a következő ellenőrző pontig?"),
        ("hu", "Hány zsetont kaphatok még ma?"),
        ("hu", "Hogy állok?"),
        ("hu", "Mennyi zseton van a perselyekben?"),
        ("en", "um how many tokens do I have"),
        ("en", "How much time do I have left?"),
        ("en", "How are the kids doing with their tasks?"),
    ],
)
async def test_written_questions(
    hass: HomeAssistant, assist: dict[str, str], language: str, text: str
) -> None:
    assert await _ask(hass, text, language)
