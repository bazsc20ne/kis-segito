# SPDX-License-Identifier: AGPL-3.0-only
"""Sentences the built-in Assist agent understands, from the language files
(assist_translations/<language>.json, "sentences"), in Home Assistant's
sentence syntax: (a|b) alternatives, [x] optional words, (a;b) any order.

"words" are placeholders for words that stand for the same thing, and
"prefix" (optional filler words such as "um" or "és") goes in front of every
sentence. The scopes:

- "child": about one child, with the child's names in every form the
  language's grammar knows (<N>, <NX>, <ND> … in assist_lang.py);
- "all": without a name, for every child;
- "speaker": in the first person, for the child who is speaking;
- "followup": short follow-ups that reuse the previous question's topic
  ("speaker", "child", "all"; "…_amount" ones ask how many, so they ask
  about tokens when there was no question before), and "identify" (a child
  saying their name);
- "routine": about one routine (<R>, <RF>);
- "checkpoint": about one checkpoint (<C>, <CI>).
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


def _build(
    language: str, scope: str, values: dict[str, str]
) -> dict[str, list[str]]:
    lang_texts = texts(language)
    words = lang_texts.get("words", {}) | values
    prefix = lang_texts.get("prefix", "")
    return {
        topic: [f"{prefix} {_fill(s, words)}".strip() for s in items]
        for topic, items in lang_texts.get("sentences", {}).get(scope, {}).items()
    }


def child_sentences(names: list[str], language: str) -> dict[str, list[str]]:
    """The sentences about one child, by topic, for its names."""
    forms = grammar(language).name_words(_names(names))
    return _build(language, "child", {k: _alternatives(v) for k, v in forms.items()})


def all_sentences(language: str) -> dict[str, list[str]]:
    """The sentences without a name, by topic."""
    return _build(language, "all", {})


def speaker_sentences(language: str) -> dict[str, list[str]]:
    """The sentences in the first person, by topic."""
    return _build(language, "speaker", {})


def followup_sentences(
    language: str, names: list[str] | None = None
) -> dict[str, list[str]]:
    """The follow-ups: with a child's names "child" and "identify", without
    them "speaker" and "all"."""
    values: dict[str, str] = {}
    if names is not None:
        forms = grammar(language).name_words(_names(names))
        values = {k: _alternatives(v) for k, v in forms.items()}
    built = _build(language, "followup", values)
    named = ("child", "identify")
    return {
        kind: items
        for kind, items in built.items()
        if (kind.split("_")[0] in named) == (names is not None)
    }


def routine_sentences(names: list[str], language: str) -> dict[str, list[str]]:
    """The sentences about one routine, by topic, for its name."""
    forms = grammar(language).routine_words(_names(names))
    return _build(language, "routine", {k: _alternatives(v) for k, v in forms.items()})


def checkpoint_sentences(names: list[str], language: str) -> dict[str, list[str]]:
    """The sentences about one checkpoint, by topic, for its name."""
    forms = grammar(language).checkpoint_words(_names(names))
    return _build(language, "checkpoint", {k: _alternatives(v) for k, v in forms.items()})
