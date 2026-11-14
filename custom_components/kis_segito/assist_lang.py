# SPDX-License-Identifier: AGPL-3.0-only
"""The languages of the Assist answers and sentences.

The texts are in assist_translations/<language>.json:

- "prefix": optional filler words put in front of every sentence;
- "words": placeholders for words that stand for the same thing;
- "sentences": what the built-in agent understands, by scope and topic;
- "nouns": the nouns that follow a number ({wallet:token});
- "lists": how lists are joined; "groups": words for every child at once;
- "answers": the answers, by scope, topic and case, each with a few wordings.

A new language needs only a new file. What a language's grammar needs beyond
the texts is a small class here (Hungarian name endings, numbers and times in
words). A language without one gets numbers as digits and its names as they
are.
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
# The wording used last for each answer, so the next one is a different one.
_last: dict[tuple[str, ...], int] = {}


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

    def number(self, n: int, attributive: bool = True) -> str:
        return str(n)

    def article_number(self, n: int) -> str:
        """A number with the article it takes ("az öt")."""
        return self.number(n)

    def count(self, n: int, noun: Any) -> str:
        if isinstance(noun, list):
            noun = noun[0] if n == 1 else noun[-1]
        return f"{self.number(n)} {noun}".strip()

    def clock(self, when: datetime) -> str:
        return when.strftime("%H:%M")

    def until(self, minutes: int) -> str:
        """How long until something ("in half an hour")."""
        return str(minutes)

    def span(self, minutes: int) -> str:
        """The same length without "in" ("half an hour")."""
        return str(minutes)

    def name_words(self, names: list[str]) -> dict[str, list[str]]:
        """The forms of a child's names for the sentence placeholders."""
        return {"<N>": names, "<NX>": names}

    def routine_words(self, names: list[str]) -> dict[str, list[str]]:
        return {"<R>": names, "<RF>": names}

    def checkpoint_words(self, names: list[str]) -> dict[str, list[str]]:
        return {"<C>": names, "<CI>": names}

    def name_values(self, name: str) -> dict[str, str]:
        """The forms of a child's name for the answers."""
        return {"name": name, "name_dat": name, "name_s": name}

    def label(self, text: str) -> str:
        """A label made by the user with its article, never suffixed."""
        return text

    def phrase_values(self, routine: str, task: str, checkpoint: str) -> dict[str, str]:
        """Routine, task and checkpoint names as the answers use them."""
        values = {
            "routine": routine,
            "routine_art": self.label(routine),
            "task": task,
            "task_art": self.label(task),
            "cp": checkpoint,
            "cp_art": self.label(checkpoint),
        }
        for key in ("routine_at", "routine_acc", "routine_gen", "routine_from", "routine_nom"):
            values[key] = routine
        return values


class English(Grammar):
    def number(self, n: int, attributive: bool = True) -> str:
        return en_number(n)

    def clock(self, when: datetime) -> str:
        return en_clock(when)

    def until(self, minutes: int) -> str:
        return en_in(minutes)

    def span(self, minutes: int) -> str:
        return en_in(minutes).removeprefix("in ")

    def name_words(self, names: list[str]) -> dict[str, list[str]]:
        return {
            "<N>": names,
            "<NX>": names,
            "<NS>": [f"{n}'s" for n in names] + [f"{n}s" for n in names],
        }

    def name_values(self, name: str) -> dict[str, str]:
        possessive = f"{name}'" if name.endswith("s") else f"{name}'s"
        return {"name": name, "name_dat": name, "name_s": possessive}


class Hungarian(Grammar):
    def number(self, n: int, attributive: bool = True) -> str:
        return hu_number(n, attributive)

    def article_number(self, n: int) -> str:
        word = hu_number(n)
        return f"{hu_article(word)} {word}"

    def count(self, n: int, noun: Any) -> str:
        # A noun after a number stays singular ("két zseton").
        if isinstance(noun, list):
            noun = noun[0]
        return f"{hu_number(n)} {noun}"

    def clock(self, when: datetime) -> str:
        return hu_clock(when)

    def until(self, minutes: int) -> str:
        return hu_in(minutes)

    def span(self, minutes: int) -> str:
        return hu_in(minutes).removesuffix(" múlva")

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

    def checkpoint_words(self, names: list[str]) -> dict[str, list[str]]:
        # In (-ban/-ben), with both vowel harmonies, as the speaker may say it.
        inside = [hu_forms(n)["dative"][:-3] + end for n in names for end in ("ban", "ben")]
        return {"<C>": names, "<CI>": inside}

    def name_values(self, name: str) -> dict[str, str]:
        return {"name": name, "name_dat": hu_forms(name)["dative"], "name_s": name}

    def label(self, text: str) -> str:
        return f"{hu_article(text)} {text}" if text else ""

    def phrase_values(self, routine: str, task: str, checkpoint: str) -> dict[str, str]:
        base = self._routine_base(routine) if routine else ""
        art = hu_article(base) if base else ""
        return super().phrase_values(routine, task, checkpoint) | {
            "routine_at": f"{art} {base}nál",
            "routine_acc": f"{art} {base}t",
            "routine_gen": f"{art} {base}",
            "routine_from": f"{art} {base}ból",
            "routine_nom": f"{art} {base}",
        }


GRAMMARS: dict[str, Grammar] = {"en": English(), "hu": Hungarian()}


def grammar(language: str) -> Grammar:
    return GRAMMARS.get(language_of(language), Grammar())


# ---------------------------------------------------------------- lists


def join(language: str, items: list[str]) -> str:
    """Items joined as the language does it ("a, b és c"); more than five:
    the first three and how many more."""
    items = [i for i in items if i]
    lists = texts(language).get("lists", {})
    sep = lists.get("sep", ", ")
    last = lists.get("last", " & ")
    if len(items) > 5 and lists.get("more"):
        formatter = _Formatter(grammar(language), texts(language).get("nouns", {}))
        return formatter.format(lists["more"], items=sep.join(items[:3]), more=len(items) - 3)
    if len(items) < 2:
        return "".join(items)
    return sep.join(items[:-1]) + last + items[-1]


def group(language: str, key: str, count: int) -> str:
    """A word for every child at once ("mindkét gyereknek", "both kids")."""
    words = texts(language).get("groups", {}).get(key, {})
    return words.get(str(count)) or words.get("other", "")


# ---------------------------------------------------------------- answers


class _Formatter(string.Formatter):
    """{value:noun} is a number followed by that noun, {value:num} the number
    alone, {value:alone} the number standing without a noun ("kettő"),
    {value:art} the number with its article, in the language's words."""

    def __init__(self, gram: Grammar, nouns: dict[str, Any]) -> None:
        self.gram = gram
        self.nouns = nouns

    def format_field(self, value: Any, format_spec: str) -> str:
        if format_spec == "num":
            return self.gram.number(int(value))
        if format_spec == "alone":
            return self.gram.number(int(value), False)
        if format_spec == "art":
            return self.gram.article_number(int(value))
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


def wordings(language: str, *path: str) -> list[str]:
    """The wordings of an answer (English when the language lacks it)."""

    def find(lang_texts: dict[str, Any]) -> list[str]:
        node: Any = lang_texts.get("answers", {})
        for key in path:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        return node if isinstance(node, list) else []

    return find(texts(language)) or find(texts(FALLBACK))


def has(language: str, *path: str) -> bool:
    return bool(wordings(language, *path))


def pick(language: str, *path: str) -> int:
    """A wording of an answer chosen at random, not the one used last time."""
    count = len(wordings(language, *path)) or 1
    key = (language_of(language), *path)
    choices = [i for i in range(count) if i != _last.get(key)] or [0]
    index = random.choice(choices)
    _last[key] = index
    return index


def say(language: str, *path: str, variant: int | None = None, **values: Any) -> str:
    """One answer sentence: a wording chosen at random, not the one used last
    time for the same answer. The path is scope, topic and case
    ("child", "tokens", "wallet"); ``variant`` asks for one wording (the
    items of a list use matching wordings)."""
    options = wordings(language, *path) or [""]
    index = pick(language, *path) if variant is None else variant % len(options)
    formatter = _Formatter(grammar(language), texts(language).get("nouns", {}))
    text = formatter.format(options[index], **values)
    return _capitalise(" ".join(text.split()))


def sentence(text: str) -> str:
    """A piece of text as a finished, capitalised sentence."""
    text = " ".join(text.split())
    if text and text[-1] not in ".!?":
        text += "."
    return _capitalise(text)


load()
