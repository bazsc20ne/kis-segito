# SPDX-License-Identifier: AGPL-3.0-only
"""Answers for Home Assistant's assistants (Assist), read only.

Per child: tokens (wallet, piggy bank), the task right now, the time until the
next checkpoint, the tokens still to earn today, and the streak.

- The built-in Assist agent (no LLM) gets English and Hungarian sentences
  (assist_sentences.py, registered like conversation triggers) with the
  children's names in every form, and sentences without a name for every
  child. A name Kis Segítő does not know is left to the other agents.
- LLM agents get the same answers through the ``KisSegitoChildStatus`` intent
  (see llm.py), and the child sensors carry the same data as attributes.
"""

from __future__ import annotations

import logging
import math
import unicodedata
from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .assist_lang import grammar, languages, say
from .assist_sentences import all_sentences, child_sentences, routine_sentences
from .entity_helpers import next_checkpoint, running_routines
from .logic import applies_to, reward_for
from .manager import KisSegitoManager

_LOGGER = logging.getLogger(__name__)

INTENT_CHILD_STATUS = "KisSegitoChildStatus"
TOPICS = ("tokens", "task", "checkpoint", "earnable", "streak", "all")


# ---------------------------------------------------------------- data


def child_status(manager: KisSegitoManager, child_id: str) -> dict[str, Any]:
    """Everything an assistant can tell about a child right now."""
    child = manager.child(child_id) or {}
    now = dt_util.now()
    day = now.date()
    balances = manager.balances(child_id)
    current = next(
        (r for r in running_routines(manager) if applies_to(r, child_id)), None
    )
    tasks_left: list[str] = []
    if current is not None:
        done = manager.progress(day, current["id"], child_id)["tasks"]
        tasks_left = [
            t.get("label") or t.get("icon", "")
            for t in current.get("tasks", [])
            if t["id"] not in done
        ]
    if current is None:
        task_status = "none"
    elif tasks_left:
        task_status = "task"
    else:
        task_status = "done"
    nxt = next_checkpoint(manager, child_id)
    minutes = None
    if nxt is not None:
        due = dt_util.parse_datetime(nxt["time"])
        if due is not None:
            minutes = max(0, math.ceil((due - now).total_seconds() / 60))
    earn_today = 0
    earn_now = 0
    for routine in manager.routines_on_day(day):
        if not applies_to(routine, child_id):
            continue
        reached = manager.progress(day, routine["id"], child_id)["checkpoints"]
        for cp in routine.get("checkpoints", []):
            if not applies_to(cp, child_id) or cp["id"] in reached:
                continue
            due = manager.checkpoint_time(routine, cp, day)
            tokens = reward_for(cp.get("reward_bands", []), (due - now).total_seconds())
            earn_today += tokens
            if current is not None and routine["id"] == current["id"]:
                earn_now += tokens
    return {
        "name": child.get("name", ""),
        "wallet": balances["wallet"],
        "piggy": balances["piggy"],
        "piggy_unlocked": bool(child.get("piggy_unlocked")),
        "task_status": task_status,
        "current_routine": current.get("name") if current else None,
        "current_task": tasks_left[0] if tasks_left else None,
        "tasks_left": tasks_left,
        "next_checkpoint": nxt["name"] if nxt else None,
        "next_checkpoint_time": nxt["time"] if nxt else None,
        "next_checkpoint_minutes": minutes,
        "tokens_earnable_now": earn_now,
        "tokens_earnable_today": earn_today,
        "streak": manager.streak(child_id),
        "streak_target": int(manager.settings.get("streak_target", 7)),
    }


def _plain(text: str) -> str:
    """Lower case without accents, for comparing names."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip()


def find_child(manager: KisSegitoManager, spoken: str) -> dict[str, Any] | None:
    """The child named in a sentence: by name or alias, also with a Hungarian
    case ending (e.g. a name + "nak"/"nek")."""
    word = _plain(spoken).strip(" ?.!,'’")
    if not word:
        return None
    best: tuple[int, dict[str, Any]] | None = None
    for child in manager.children(active_only=True):
        names = [child.get("name", "")] + [
            a.strip() for a in str(child.get("aliases") or "").split(",")
        ]
        for name in filter(None, (_plain(n) for n in names)):
            if word == name:
                return child
            # A case ending or a possessive after the name.
            if word.startswith(name) and len(word) - len(name) <= 5:
                rest = len(word) - len(name)
                if best is None or rest < best[0]:
                    best = (rest, child)
    return best[1] if best else None


# ---------------------------------------------------------------- answers
#
# Answers are made to be spoken: numbers and times are words in the languages
# that have a grammar for it (assist_lang.py), so every text-to-speech engine
# reads them right. The wordings are in assist_translations/<language>.json;
# each answer has a few, chosen at random.


def _names(child: dict[str, Any]) -> list[str]:
    return [child.get("name", "")] + [
        a.strip() for a in str(child.get("aliases") or "").split(",") if a.strip()
    ]


def _due(status: dict[str, Any]) -> datetime | None:
    if not status.get("next_checkpoint_time"):
        return None
    due = dt_util.parse_datetime(status["next_checkpoint_time"])
    return dt_util.as_local(due) if due is not None else None


def _answer_parts(status: dict[str, Any], topic: str, language: str) -> list[str]:
    gram = grammar(language)
    values = gram.name_values(status["name"]) | {"wallet": status["wallet"]}
    parts: list[str] = []

    def add(section: str, case: str, **extra: Any) -> None:
        parts.append(say(language, section, case, **(values | extra)))

    if topic in ("tokens", "all"):
        add("tokens", "some" if status["wallet"] else "none")
        if status["piggy_unlocked"]:
            add("tokens", "piggy" if status["piggy"] else "piggy_empty", piggy=status["piggy"])
    if topic in ("task", "all"):
        left = status["tasks_left"]
        phrases = gram.phrase_values(
            status["current_routine"] or "", status["current_task"] or "", ""
        )
        if status["task_status"] == "task":
            add("task", "last" if len(left) == 1 else "task", left=len(left), **phrases)
        elif status["task_status"] == "done":
            add("task", "done", **phrases)
        else:
            add("task", "none")
    if topic in ("checkpoint", "all"):
        minutes = status["next_checkpoint_minutes"]
        due = _due(status)
        phrases = gram.phrase_values("", "", status["next_checkpoint"] or "")
        if minutes is None or due is None:
            add("checkpoint", "none")
        elif minutes == 0:
            add("checkpoint", "now", **phrases)
        else:
            add(
                "checkpoint", "next", at=gram.clock(due), **{"in": gram.until(minutes)}, **phrases
            )
    if topic in ("earnable", "all"):
        today = status["tokens_earnable_today"]
        now = status["tokens_earnable_now"]
        if today:
            add("earnable", "some", today=today)
            if now and now != today:
                add("earnable", "now_part", now=now)
        else:
            add("earnable", "none")
    if topic in ("streak", "all"):
        add(
            "streak",
            "some" if status["streak"] else "none",
            streak=status["streak"],
            target=status["streak_target"],
        )
    return parts


def answer(status: dict[str, Any], topic: str, language: str) -> str:
    """One spoken answer about a child, in the asker's language (English when
    there is no file for it)."""
    return " ".join(_answer_parts(status, topic, language))


def answer_all(manager: KisSegitoManager, topic: str, language: str) -> str:
    """The answer for every active child."""
    children = manager.children(active_only=True)
    if not children:
        return say(language, "general", "no_children")
    return " ".join(
        answer(child_status(manager, c["id"]), topic, language) for c in children
    )


def unknown(name: str, language: str) -> str:
    return say(language, "general", "unknown", spoken=name)


def answer_for(
    manager: KisSegitoManager, spoken: str | None, topic: str, language: str
) -> str:
    """The answer for a sentence naming a child (or every child)."""
    if not spoken or not spoken.strip():
        return answer_all(manager, topic, language)
    child = find_child(manager, spoken)
    if child is None:
        return unknown(spoken.strip(), language)
    return answer(child_status(manager, child["id"]), topic, language)


def answer_routine(manager: KisSegitoManager, routine_id: str, language: str) -> str:
    """What is left of a routine today, for every child it is for."""
    day = manager.today()
    gram = grammar(language)
    routine = manager.routine_for_day(routine_id, day)
    name = (routine or manager.routine(routine_id) or {}).get("name", "")
    if routine is None:
        return say(language, "routine_left", "not_today", **gram.phrase_values(name, "", ""))
    parts = []
    for child in manager.children(active_only=True):
        if not applies_to(routine, child["id"]):
            continue
        done = manager.progress(day, routine_id, child["id"])["tasks"]
        left = [
            t.get("label") or ""
            for t in routine.get("tasks", [])
            if t["id"] not in done and applies_to(t, child["id"])
        ]
        values = gram.name_values(child.get("name", "")) | gram.phrase_values(
            name, left[0] if left else "", ""
        )
        case = "done" if not left else "last" if len(left) == 1 else "left"
        parts.append(say(language, "routine_left", case, left=len(left), **values))
    return " ".join(parts)


# ---------------------------------------------------------------- built-in agent


def _signature(manager: KisSegitoManager) -> tuple:
    return tuple(
        (c["id"], tuple(_names(c))) for c in manager.children(active_only=True)
    ) + tuple((r["id"], r.get("name", "")) for r in manager.data["routines"])


def _register_sentences(
    hass: HomeAssistant, manager: KisSegitoManager
) -> list[Callable[[], None]]:
    """Register the sentences with the built-in agent (when it is there): one
    set per child with its names in every form, and one for every child."""
    try:
        from homeassistant.components.conversation.agent_manager import (
            get_agent_manager,
        )
    except ImportError:
        return []
    agents = get_agent_manager(hass)
    removers: list[Callable[[], None]] = []

    def add(sentences: list[str], respond: Callable[..., Any]) -> None:
        removers.append(agents.register_trigger(sentences, respond))

    try:
        for child in manager.children(active_only=True):
            child_id = child["id"]
            per_topic: dict[str, list[str]] = {}
            for language in languages():
                for topic, sentences in child_sentences(
                    _names(child), language
                ).items():
                    per_topic.setdefault(topic, []).extend(sentences)
            for topic, sentences in per_topic.items():

                async def respond(
                    user_input: Any,
                    result: Any,
                    topic: str = topic,
                    child_id: str = child_id,
                ) -> str:
                    status = child_status(manager, child_id)
                    return answer(status, topic, user_input.language or "en")

                add(sentences, respond)
        for topic in TOPICS[:-1]:

            async def respond_all(
                user_input: Any, result: Any, topic: str = topic
            ) -> str:
                return answer_all(manager, topic, user_input.language or "en")

            add(
                [s for lang in languages() for s in all_sentences(lang).get(topic, [])],
                respond_all,
            )
        for routine in manager.data["routines"]:
            if not routine.get("name"):
                continue
            routine_id = routine["id"]
            sentences = [
                s
                for lang in languages()
                for items in routine_sentences([routine["name"]], lang).values()
                for s in items
            ]

            async def respond_routine(
                user_input: Any, result: Any, routine_id: str = routine_id
            ) -> str:
                return answer_routine(manager, routine_id, user_input.language or "en")

            if sentences:
                add(sentences, respond_routine)
    except Exception:  # noqa: BLE001 - a changed agent API only loses the sentences
        _LOGGER.warning("Kis Segítő: the Assist sentences could not be added")
    return removers


# ---------------------------------------------------------------- intent


class ChildStatusIntent(intent.IntentHandler):
    """Read-only: what Kis Segítő knows about the children (for LLM agents)."""

    intent_type = INTENT_CHILD_STATUS
    description = (
        "Kis Segítő (children's routine helper): a child's tokens, current task, "
        "time to the next checkpoint, tokens still to earn today and streak. "
        "Leave out the name to get every child. Read only."
    )
    slot_schema: ClassVar[dict[Any, Any]] = {
        vol.Optional("name"): str,
        vol.Optional("topic"): vol.In(TOPICS),
    }

    def __init__(self, manager: KisSegitoManager) -> None:
        self.manager = manager

    def _data(self, child: dict[str, Any]) -> dict[str, Any]:
        data = child_status(self.manager, child["id"])
        data["aliases"] = _names(child)[1:]
        return data

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        slots = self.async_validate_slots(intent_obj.slots)
        topic = slots.get("topic", {}).get("value", "all")
        name = str(slots.get("name", {}).get("value") or "").strip()
        language = intent_obj.language or "en"
        response = intent_obj.create_response()
        response.async_set_speech(answer_for(self.manager, name, topic, language))
        if name:
            child = find_child(self.manager, name)
            if child is not None:
                response.async_set_speech_slots(self._data(child))
        else:
            response.async_set_speech_slots(
                {
                    "children": [
                        self._data(c) for c in self.manager.children(active_only=True)
                    ]
                }
            )
        return response


@callback
def async_setup_assist(
    hass: HomeAssistant, manager: KisSegitoManager
) -> Callable[[], None]:
    """Add the intent and, once Home Assistant runs, the sentences (added
    again when a child's names change)."""
    intent.async_register(hass, ChildStatusIntent(manager))
    sentences: list[Callable[[], None]] = []
    removers: list[Callable[[], None]] = []
    state: dict[str, Any] = {"signature": None, "started": False}

    @callback
    def refresh() -> None:
        if not state["started"]:
            return
        signature = _signature(manager)
        if signature == state["signature"]:
            return
        state["signature"] = signature
        while sentences:
            sentences.pop()()
        sentences.extend(_register_sentences(hass, manager))

    @callback
    def started(_hass: HomeAssistant) -> None:
        state["started"] = True
        refresh()

    removers.append(async_at_started(hass, started))
    removers.append(manager.async_add_listener(refresh))

    @callback
    def remove() -> None:
        while removers:
            removers.pop()()
        while sentences:
            sentences.pop()()
        intent.async_remove(hass, INTENT_CHILD_STATUS)

    return remove
