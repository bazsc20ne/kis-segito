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
import random
import unicodedata
from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .assist_sentences import all_sentences, child_sentences
from .assist_words import (
    en_clock,
    en_in,
    en_number,
    hu_article,
    hu_clock,
    hu_forms,
    hu_in,
    hu_number,
)
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
# Answers are made to be spoken: numbers and times are written out in words
# and there are no symbols, so every text-to-speech engine reads them right.
# Each answer has a few wordings, chosen at random.


def _names(child: dict[str, Any]) -> list[str]:
    return [child.get("name", "")] + [
        a.strip() for a in str(child.get("aliases") or "").split(",") if a.strip()
    ]


def _due(status: dict[str, Any]) -> datetime | None:
    if not status.get("next_checkpoint_time"):
        return None
    due = dt_util.parse_datetime(status["next_checkpoint_time"])
    return dt_util.as_local(due) if due is not None else None


def _hu_answer(status: dict[str, Any], topic: str) -> list[str]:
    name = status["name"]
    dative = hu_forms(name)["dative"]
    parts: list[str] = []
    if topic in ("tokens", "all"):
        wallet = status["wallet"]
        if wallet:
            n = hu_number(wallet)
            parts.append(
                random.choice(
                    [
                        f"{dative} {n} zsetonja van.",
                        f"{dative} most {n} zsetonja van.",
                        f"{name} pénztárcájában {n} zseton van.",
                    ]
                )
            )
        else:
            parts.append(
                random.choice(
                    [f"{dative} most nincs zsetonja.", f"{name} pénztárcája most üres."]
                )
            )
        if status["piggy_unlocked"]:
            if status["piggy"]:
                parts.append(f"A perselyében {hu_number(status['piggy'])} zseton van.")
            else:
                parts.append("A perselye üres.")
    if topic in ("task", "all"):
        routine = status["current_routine"]
        left = status["tasks_left"]
        if status["task_status"] == "task":
            text = random.choice(
                [
                    f"{name} most {hu_article(routine)} {routine} rutint csinálja.",
                    f"{name} most {hu_article(routine)} {routine} rutinnál tart.",
                ]
            )
            task = status["current_task"]
            text += " " + random.choice(
                [f"A következő feladata {task}.", f"Most ez jön, {task}."]
            )
            if len(left) == 1:
                text += " Ez az utolsó feladata."
            else:
                text += f" Még {hu_number(len(left))} feladat van hátra."
            parts.append(text)
        elif status["task_status"] == "done":
            parts.append(
                random.choice(
                    [
                        f"{name} {hu_article(routine)} {routine} rutin minden feladatát elvégezte. Ügyes!",
                        f"{name} már kész {hu_article(routine)} {routine} rutin összes feladatával.",
                    ]
                )
            )
        else:
            parts.append(
                random.choice(
                    [
                        f"{dative} most nincs feladata.",
                        f"{dative} most nincs semmi dolga.",
                    ]
                )
            )
    if topic in ("checkpoint", "all"):
        minutes = status["next_checkpoint_minutes"]
        due = _due(status)
        if minutes is None or due is None:
            parts.append(
                random.choice(
                    [
                        f"{dative} mára nincs több ellenőrzőpontja.",
                        f"{dative} ma már nincs ellenőrzőpontja.",
                    ]
                )
            )
        elif minutes == 0:
            parts.append(
                f"{name} ellenőrzőpontja, {hu_article(status['next_checkpoint'])} "
                f"{status['next_checkpoint']}, most van."
            )
        else:
            cp = status["next_checkpoint"]
            parts.append(
                random.choice(
                    [
                        f"{name} következő ellenőrzőpontja {hu_article(cp)} {cp}, {hu_in(minutes)}, {hu_clock(due)}.",
                        f"{hu_in(minutes).capitalize()} jön {name} következő ellenőrzőpontja, {hu_article(cp)} {cp}. Ez {hu_clock(due)} lesz.",
                    ]
                )
            )
    if topic in ("earnable", "all"):
        today = status["tokens_earnable_today"]
        now = status["tokens_earnable_now"]
        if today:
            text = random.choice(
                [
                    f"{name} ma még {hu_number(today)} zsetont szerezhet.",
                    f"{dative} ma még {hu_number(today)} zseton jár, ha mindent időben megcsinál.",
                ]
            )
            if now and now != today:
                text += f" Ebből {hu_number(now)} a mostani rutinban."
            parts.append(text)
        else:
            parts.append(f"{name} ma már nem szerezhet több zsetont.")
    if topic in ("streak", "all"):
        streak = status["streak"]
        target = status["streak_target"]
        if streak:
            parts.append(
                random.choice(
                    [
                        f"{name} már {hu_number(streak)} napja mindent megcsinál. A cél {hu_number(target)} nap.",
                        f"{name} {hu_number(target)} napból {hu_number(streak)} napot már teljesített.",
                    ]
                )
            )
        else:
            parts.append(
                f"{dative} most nincs sorozata. A cél {hu_number(target)} hibátlan nap egymás után."
            )
    return parts


def _en_answer(status: dict[str, Any], topic: str) -> list[str]:
    name = status["name"]
    parts: list[str] = []

    def tokens(n: int) -> str:
        return f"{en_number(n)} token{'' if n == 1 else 's'}"

    def days(n: int) -> str:
        return f"{en_number(n)} day{'' if n == 1 else 's'}"

    if topic in ("tokens", "all"):
        wallet = status["wallet"]
        if wallet:
            parts.append(
                random.choice(
                    [
                        f"{name} has {tokens(wallet)}.",
                        f"{name} has {tokens(wallet)} right now.",
                    ]
                )
            )
        else:
            parts.append(f"{name} has no tokens right now.")
        if status["piggy_unlocked"]:
            if status["piggy"]:
                parts.append(f"The piggy bank holds {tokens(status['piggy'])}.")
            else:
                parts.append("The piggy bank is empty.")
    if topic in ("task", "all"):
        routine = status["current_routine"]
        left = status["tasks_left"]
        if status["task_status"] == "task":
            text = f"{name} is doing {routine} now. Next is {status['current_task']}."
            if len(left) == 1:
                text += " That is the last task."
            else:
                text += f" {en_number(len(left)).capitalize()} tasks are left."
            parts.append(text)
        elif status["task_status"] == "done":
            parts.append(
                random.choice(
                    [
                        f"{name} has finished every task of {routine}. Well done!",
                        f"{name} is done with all of {routine}.",
                    ]
                )
            )
        else:
            parts.append(
                random.choice(
                    [
                        f"{name} has no task right now.",
                        f"{name} has nothing to do right now.",
                    ]
                )
            )
    if topic in ("checkpoint", "all"):
        minutes = status["next_checkpoint_minutes"]
        due = _due(status)
        if minutes is None or due is None:
            parts.append(f"{name} has no more checkpoints today.")
        elif minutes == 0:
            parts.append(f"{name}'s checkpoint, {status['next_checkpoint']}, is now.")
        else:
            cp = status["next_checkpoint"]
            parts.append(
                random.choice(
                    [
                        f"{name}'s next checkpoint, {cp}, is {en_in(minutes)}, {en_clock(due)}.",
                        f"{name}'s next checkpoint is {cp}, {en_clock(due)}. That is {en_in(minutes)}.",
                    ]
                )
            )
    if topic in ("earnable", "all"):
        today = status["tokens_earnable_today"]
        now = status["tokens_earnable_now"]
        if today:
            text = f"{name} can still earn {tokens(today)} today."
            if now and now != today:
                text += (
                    f" {en_number(now).capitalize()} of them in the current routine."
                )
            parts.append(text)
        else:
            parts.append(f"{name} can't earn any more tokens today.")
    if topic in ("streak", "all"):
        streak = status["streak"]
        target = status["streak_target"]
        if streak:
            parts.append(
                random.choice(
                    [
                        f"{name}'s streak is {days(streak)} out of {en_number(target)}.",
                        f"{name} has done everything for {days(streak)} in a row. The goal is {days(target)}.",
                    ]
                )
            )
        else:
            parts.append(
                f"{name} has no streak right now. The goal is {days(target)} in a row."
            )
    return parts


def answer(status: dict[str, Any], topic: str, language: str) -> str:
    """One spoken answer about a child (Hungarian, or English for every
    other language)."""
    if (language or "").lower().startswith("hu"):
        return " ".join(_hu_answer(status, topic))
    return " ".join(_en_answer(status, topic))


def answer_all(manager: KisSegitoManager, topic: str, language: str) -> str:
    """The answer for every active child."""
    children = manager.children(active_only=True)
    if not children:
        if (language or "").lower().startswith("hu"):
            return "Még nincs gyerek a Kis Segítőben."
        return "There are no children in Kis Segítő yet."
    return " ".join(
        answer(child_status(manager, c["id"]), topic, language) for c in children
    )


def unknown(name: str, language: str) -> str:
    if (language or "").lower().startswith("hu"):
        return f"Nem ismerek {name} nevű gyereket a Kis Segítőben."
    return f"I don't know a child called {name} in Kis Segítő."


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


# ---------------------------------------------------------------- built-in agent


def _signature(manager: KisSegitoManager) -> tuple:
    return tuple(
        (c["id"], tuple(_names(c))) for c in manager.children(active_only=True)
    )


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
            for language in ("hu", "en"):
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

            add(all_sentences("hu")[topic] + all_sentences("en")[topic], respond_all)
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
