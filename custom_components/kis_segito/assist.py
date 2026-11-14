# SPDX-License-Identifier: AGPL-3.0-only
"""Answers for Home Assistant's assistants (Assist), read only.

Per child: tokens (wallet, piggy bank), the task right now, the tasks still
left today, the next checkpoint, the next routine, the tokens still to earn
today and the streak; and the tasks that lead to a checkpoint.

- The built-in Assist agent (no LLM) gets the sentences of
  assist_translations/<language>.json (registered like conversation
  triggers): about a named child, about every child, in the first person
  ("how many tokens do I have"), short follow-ups ("and me?") and questions
  about a routine or a checkpoint. A name Kis Segítő does not know is left to
  the other agents.
- First-person questions are answered for the child who is speaking: the
  one a speaker recognition integration reports for the conversation, when
  one is installed, or else the children the voice satellite is assigned to
  in Kis Segítő. Kis Segítő never guesses one child.
- LLM agents get the same answers through the ``KisSegitoChildStatus`` intent
  (see llm.py), and the child sensors carry the same data as attributes.
"""

from __future__ import annotations

import logging
import math
import sys
import time
import unicodedata
from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .assist_lang import grammar, group, has, join, languages, pick, say, sentence
from .assist_sentences import (
    all_sentences,
    checkpoint_sentences,
    child_sentences,
    followup_sentences,
    routine_sentences,
    speaker_sentences,
)
from .entity_helpers import next_checkpoint, routine_times, running_routines
from .logic import applies_to, reward_for
from .manager import KisSegitoManager

_LOGGER = logging.getLogger(__name__)

INTENT_CHILD_STATUS = "KisSegitoChildStatus"
# "all" asks for a summary (tokens, task and checkpoint).
TOPICS = (
    "tokens",
    "task",
    "remaining",
    "checkpoint",
    "next_routine",
    "earnable",
    "streak",
    "all",
)
SUMMARY = ("tokens", "task", "checkpoint")
# How long a follow-up ("and me?") still refers to the previous question.
FOLLOWUP_SECONDS = 60
# How long a speaker recognition integration may take to answer.
SPEAKER_TIMEOUT = 1.5
SPEAKER_HOOK = "async_get_turn_result"


# ---------------------------------------------------------------- data


def _minutes_until(when: datetime | None, now: datetime) -> int | None:
    if when is None:
        return None
    return max(0, math.ceil((when - now).total_seconds() / 60))


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
            if t["id"] not in done and applies_to(t, child_id)
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
        minutes = _minutes_until(dt_util.parse_datetime(nxt["time"]), now)
    earn_today = 0
    earn_now = 0
    next_routine: tuple[datetime, dict[str, Any]] | None = None
    for routine in manager.routines_on_day(day):
        if not applies_to(routine, child_id):
            continue
        start = routine_times(manager, routine, day)[0]
        if start > now and (next_routine is None or start < next_routine[0]):
            next_routine = (start, routine)
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
        "next_routine": next_routine[1].get("name") if next_routine else None,
        "next_routine_time": next_routine[0].isoformat() if next_routine else None,
        "next_routine_minutes": _minutes_until(next_routine[0], now)
        if next_routine
        else None,
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
# each answer has a few, chosen at random, and labels made by the user
# (routines, tasks, checkpoints) are never given a suffix.


def _names(child: dict[str, Any]) -> list[str]:
    return [child.get("name", "")] + [
        a.strip() for a in str(child.get("aliases") or "").split(",") if a.strip()
    ]


def _local(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    return dt_util.as_local(parsed) if parsed is not None else None


def _topic(topic: str) -> str:
    return "summary" if topic in ("all", "summary") else topic


def _values(status: dict[str, Any], language: str) -> dict[str, Any]:
    """Everything the wordings of a child's answer can use."""
    gram = grammar(language)
    left = status["tasks_left"]
    labels = [gram.label(t) for t in left]
    values: dict[str, Any] = (
        gram.name_values(status["name"])
        | gram.phrase_values(
            status["current_routine"] or "",
            status["current_task"] or "",
            status["next_checkpoint"] or "",
        )
        | {
            "wallet": status["wallet"],
            "piggy": status["piggy"],
            "left": len(left),
            "left_after": max(len(left) - 1, 0),
            "tasks_list": join(language, labels),
            "tasks_rest_list": join(language, labels[1:]),
            "today": status["tokens_earnable_today"],
            "now": status["tokens_earnable_now"],
            "streak": status["streak"],
            "target": status["streak_target"],
        }
    )
    due = _local(status["next_checkpoint_time"])
    minutes = status["next_checkpoint_minutes"]
    if due is not None and minutes is not None:
        values |= {
            "cp_clock": gram.clock(due),
            "cp_in": gram.until(minutes),
            "cp_left": gram.span(minutes),
        }
    start = _local(status.get("next_routine_time"))
    if start is not None and status.get("next_routine_minutes") is not None:
        values |= {
            "start_clock": gram.clock(start),
            "start_in": gram.until(status["next_routine_minutes"]),
            "next_routine": status["next_routine"],
            "next_routine_art": gram.label(status["next_routine"] or ""),
        }
    return values


def _child_parts(
    status: dict[str, Any], topic: str, language: str, scope: str = "child"
) -> list[str]:
    """The sentences of a child's answer ("speaker": said to the child)."""
    topic = _topic(topic)
    if topic == "summary":
        return [p for t in SUMMARY for p in _child_parts(status, t, language, scope)]
    values = _values(status, language)
    parts: list[str] = []

    def add(case: str, **extra: Any) -> None:
        parts.append(say(language, scope, topic, case, **(values | extra)))

    if topic == "tokens":
        add("wallet" if status["wallet"] else "wallet_zero")
        if status["piggy_unlocked"]:
            add("piggy" if status["piggy"] else "piggy_zero")
    elif topic in ("task", "remaining"):
        left = len(status["tasks_left"])
        if status["task_status"] == "task":
            if topic == "task":
                add("task_last" if left == 1 else "task_many")
            else:
                add("one" if left == 1 else "many")
        elif status["task_status"] == "done":
            add("done")
        elif topic == "task" and "cp_clock" in values:
            add("none_next")
        else:
            add("none")
    elif topic == "checkpoint":
        if "cp_clock" not in values:
            add("none")
        elif status["next_checkpoint_minutes"] == 0:
            add("now")
        else:
            add("soon")
    elif topic == "next_routine":
        if "start_clock" in values:
            add("soon", routine=values["next_routine"], routine_art=values["next_routine_art"])
        else:
            add("none")
    elif topic == "earnable":
        today = status["tokens_earnable_today"]
        now = status["tokens_earnable_now"]
        if today:
            add("some")
            if now and now != today:
                add("some_now")
        else:
            add("zero")
    elif topic == "streak":
        target = status["streak_target"]
        if not status["streak"]:
            add("zero")
        elif target and status["streak"] >= target and has(language, scope, topic, "reached"):
            add("reached")
        else:
            add("some")
    return parts


def answer(status: dict[str, Any], topic: str, language: str, scope: str = "child") -> str:
    """One spoken answer about a child, in the asker's language (English when
    there is no file for it)."""
    return " ".join(_child_parts(status, topic, language, scope))


def _group_values(statuses: list[dict[str, Any]], language: str) -> dict[str, Any]:
    gram = grammar(language)
    count = len(statuses)
    names = [gram.name_values(s["name"]) for s in statuses]
    return {
        "all_dat": group(language, "all_dat", count),
        "all_nom": group(language, "all_nom", count),
        "all_pron": group(language, "all_pron", count),
        "names_and": join(language, [n["name"] for n in names]),
        "names_and_dat": join(language, [n["name_dat"] for n in names]),
    }


def _all_parts(statuses: list[dict[str, Any]], topic: str, language: str) -> list[str]:
    """The answer for several children at once: one sentence when they are
    all the same, otherwise a short list (largest first)."""
    topic = _topic(topic)
    if len(statuses) == 1:
        return _child_parts(statuses[0], topic, language)
    if topic == "summary":
        return [p for t in SUMMARY for p in _all_parts(statuses, t, language)]
    common = _group_values(statuses, language)

    def say_for(
        case: str, status: dict[str, Any], variant: int | None = None, **extra: Any
    ) -> str:
        values = _values(status, language) | common | extra
        return say(language, "all", topic, case, variant=variant, **values)

    first = statuses[0]

    def numbers(key: str, items: list[dict[str, Any]], prefix: str = "") -> list[str]:
        values = [s[key] for s in items]
        if not any(values):
            return [say_for(f"{prefix}all_zero", items[0])]
        if len(set(values)) == 1:
            return [say_for(f"{prefix}same", items[0], **_group_values(items, language))]
        ordered = sorted(items, key=lambda s: s[key], reverse=True)
        # The items of the list use matching wordings.
        variant = pick(language, "all", topic, f"{prefix}list_first")
        pieces = [say_for(f"{prefix}list_first", ordered[0], variant=variant).rstrip(".")]
        for status in ordered[1:]:
            case = f"{prefix}list_next" if status[key] else f"{prefix}list_next_zero"
            pieces.append(say_for(case, status, variant=variant).rstrip("."))
        return [sentence(join(language, pieces))]

    if topic == "tokens":
        parts = numbers("wallet", statuses)
        unlocked = [s for s in statuses if s["piggy_unlocked"]]
        if len(unlocked) == 1:
            if unlocked[0]["piggy"]:
                parts.append(sentence(say_for("piggy_list_first", unlocked[0])))
        elif unlocked:
            parts += numbers("piggy", unlocked, "piggy_")
        return parts
    if topic == "earnable":
        return numbers("tokens_earnable_today", statuses)
    if topic == "streak":
        return numbers("streak", statuses)
    if topic == "task":
        kinds = {s["task_status"] for s in statuses}
        if kinds == {"none"}:
            nexts = {(s["next_checkpoint"], s["next_checkpoint_time"]) for s in statuses}
            if len(nexts) == 1 and first["next_checkpoint_time"]:
                return [say_for("all_none_next", first)]
            return [say_for("all_none", first)]
        if kinds == {"done"} and len({s["current_routine"] for s in statuses}) == 1:
            return [say_for("all_done", first)]
        if kinds == {"task"} and len({tuple(s["tasks_left"]) for s in statuses}) == 1:
            return [say_for("same_last" if len(first["tasks_left"]) == 1 else "same", first)]
        pieces = [
            say_for(
                {"task": "list_task", "done": "list_done"}.get(s["task_status"], "list_none"), s
            ).rstrip(".")
            for s in statuses
        ]
        return [sentence(join(language, pieces))]
    if topic == "remaining":
        kinds = {s["task_status"] for s in statuses}
        if kinds == {"none"}:
            return [say_for("all_none", first)]
        if kinds == {"done"}:
            return [say_for("all_done", first)]
        if kinds == {"task"} and len({tuple(s["tasks_left"]) for s in statuses}) == 1:
            return [say_for("same", first)]
        ordered = sorted(statuses, key=lambda s: len(s["tasks_left"]), reverse=True)
        parts = []
        for index, status in enumerate(ordered):
            left = len(status["tasks_left"])
            if status["task_status"] == "done":
                parts.append(say_for("list_done", status))
            elif status["task_status"] == "none":
                parts.append(say(language, "child", "remaining", "none", **_values(status, language)))
            elif left == 1:
                parts.append(say_for("list_next_one", status))
            else:
                parts.append(say_for("list_first" if index == 0 else "list_next", status))
        return parts
    if topic == "checkpoint":
        if not any(s["next_checkpoint_time"] for s in statuses):
            return [say_for("all_none", first)]
        if len({(s["next_checkpoint"], s["next_checkpoint_time"]) for s in statuses}) == 1:
            return [say_for("same_now" if first["next_checkpoint_minutes"] == 0 else "same", first)]
        ordered = sorted(statuses, key=lambda s: s["next_checkpoint_time"] or "~")
        return [
            say_for("list_item" if s["next_checkpoint_time"] else "list_item_none", s)
            for s in ordered
        ]
    if topic == "next_routine":
        if not any(s["next_routine_time"] for s in statuses):
            return [say_for("all_none", first)]

        def routine_values(status: dict[str, Any]) -> dict[str, Any]:
            gram = grammar(language)
            name = status["next_routine"] or ""
            return {"routine": name, "routine_art": gram.label(name)}

        if len({(s["next_routine"], s["next_routine_time"]) for s in statuses}) == 1:
            return [say_for("same", first, **routine_values(first))]
        ordered = sorted(statuses, key=lambda s: s["next_routine_time"] or "~")
        return [
            say_for(
                "list_item" if s["next_routine_time"] else "list_item_none",
                s,
                **routine_values(s),
            )
            for s in ordered
        ]
    return []


def answer_children(
    manager: KisSegitoManager,
    topic: str,
    language: str,
    children: list[dict[str, Any]] | None = None,
) -> str:
    """The answer for the given children (every active child by default)."""
    if children is None:
        children = manager.children(active_only=True)
    if not children:
        return say(language, "system", "no_children")
    statuses = [child_status(manager, c["id"]) for c in children]
    return " ".join(_all_parts(statuses, topic, language))


def answer_all(manager: KisSegitoManager, topic: str, language: str) -> str:
    """The answer for every active child."""
    return answer_children(manager, topic, language)


def unknown(name: str, language: str) -> str:
    return say(language, "system", "unknown_child", spoken=name)


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
        return say(language, "routine", "not_today", **gram.phrase_values(name, "", ""))
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
        parts.append(say(language, "routine", case, left=len(left), **values))
    return " ".join(parts)


def checkpoint_tasks(manager: KisSegitoManager, name: str) -> list[str]:
    """The tasks that lead to the checkpoints called ``name`` (today's
    routines first, then every routine)."""
    day = manager.today()
    wanted = _plain(name)
    found: list[str] = []
    seen: set[str] = set()
    for routines in (manager.routines_on_day(day), manager.data["routines"]):
        for routine in routines:
            for cp in routine.get("checkpoints", []):
                if _plain(cp.get("name", "")) != wanted or cp["id"] in seen:
                    continue
                seen.add(cp["id"])
                for task in routine.get("tasks", []):
                    lead = manager.task_checkpoint(routine, task)
                    label = task.get("label") or ""
                    if lead is not None and lead["id"] == cp["id"] and label not in found:
                        found.append(label)
        if seen:
            break
    return [t for t in found if t]


def answer_checkpoint_tasks(manager: KisSegitoManager, name: str, language: str) -> str:
    gram = grammar(language)
    tasks = checkpoint_tasks(manager, name)
    values = gram.phrase_values("", tasks[0] if tasks else "", name) | {
        "tasks_list": join(language, [gram.label(t) for t in tasks]),
        "left": len(tasks),
    }
    case = "none" if not tasks else "one" if len(tasks) == 1 else "many"
    return say(language, "checkpoint", "checkpoint_tasks", case, **values)


# ---------------------------------------------------------------- who is speaking


def _field(result: Any, key: str) -> Any:
    if isinstance(result, dict):
        return result.get(key)
    return getattr(result, key, None)


def _speaker_hooks(hass: HomeAssistant) -> list[Callable[..., Any]]:
    """Speaker recognition integrations that report who spoke in a
    conversation (``async_get_turn_result(hass, conversation_id, timeout)``).
    Optional: Kis Segítő works without one."""
    hooks = []
    for domain in list(hass.config.components):
        if "." in domain:
            continue
        module = sys.modules.get(f"custom_components.{domain}")
        hook = getattr(module, SPEAKER_HOOK, None) if module else None
        if callable(hook):
            hooks.append(hook)
    return hooks


async def recognised_child(
    hass: HomeAssistant, manager: KisSegitoManager, conversation_id: str | None
) -> tuple[dict[str, Any] | None, bool]:
    """The child a speaker recognition integration heard, and whether such
    an integration is there at all."""
    hooks = _speaker_hooks(hass)
    if not conversation_id:
        return None, bool(hooks)
    for hook in hooks:
        try:
            result = await hook(hass, conversation_id, timeout=SPEAKER_TIMEOUT)
        except Exception:  # another integration's failure must not stop the answer
            _LOGGER.debug("Kis Segítő: speaker recognition failed", exc_info=True)
            continue
        name = _field(result, "name")
        verified = _field(result, "verified")
        if not name or verified is False:
            continue
        child = find_child(manager, str(name))
        if child is not None:
            return child, True
    return None, bool(hooks)


def assigned_children(
    hass: HomeAssistant,
    manager: KisSegitoManager,
    device_id: str | None,
    satellite_id: str | None,
) -> list[dict[str, Any]]:
    """The children a voice satellite (or its area) is assigned to."""
    rules = manager.settings.get("assist_speakers") or []
    if not rules:
        return []
    area_id = None
    entity = er.async_get(hass).async_get(satellite_id) if satellite_id else None
    if entity is not None:
        device_id = device_id or entity.device_id
        area_id = entity.area_id
    device = dr.async_get(hass).async_get(device_id) if device_id else None
    if device is not None:
        area_id = area_id or device.area_id
    active = {c["id"]: c for c in manager.children(active_only=True)}

    def matching(key: str, value: str | None) -> list[str]:
        if not value:
            return []
        return [cid for rule in rules if rule.get(key) == value for cid in rule.get("children", [])]

    ids = matching("device_id", device_id) or matching("area_id", area_id)
    return [active[cid] for cid in dict.fromkeys(ids) if cid in active]


# ---------------------------------------------------------------- conversations


class Conversations:
    """What was asked last on each voice satellite (or conversation), so a
    short follow-up ("and me?") can reuse the topic for about a minute."""

    def __init__(self) -> None:
        self._last: dict[str, dict[str, Any]] = {}

    @staticmethod
    def key(user_input: Any) -> str:
        for attr in ("satellite_id", "device_id", "conversation_id"):
            value = getattr(user_input, attr, None)
            if value:
                return f"{attr}:{value}"
        return "default"

    def remember(self, user_input: Any, topic: str, *, waiting: bool = False) -> None:
        now = time.monotonic()
        self._last = {k: v for k, v in self._last.items() if now - v["at"] < FOLLOWUP_SECONDS}
        self._last[self.key(user_input)] = {"topic": topic, "waiting": waiting, "at": now}

    def last(self, user_input: Any) -> dict[str, Any] | None:
        entry = self._last.get(self.key(user_input))
        if entry is None or time.monotonic() - entry["at"] >= FOLLOWUP_SECONDS:
            return None
        return entry


class Responder:
    """Answers the built-in agent's sentences."""

    def __init__(self, hass: HomeAssistant, manager: KisSegitoManager) -> None:
        self.hass = hass
        self.manager = manager
        self.conversations = Conversations()

    @staticmethod
    def _language(user_input: Any) -> str:
        return getattr(user_input, "language", None) or "en"

    def child(self, user_input: Any, child_id: str, topic: str) -> str:
        self.conversations.remember(user_input, topic)
        language = self._language(user_input)
        if self.manager.child(child_id) is None:
            return say(language, "system", "no_children")
        return answer(child_status(self.manager, child_id), topic, language)

    def all(self, user_input: Any, topic: str) -> str:
        self.conversations.remember(user_input, topic)
        return answer_all(self.manager, topic, self._language(user_input))

    async def speaker(self, user_input: Any, topic: str) -> str:
        language = self._language(user_input)
        child, has_hook = await recognised_child(
            self.hass, self.manager, getattr(user_input, "conversation_id", None)
        )
        if child is not None:
            self.conversations.remember(user_input, topic)
            return answer(child_status(self.manager, child["id"]), topic, language, "speaker")
        children = assigned_children(
            self.hass,
            self.manager,
            getattr(user_input, "device_id", None),
            getattr(user_input, "satellite_id", None),
        )
        if len(children) == 1:
            self.conversations.remember(user_input, topic)
            status = child_status(self.manager, children[0]["id"])
            return answer(status, topic, language, "speaker")
        if not children and has_hook:
            # Ask who is speaking; "<name> vagyok" then answers this question.
            self.conversations.remember(user_input, topic, waiting=True)
            active = self.manager.children(active_only=True)
            if not active:
                return say(language, "system", "no_children")
            gram = grammar(language)
            example = gram.name_values(active[0].get("name", ""))
            return say(
                language,
                "system",
                "unknown_speaker",
                example_name=example["name"],
                example_dat=example["name_dat"],
            )
        self.conversations.remember(user_input, topic)
        return answer_children(self.manager, topic, language, children or None)

    def _followup_topic(self, user_input: Any, amount: bool) -> str | None:
        last = self.conversations.last(user_input)
        if last is not None:
            return last["topic"]
        return "tokens" if amount else None

    async def followup(self, user_input: Any, kind: str, child_id: str | None = None) -> str:
        language = self._language(user_input)
        base, _, extra = kind.partition("_")
        if base == "identify" and child_id is not None:
            last = self.conversations.last(user_input)
            if last is None:
                return say(language, "system", "no_previous_topic")
            self.conversations.remember(user_input, last["topic"])
            status = child_status(self.manager, child_id)
            return answer(status, last["topic"], language, "speaker")
        topic = self._followup_topic(user_input, extra == "amount")
        if topic is None:
            return say(language, "system", "no_previous_topic")
        if base == "speaker":
            return await self.speaker(user_input, topic)
        if base == "child" and child_id is not None:
            return self.child(user_input, child_id, topic)
        return self.all(user_input, topic)


# ---------------------------------------------------------------- built-in agent


def _checkpoint_names(manager: KisSegitoManager) -> list[str]:
    names: dict[str, str] = {}
    for routine in manager.data["routines"]:
        for cp in routine.get("checkpoints", []):
            name = (cp.get("name") or "").strip()
            if name:
                names.setdefault(_plain(name), name)
    return list(names.values())


def _signature(manager: KisSegitoManager) -> tuple:
    return (
        tuple((c["id"], tuple(_names(c))) for c in manager.children(active_only=True))
        + tuple((r["id"], r.get("name", "")) for r in manager.data["routines"])
        + tuple(_checkpoint_names(manager))
    )


def _register_sentences(
    hass: HomeAssistant, manager: KisSegitoManager, responder: Responder
) -> list[Callable[[], None]]:
    """Register the sentences with the built-in agent (when it is there)."""
    try:
        from homeassistant.components.conversation.agent_manager import (
            get_agent_manager,
        )
    except ImportError:
        return []
    agents = get_agent_manager(hass)
    removers: list[Callable[[], None]] = []

    def add(sentences: list[str], respond: Callable[..., Any]) -> None:
        if sentences:
            removers.append(agents.register_trigger(sentences, respond))

    def collect(build: Callable[[str], dict[str, list[str]]]) -> dict[str, list[str]]:
        per_topic: dict[str, list[str]] = {}
        for language in languages():
            for topic, sentences in build(language).items():
                per_topic.setdefault(topic, []).extend(sentences)
        return per_topic

    try:
        for child in manager.children(active_only=True):
            child_id = child["id"]
            names = _names(child)
            for topic, sentences in collect(lambda lang, names=names: child_sentences(names, lang)).items():

                async def respond_child(
                    user_input: Any, result: Any, topic: str = topic, child_id: str = child_id
                ) -> str:
                    return responder.child(user_input, child_id, topic)

                add(sentences, respond_child)
            for kind, sentences in collect(lambda lang, names=names: followup_sentences(lang, names)).items():

                async def respond_named(
                    user_input: Any, result: Any, kind: str = kind, child_id: str = child_id
                ) -> str:
                    return await responder.followup(user_input, kind, child_id)

                add(sentences, respond_named)
        for topic, sentences in collect(all_sentences).items():

            async def respond_all(user_input: Any, result: Any, topic: str = topic) -> str:
                return responder.all(user_input, topic)

            add(sentences, respond_all)
        for topic, sentences in collect(speaker_sentences).items():

            async def respond_speaker(user_input: Any, result: Any, topic: str = topic) -> str:
                return await responder.speaker(user_input, topic)

            add(sentences, respond_speaker)
        for kind, sentences in collect(followup_sentences).items():

            async def respond_followup(user_input: Any, result: Any, kind: str = kind) -> str:
                return await responder.followup(user_input, kind)

            add(sentences, respond_followup)
        for routine in manager.data["routines"]:
            if not routine.get("name"):
                continue
            routine_id = routine["id"]
            name = routine["name"]
            sentences = [
                s
                for items in collect(lambda lang, name=name: routine_sentences([name], lang)).values()
                for s in items
            ]

            async def respond_routine(
                user_input: Any, result: Any, routine_id: str = routine_id
            ) -> str:
                return answer_routine(manager, routine_id, responder._language(user_input))

            add(sentences, respond_routine)
        for cp_name in _checkpoint_names(manager):
            sentences = [
                s
                for items in collect(lambda lang, cp_name=cp_name: checkpoint_sentences([cp_name], lang)).values()
                for s in items
            ]

            async def respond_checkpoint(
                user_input: Any, result: Any, cp_name: str = cp_name
            ) -> str:
                return answer_checkpoint_tasks(manager, cp_name, responder._language(user_input))

            add(sentences, respond_checkpoint)
    except Exception:  # a changed agent API only loses the sentences
        _LOGGER.warning("Kis Segítő: the Assist sentences could not be added", exc_info=True)
    return removers


# ---------------------------------------------------------------- intent


class ChildStatusIntent(intent.IntentHandler):
    """Read-only: what Kis Segítő knows about the children (for LLM agents)."""

    intent_type = INTENT_CHILD_STATUS
    description = (
        "Kis Segítő (children's routine helper): a child's tokens, current task, "
        "tasks left today, next checkpoint, next routine, tokens still to earn "
        "today and streak. Leave out the name to get every child; set speaker "
        "when a child asks about themselves (\"my tokens\"). Times come in "
        "spoken form too (the *_spoken fields): say them as they are. Read only."
    )
    slot_schema: ClassVar[dict[Any, Any]] = {
        vol.Optional("name"): str,
        vol.Optional("topic"): vol.In(TOPICS),
        vol.Optional("speaker"): bool,
    }

    def __init__(self, manager: KisSegitoManager) -> None:
        self.manager = manager

    def _data(self, child: dict[str, Any], language: str) -> dict[str, Any]:
        data = child_status(self.manager, child["id"])
        data["aliases"] = _names(child)[1:]
        values = _values(data, language)
        data["next_checkpoint_time_spoken"] = values.get("cp_clock")
        data["next_checkpoint_in_spoken"] = values.get("cp_in")
        data["next_routine_time_spoken"] = values.get("start_clock")
        return data

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        slots = self.async_validate_slots(intent_obj.slots)
        topic = slots.get("topic", {}).get("value", "all")
        name = str(slots.get("name", {}).get("value") or "").strip()
        language = intent_obj.language or "en"
        response = intent_obj.create_response()
        if slots.get("speaker", {}).get("value") and not name:
            # The satellite's children, or every child: never one guessed.
            children = assigned_children(
                intent_obj.hass,
                self.manager,
                getattr(intent_obj, "device_id", None),
                getattr(intent_obj, "satellite_id", None),
            ) or self.manager.children(active_only=True)
            if len(children) == 1:
                status = child_status(self.manager, children[0]["id"])
                response.async_set_speech(answer(status, topic, language, "speaker"))
                response.async_set_speech_slots(self._data(children[0], language))
            else:
                response.async_set_speech(
                    answer_children(self.manager, topic, language, children)
                )
                response.async_set_speech_slots(
                    {"children": [self._data(c, language) for c in children]}
                )
            return response
        response.async_set_speech(answer_for(self.manager, name, topic, language))
        if name:
            child = find_child(self.manager, name)
            if child is not None:
                response.async_set_speech_slots(self._data(child, language))
        else:
            response.async_set_speech_slots(
                {
                    "children": [
                        self._data(c, language)
                        for c in self.manager.children(active_only=True)
                    ]
                }
            )
        return response


@callback
def async_setup_assist(
    hass: HomeAssistant, manager: KisSegitoManager
) -> Callable[[], None]:
    """Add the intent and, once Home Assistant runs, the sentences (added
    again when a child's names, a routine or a checkpoint change)."""
    intent.async_register(hass, ChildStatusIntent(manager))
    responder = Responder(hass, manager)
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
        sentences.extend(_register_sentences(hass, manager, responder))

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
