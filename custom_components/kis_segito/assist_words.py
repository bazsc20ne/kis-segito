# SPDX-License-Identifier: AGPL-3.0-only
"""Words for spoken answers: numbers and times written out (so every
text-to-speech engine reads them right), and the Hungarian forms of names."""

from __future__ import annotations

import unicodedata
from datetime import datetime

# ---------------------------------------------------------------- Hungarian

_HU_ONES = ["", "egy", "kettő", "három", "négy", "öt", "hat", "hét", "nyolc", "kilenc"]
_HU_TENS = [
    "",
    "tíz",
    "húsz",
    "harminc",
    "negyven",
    "ötven",
    "hatvan",
    "hetven",
    "nyolcvan",
    "kilencven",
]
_HU_TENS_PREFIX = [
    "",
    "tizen",
    "huszon",
    "harminc",
    "negyven",
    "ötven",
    "hatvan",
    "hetven",
    "nyolcvan",
    "kilencven",
]


def _hu_below_thousand(n: int, attributive: bool) -> str:
    hundreds, rest = divmod(n, 100)
    tens, ones = divmod(rest, 10)
    words = ""
    if hundreds:
        words += ("" if hundreds == 1 else _hu_number_word(hundreds, True)) + "száz"
    if tens:
        words += _HU_TENS_PREFIX[tens] if ones else _HU_TENS[tens]
    if ones:
        words += "két" if ones == 2 and attributive else _HU_ONES[ones]
    return words


def _hu_number_word(n: int, attributive: bool) -> str:
    return "két" if n == 2 and attributive else _HU_ONES[n]


def hu_number(n: int, attributive: bool = True) -> str:
    """A whole number in Hungarian words ("két" before a noun, "kettő" alone)."""
    if n < 0:
        return "mínusz " + hu_number(-n, attributive)
    if n == 0:
        return "nulla"
    if n < 1000:
        return _hu_below_thousand(n, attributive)
    thousands, rest = divmod(n, 1000)
    head = ("" if thousands == 1 else _hu_below_thousand(thousands, True)) + "ezer"
    if not rest:
        return head
    # Above two thousand the parts are joined with a hyphen.
    joiner = "-" if n > 2000 else ""
    return head + joiner + _hu_below_thousand(rest, attributive)


def hu_article(word: str) -> str:
    """ "az" before a vowel, "a" otherwise."""
    first = _plain(word)[:1]
    return "az" if first in "aeiou" else "a"


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_BACK = set("aáoóuú")
_FRONT = set("eéiíöőüű")


def _back(word: str) -> bool:
    """Vowel harmony: back vowels take -nak/-nál, front ones -nek/-nél.

    The last vowel decides (Alex, hotel: front); i and í let the vowel before
    them decide (Ari, papír: back), and so does a final é (kávé: back).
    """
    vowels = [c for c in word.casefold() if c in _BACK or c in _FRONT]
    if not vowels:
        return True
    last = vowels[-1]
    if last in _BACK:
        return True
    if last in "ií" or (last == "é" and word.casefold().endswith("é")):
        before = [c for c in vowels[:-1] if c not in "ií"]
        return bool(before) and before[-1] in _BACK
    return False


def _stem(word: str) -> str:
    """A final a/e lengthens before a suffix (alma → almá-, kecske → kecské-)."""
    if word.endswith("a"):
        return word[:-1] + "á"
    if word.endswith("e"):
        return word[:-1] + "é"
    return word


def hu_forms(name: str) -> dict[str, str]:
    """A name and its forms: dative (-nak/-nek), adessive (-nál/-nél) and
    possessive (-é)."""
    back = _back(name)
    stem = _stem(name)
    return {
        "base": name,
        "dative": stem + ("nak" if back else "nek"),
        "adessive": stem + ("nál" if back else "nél"),
        "possessive": stem + "é",
    }


def hu_all_forms(name: str) -> dict[str, list[str]]:
    """Every form a speaker may use, also with the other vowel harmony
    (names do not always follow the rule)."""
    stem = _stem(name)
    return {
        "base": [name],
        "dative": [stem + "nak", stem + "nek"],
        "adessive": [stem + "nál", stem + "nél"],
        "possessive": [stem + "é"],
    }


def hu_day_part(when: datetime) -> str:
    """The part of the day a time is in (reggel, délután, este …)."""
    hour = when.hour
    if hour < 4:
        return "éjjel"
    if hour < 9:
        return "reggel"
    if hour < 12:
        return "délelőtt"
    if hour < 18:
        return "délután"
    if hour < 22:
        return "este"
    return "éjjel"


def hu_clock(when: datetime) -> str:
    """A time of day as people say it, with the part of the day and "-kor"
    (reggel fél nyolckor, este hét órakor)."""
    if when.hour == 12 and when.minute == 0:
        return "délben"
    if when.hour == 0 and when.minute == 0:
        return "éjfélkor"
    hour = when.hour % 12 or 12
    nxt = hour % 12 + 1
    minute = when.minute
    if minute == 0:
        text = f"{hu_number(hour, False)} órakor"
    elif minute == 15:
        text = f"negyed {hu_number(nxt, False)}kor"
    elif minute == 30:
        text = f"fél {hu_number(nxt, False)}kor"
    elif minute == 45:
        text = f"háromnegyed {hu_number(nxt, False)}kor"
    else:
        text = f"{hu_number(hour, True)} óra {hu_number(minute, True)} perckor"
    return f"{hu_day_part(when)} {text}"


def hu_in(minutes: int) -> str:
    """How long until something, as people say it (negyed óra múlva)."""
    if minutes <= 0:
        return "most"
    named = {15: "negyed óra", 30: "fél óra", 45: "háromnegyed óra"}
    if minutes in named:
        return named[minutes] + " múlva"
    if minutes < 60:
        return f"{hu_number(minutes)} perc múlva"
    hours, rest = divmod(minutes, 60)
    text = f"{hu_number(hours)} óra"
    if rest:
        text += f" {hu_number(rest)} perc"
    return text + " múlva"


# ---------------------------------------------------------------- English

_EN_ONES = [
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_EN_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def _en_below_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_EN_ONES[hundreds]} hundred")
    if rest:
        if rest < 20:
            text = _EN_ONES[rest]
        else:
            tens, ones = divmod(rest, 10)
            text = _EN_TENS[tens] + (f"-{_EN_ONES[ones]}" if ones else "")
        parts.append(("and " if hundreds else "") + text)
    return " ".join(parts)


def en_number(n: int) -> str:
    """A whole number in English words."""
    if n < 0:
        return "minus " + en_number(-n)
    if n == 0:
        return "zero"
    if n < 1000:
        return _en_below_thousand(n)
    thousands, rest = divmod(n, 1000)
    text = f"{_en_below_thousand(thousands)} thousand"
    if rest:
        text += (" and " if rest < 100 else " ") + _en_below_thousand(rest)
    return text


def en_day_part(when: datetime) -> str:
    """The part of the day a time is in (in the morning, in the evening …)."""
    hour = when.hour
    if hour < 4 or hour >= 22:
        return "at night"
    if hour < 12:
        return "in the morning"
    if hour < 18:
        return "in the afternoon"
    return "in the evening"


def en_clock(when: datetime) -> str:
    """A time of day as people say it, with the part of the day
    (at half past seven in the morning, at seven in the evening)."""
    if when.hour == 12 and when.minute == 0:
        return "at noon"
    if when.hour == 0 and when.minute == 0:
        return "at midnight"
    hour = when.hour % 12 or 12
    nxt = hour % 12 + 1
    minute = when.minute
    if minute == 0:
        text = f"at {en_number(hour)}"
    elif minute == 15:
        text = f"at quarter past {en_number(hour)}"
    elif minute == 30:
        text = f"at half past {en_number(hour)}"
    elif minute == 45:
        text = f"at quarter to {en_number(nxt)}"
    else:
        tail = en_number(minute) if minute >= 10 else "oh " + en_number(minute)
        text = f"at {en_number(hour)} {tail}"
    # "quarter to" names the next hour: its part of the day decides.
    part_of = when.replace(hour=(when.hour + 1) % 24) if minute == 45 else when
    return f"{text} {en_day_part(part_of)}"


def en_in(minutes: int) -> str:
    """How long until something (in a quarter of an hour)."""
    if minutes <= 0:
        return "now"
    named = {15: "in a quarter of an hour", 30: "in half an hour", 60: "in an hour"}
    if minutes in named:
        return named[minutes]
    if minutes < 60:
        return f"in {en_number(minutes)} minute{'s' if minutes != 1 else ''}"
    hours, rest = divmod(minutes, 60)
    text = f"in {en_number(hours)} hour{'s' if hours != 1 else ''}"
    if rest:
        text += f" and {en_number(rest)} minute{'s' if rest != 1 else ''}"
    return text
