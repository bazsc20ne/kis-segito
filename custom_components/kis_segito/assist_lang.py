# SPDX-License-Identifier: AGPL-3.0-only
"""The languages of the Assist answers and sentences.

The texts are in assist_translations/<language>.json: the sentences the
built-in agent understands ("sentences"), the answers ("answers") and the
nouns that follow a number ("nouns"). A new language needs only a new file.

What a language's grammar needs beyond the texts is a small class here
(Hungarian name endings, numbers and times in words). A language without
one gets numbers as digits and its names as they are.
"""

from __future__ import annotations

import json
import random
import string
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from .assist_words import (
    en_clock,
    en_in,
    en_number,
    hu_all_forms,
    hu_article,
    hu_clock,
    hu_forms,
    hu_in,
    hu_number,
)

TEXTS_DIR = Path(__file__).parent / "assist_translations"
FALLBACK = "en"

_texts: dict[str, dict[str, Any]] = {}


def load() -> None:
    """Read every language file (in the executor: it reads files)."""
    _texts.clear()
    for path in sorted(TEXTS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            _texts[path.stem] = json.load(file)


def languages() -> list[str]:
    return list(_texts)


def texts(language: str) -> dict[str, Any]:
    """The texts of a language ("hu-HU" uses hu), English when missing."""
    code = (language or FALLBACK).lower().split("-")[0].split("_")[0]
    return _texts.get(code) or _texts.get(FALLBACK, {})


def language_of(language: str) -> str:
    code = (language or FALLBACK).lower().split("-")[0].split("_")[0]
    return code if code in _texts else FALLBACK


def plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# ---------------------------------------------------------------- grammar


class Grammar:
    """A language without its own grammar class: digits, names as they are."""

    def number(self, n: int) -> str:
        return str(n)

    def count(self, n: int, noun: Any) -> str:
        if isinstance(noun, list):
            noun = noun[0] if n == 1 else noun[-1]
        return f"{self.number(n)} {noun}".strip()

    def clock(self, when: datetime) -> str:
        return when.strftime("%H:%M")

    def until(self, minutes: int) -> str:
        return str(minutes)

    def name_words(self, names: list[str]) -> dict[str, list[str]]:
        """The forms of a child's names for the sentence placeholders."""
        return {"<N>": names, "<NX>": names}

    def routine_words(self, names: list[str]) -> dict[str, list[str]]:
        return {"<R>": names, "<RF>": names}

    def name_values(self, name: str) -> dict[str, str]:
        """The forms of a child's name for the answers."""
        return {"name": name, "name_dat": name}

    def phrase_values(self, routine: str, task: str, checkpoint: str) -> dict[str, str]:
        """Routine, task and checkpoint names as the answers use them."""
        values = {"routine": routine, "task": task, "cp": checkpoint}
        for key in ("routine_at", "routine_acc", "routine_gen", "routine_from", "routine_nom"):
            values[key] = routine
        values["task_art"] = task
        values["cp_art"] = checkpoint
        return values


class English(Grammar):
    def number(self, n: int) -> str:
        return en_number(n)

    def clock(self, when: datetime) -> str:
        return en_clock(when)

    def until(self, minutes: int) -> str:
        return en_in(minutes)

    def name_words(self, names: list[str]) -> dict[str, list[str]]:
        return {
            "<N>": names,
            "<NX>": names,
            "<NS>": [f"{n}'s" for n in names] + [f"{n}s" for n in names],
        }


class Hungarian(Grammar):
    def number(self, n: int) -> str:
        return hu_number(n)

    def count(self, n: int, noun: Any) -> str:
        # A noun after a number stays singular ("két zseton").
        if isinstance(noun, list):
            noun = noun[0]
        return f"{hu_number(n)} {noun}"

    def clock(self, when: datetime) -> str:
        return hu_clock(when)

    def until(self, minutes: int) -> str:
        return hu_in(minutes)

    def name_words(self, names: list[str]) -> dict[str, list[str]]:
        forms = [hu_all_forms(n) for n in names]

        def pick(*kinds: str) -> list[str]:
            return [w for f in forms for k in kinds for w in f[k]]

        return {
            "<NX>": pick("base", "dative", "adessive", "possessive"),
            "<ND>": pick("dative"),
            "<NA>": pick("adessive"),
            "<NE>": pick("possessive"),
            "<N>": pick("base"),
        }

    @staticmethod
    def _routine_base(name: str) -> str:
        """A routine's name with "rutin" (not twice: "Esti rutin")."""
        return name if name.casefold().endswith("rutin") else f"{name} rutin"

    def routine_words(self, names: list[str]) -> dict[str, list[str]]:
        words = []
        for name in names:
            words.append(self._routine_base(name) + "ból")
            back = hu_forms(name)["dative"].endswith("nak")
            words.append(name + ("ból" if back else "ből"))
        return {"<R>": names, "<RF>": words}

    def name_values(self, name: str) -> dict[str, str]:
        return {"name": name, "name_dat": hu_forms(name)["dative"]}

    def phrase_values(self, routine: str, task: str, checkpoint: str) -> dict[str, str]:
        base = self._routine_base(routine) if routine else ""
        art = hu_article(base) if base else ""
        return {
            "routine": routine,
            "routine_at": f"{art} {base}nál",
            "routine_acc": f"{art} {base}t",
            "routine_gen": f"{art} {base}",
            "routine_from": f"{art} {base}ból",
            "routine_nom": f"{art} {base}",
            "task": task,
            "task_art": f"{hu_article(task)} {task}" if task else "",
            "cp": checkpoint,
            "cp_art": f"{hu_article(checkpoint)} {checkpoint}" if checkpoint else "",
        }


GRAMMARS: dict[str, Grammar] = {"en": English(), "hu": Hungarian()}


def grammar(language: str) -> Grammar:
    return GRAMMARS.get(language_of(language), Grammar())


# ---------------------------------------------------------------- answers


class _Formatter(string.Formatter):
    """{value:noun} is a number followed by that noun, {value:num} the number
    alone, in the language's words."""

    def __init__(self, gram: Grammar, nouns: dict[str, Any]) -> None:
        self.gram = gram
        self.nouns = nouns

    def format_field(self, value: Any, format_spec: str) -> str:
        if format_spec == "num":
            return self.gram.number(int(value))
        if format_spec:
            return self.gram.count(int(value), self.nouns.get(format_spec, format_spec))
        return str(value)


def _capitalise(text: str) -> str:
    """Every sentence starts with a capital letter."""
    out = []
    upper = True
    for char in text:
        if upper and char.isalpha():
            out.append(char.upper())
            upper = False
        else:
            out.append(char)
        if char in ".!?":
            upper = True
    return "".join(out)


def say(language: str, topic: str, case: str, **values: Any) -> str:
    """One answer sentence, a wording chosen at random."""
    lang_texts = texts(language)
    options = lang_texts.get("answers", {}).get(topic, {}).get(case)
    if not options:
        options = texts(FALLBACK).get("answers", {}).get(topic, {}).get(case, [""])
    formatter = _Formatter(grammar(language), lang_texts.get("nouns", {}))
    text = formatter.format(random.choice(options), **values)
    return _capitalise(" ".join(text.split()))

load()
