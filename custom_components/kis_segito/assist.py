# SPDX-License-Identifier: AGPL-3.0-only
"""Answers for Home Assistant's assistants (Assist), read only.

Per child: tokens (wallet, piggy bank), the task right now, the time until the
next checkpoint, the tokens still to earn today, and the streak.

- The built-in Assist agent (no LLM) gets English and Hungarian sentences with
  the child's name in them (registered like conversation triggers).
- LLM agents get the same answers through the ``KisSegitoChildStatus`` intent
  (see llm.py), and the child sensors carry the same data as attributes.
"""

from __future__ import annotations

import logging
import math
import unicodedata
from collections.abc import Callable
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

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

TEXTS = {
    "en": {
        "unknown": "I don't know a child called {name} in Kis Segítő.",
        "tokens": "{name} has {wallet} tokens.",
        "piggy": " The piggy bank holds {piggy}.",
        "task": "{name} is doing {routine} now: next is {task}, {left} left.",
        "task_done": "{name} has finished every task of {routine}.",
        "no_task": "{name} has no task right now.",
        "checkpoint": "{name}'s next checkpoint, {checkpoint}, is in {minutes} minutes.",
        "no_checkpoint": "{name} has no more checkpoints today.",
        "earnable": "{name} can still earn {today} tokens today.",
        "earnable_now": " {now} of them in the current routine.",
        "streak": "{name}'s streak is {streak} of {target} days.",
    },
    "hu": {
        "unknown": "Nem ismerek {name} nevű gyereket a Kis Segítőben.",
        "tokens": "{name} zsetonjai: {wallet}.",
        "piggy": " A perselyben: {piggy}.",
        "task": "{name} most a(z) {routine} rutint csinálja: a következő feladat {task}, még {left} van hátra.",
        "task_done": "{name} a(z) {routine} rutin minden feladatát elvégezte.",
        "no_task": "{name} feladata most nincs.",
        "checkpoint": "{name} következő checkpointja ({checkpoint}) {minutes} perc múlva van.",
        "no_checkpoint": "{name} mára nincs több checkpointja.",
        "earnable": "{name} ma még {today} zsetont szerezhet.",
        "earnable_now": " Ebből {now} a mostani rutinban.",
        "streak": "{name} sorozata: {streak} / {target} nap.",
    },
}


def answer(status: dict[str, Any], topic: str, language: str) -> str:
    """One answer about a child, in English or Hungarian."""
    t = TEXTS["hu" if language.startswith("hu") else "en"]
    name = status["name"]
    parts: list[str] = []
    if topic in ("tokens", "all"):
        text = t["tokens"].format(name=name, wallet=status["wallet"])
        if status["piggy_unlocked"]:
            text += t["piggy"].format(piggy=status["piggy"])
        parts.append(text)
    if topic in ("task", "all"):
        if status["task_status"] == "task":
            parts.append(
                t["task"].format(
                    name=name,
                    routine=status["current_routine"],
                    task=status["current_task"],
                    left=len(status["tasks_left"]),
                )
            )
        elif status["task_status"] == "done":
            parts.append(
                t["task_done"].format(name=name, routine=status["current_routine"])
            )
        else:
            parts.append(t["no_task"].format(name=name))
    if topic in ("checkpoint", "all"):
        if status["next_checkpoint_minutes"] is None:
            parts.append(t["no_checkpoint"].format(name=name))
        else:
            parts.append(
                t["checkpoint"].format(
                    name=name,
                    checkpoint=status["next_checkpoint"],
                    minutes=status["next_checkpoint_minutes"],
                )
            )
    if topic in ("earnable", "all"):
        text = t["earnable"].format(name=name, today=status["tokens_earnable_today"])
        if status["tokens_earnable_now"]:
            text += t["earnable_now"].format(now=status["tokens_earnable_now"])
        parts.append(text)
    if topic in ("streak", "all"):
        parts.append(
            t["streak"].format(
                name=name, streak=status["streak"], target=status["streak_target"]
            )
        )
    return " ".join(parts)


def answer_for(
    manager: KisSegitoManager, spoken: str, topic: str, language: str
) -> str:
    """The answer for a sentence naming a child."""
    child = find_child(manager, spoken)
    if child is None:
        t = TEXTS["hu" if language.startswith("hu") else "en"]
        return t["unknown"].format(name=spoken.strip())
    return answer(child_status(manager, child["id"]), topic, language)


# ---------------------------------------------------------------- built-in agent

# Sentences for the built-in agent ({child}: the child's name, any words).
SENTENCES: dict[str, list[str]] = {
    "tokens": [
        "how many (coins|tokens) does {child} have",
        "how many (coins|tokens) has {child} got",
        "what is {child}'s (balance|wallet)",
        "hány zsetonja van {child}",
        "{child} hány zsetonja van",
        "mennyi zsetonja van {child}",
        "{child} mennyi zsetonja van",
        "hány zseton van {child}",
    ],
    "task": [
        "does {child} have a task [right] now",
        "what is {child}'s task [right] now",
        "what (does|should) {child} (do|be doing) [right] now",
        "van most feladata {child}",
        "{child} van most feladata",
        "mi {child} feladata most",
        "mi a feladata most {child}",
        "{child} mi a feladata most",
        "mit kell most csinálnia {child}",
    ],
    "checkpoint": [
        "how long until {child}'s next checkpoint",
        "when is {child}'s next checkpoint",
        "how much time does {child} have until the next checkpoint",
        "mennyi idő van {child} következő checkpointjáig",
        "mikor van {child} következő checkpointja",
        "mennyi ideje van {child} a következő checkpointig",
        "{child} mennyi ideje van a következő checkpointig",
    ],
    "earnable": [
        "how many (coins|tokens) can {child} [still] (get|earn) today",
        "how many (coins|tokens) can {child} [still] (get|earn)",
        "hány zsetont kaphat még ma {child}",
        "hány zsetont szerezhet még ma {child}",
        "{child} hány zsetont kaphat még ma",
        "{child} hány zsetont szerezhet még ma",
        "mennyi zsetont szerezhet még ma {child}",
    ],
    "streak": [
        "how long is {child}'s streak",
        "what is {child}'s streak",
        "hány napos {child} sorozata",
        "milyen hosszú {child} sorozata",
    ],
}


def _register_sentences(
    hass: HomeAssistant, manager: KisSegitoManager
) -> list[Callable[[], None]]:
    """Register the sentences with the built-in agent (when it is there)."""
    try:
        from homeassistant.components.conversation.agent_manager import (
            get_agent_manager,
        )
    except ImportError:
        return []
    removers = []
    for topic, sentences in SENTENCES.items():

        async def respond(
            user_input: Any, result: Any, topic: str = topic
        ) -> str | None:
            entity = result.entities.get("child")
            spoken = str(
                getattr(entity, "text", None) or getattr(entity, "value", "") or ""
            )
            return answer_for(manager, spoken, topic, user_input.language or "en")

        try:
            removers.append(
                get_agent_manager(hass).register_trigger(sentences, respond)
            )
        except Exception:  # noqa: BLE001 - a changed agent API only loses the sentences
            _LOGGER.warning("Kis Segítő: the Assist sentences could not be added")
            break
    return removers


# ---------------------------------------------------------------- intent


class ChildStatusIntent(intent.IntentHandler):
    """Read-only: what Kis Segítő knows about a child (for LLM agents)."""

    intent_type = INTENT_CHILD_STATUS
    description = (
        "Kis Segítő (children's routine helper): a child's tokens, current task, "
        "time to the next checkpoint, tokens still to earn today and streak. "
        "Read only."
    )
    slot_schema: ClassVar[dict[Any, Any]] = {
        vol.Required("name"): str,
        vol.Optional("topic"): vol.In(TOPICS),
    }

    def __init__(self, manager: KisSegitoManager) -> None:
        self.manager = manager

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        slots = self.async_validate_slots(intent_obj.slots)
        topic = slots.get("topic", {}).get("value", "all")
        speech = answer_for(
            self.manager, slots["name"]["value"], topic, intent_obj.language or "en"
        )
        response = intent_obj.create_response()
        response.async_set_speech(speech)
        child = find_child(self.manager, slots["name"]["value"])
        if child is not None:
            response.async_set_speech_slots(child_status(self.manager, child["id"]))
        return response


@callback
def async_setup_assist(
    hass: HomeAssistant, manager: KisSegitoManager
) -> Callable[[], None]:
    """Add the intent and, once Home Assistant runs, the sentences."""
    intent.async_register(hass, ChildStatusIntent(manager))
    removers: list[Callable[[], None]] = []

    @callback
    def started(_hass: HomeAssistant) -> None:
        removers.extend(_register_sentences(hass, manager))

    removers.append(async_at_started(hass, started))

    @callback
    def remove() -> None:
        while removers:
            removers.pop()()
        intent.async_remove(hass, INTENT_CHILD_STATUS)

    return remove
