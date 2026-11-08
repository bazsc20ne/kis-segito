# SPDX-License-Identifier: AGPL-3.0-only
"""Sentences the built-in Assist agent understands, from the language files
(assist_translations/<language>.json, "sentences"), in Home Assistant's
sentence syntax: (a|b) alternatives, [x] optional words, (a;b) any order.

"words" are placeholders for words that stand for the same thing. Sentences
about one child ("child") carry the child's names in every form the
language's grammar knows (<N>, <NX>, <ND> … in assist_lang.py); sentences
without a name ("all") answer for every child; "routine" sentences name a
routine (<R>, <RF>).
"""

from __future__ import annotations

from .assist_lang import grammar, plain, texts


def _clean(name: str) -> str:
    """A name usable in a sentence (no characters of the sentence syntax)."""
    return " ".join("".join(c for c in name if c not in "()[]{}<>|;").split())


def _alternatives(words: list[str]) -> str:
    unique = sorted({w for w in words if w}, key=str.casefold)
    return "(" + "|".join(unique) + ")"


def _names(names: list[str]) -> list[str]:
    cleaned = [n for n in (_clean(x) for x in names) if n]
    return list(dict.fromkeys(cleaned + [plain(n) for n in cleaned]))


def _fill(sentence: str, values: dict[str, str]) -> str:
    # Longer placeholders first (<NX> before <N>).
    for key in sorted(values, key=len, reverse=True):
        sentence = sentence.replace(key, values[key])
    return sentence


def _build(language: str, group: str, values: dict[str, str]) -> dict[str, list[str]]:
    sentences = texts(language).get("sentences", {})
    words = sentences.get("words", {}) | values
    return {
        topic: [_fill(s, words) for s in items]
        for topic, items in sentences.get(group, {}).items()
    }


def child_sentences(names: list[str], language: str) -> dict[str, list[str]]:
    """The sentences about one child, by topic, for its names."""
    forms = grammar(language).name_words(_names(names))
    return _build(language, "child", {k: _alternatives(v) for k, v in forms.items()})


def all_sentences(language: str) -> dict[str, list[str]]:
    """The sentences without a name, by topic."""
    return _build(language, "all", {})


def routine_sentences(names: list[str], language: str) -> dict[str, list[str]]:
    """The sentences about one routine, by topic, for its name."""
    forms = grammar(language).routine_words(_names(names))
    return _build(language, "routine", {k: _alternatives(v) for k, v in forms.items()})
