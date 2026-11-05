# SPDX-License-Identifier: AGPL-3.0-only
"""Sentences the built-in Assist agent understands, in Hungarian and English
(Home Assistant's sentence syntax: (a|b) alternatives, [x] optional words,
(a;b) any order).

Sentences about one child use the child's names (name and other names, also
without accents) in every form: <N> base, <ND> -nak/-nek, <NA> -nál/-nél,
<NE> -é, <NX> any of them. Sentences without a name answer for every child.
Common speech-recognition mishearings (jeton, csekkpont, mennyei) are listed
as words of their own, so no setup of the assistant is needed.
"""

from __future__ import annotations

import unicodedata

from .assist_words import hu_all_forms

# Words that stand for the same thing.
_HU = {
    "<MENNYI>": "(mennyi|mennyei|menyi|hány|hányat|mekkora)",
    "<ZS>": (
        "(zseton|zsetonja|zsetonjai|zsetont|zsetonok|zsetonod|zsetonjuk|zsetom|zsetonya"
        "|jeton|jetonja|jetont|jetonok|érme|érméje|érméi|érmét|érmék"
        "|pénz|pénze|pénzt|pont|pontja|pontot|pontjai|pontok|tallér|tallérja)"
    ),
    "<EGYENLEG>": "(egyenleg|egyenlege|egyenlegét|egyenlegük|kassza|kasszája)",
    "<KP>": (
        "(ellenőrzőpont|ellenőrzőpontja|ellenőrző pont|ellenőrző pontja"
        "|csekkpont|csekkpontja|csekk pont|csekk pontja|check pont|check pontja"
        "|checkpoint|checkpointja|határidő|határideje)"
    ),
    "<KP0>": (
        "(ellenőrzőpont|ellenőrző pont|csekkpont|csekk pont|check pont|checkpoint)"
    ),
    "<KPIG0>": (
        "(ellenőrzőpontig|ellenőrző pontig|csekkpontig|csekk pontig|check pontig"
        "|checkpointig)"
    ),
    "<KPIG>": (
        "(ellenőrzőpontig|ellenőrzőpontjáig|ellenőrző pontig|ellenőrző pontjáig"
        "|csekkpontig|csekkpontjáig|csekk pontig|csekk pontjáig|check pontig"
        "|checkpointig|checkpointjáig|határidőig|határidejéig)"
    ),
    "<FELADAT>": (
        "(feladat|feladata|feladatai|feladatok|teendő|teendője|teendői|teendők"
        "|dolga|tennivalója|tennivalók)"
    ),
    "<SOROZAT>": "(sorozat|sorozata|sorozatja|szériája|széria)",
    "<KAPHAT>": "(kaphat|szerezhet|gyűjthet|kereshet|nyerhet|kap|szerez)",
    "<KAPHATNAK>": "(kaphatnak|szerezhetnek|gyűjthetnek|kereshetnek|kapnak)",
    "<MOST>": "[most|éppen|épp|jelenleg|ma]",
    "<MEG>": "[még]",
    "<MA>": "[ma|mára|a mai napon]",
    "<KOVETKEZO>": "(következő|következö|kovetkezo|legközelebbi)",
    "<MINDENKI>": (
        "(mindenkinek|kinek|kiknek|a gyerekeknek|a gyerekeknél|gyerekeknek|valakinek"
        "|mindenkinél|kinél)"
    ),
}

# Sentences per topic about one child (Hungarian).
HU_CHILD: dict[str, list[str]] = {
    "tokens": [
        "(<MENNYI> <ZS>; [van|vannak] [még] [neki]; <NX>)",
        "(<MENNYI> <ZS>; [van] [a] [pénztárcájában|perselyében|perselyben]; <NX>)",
        "(<MENNYI>|mi|mondd meg|mondd) [a|az] <N> <EGYENLEG>",
        "[a|az] <N> <EGYENLEG>",
        "(<ND>|<N>) (mennyi|mennyei|hány) (van|maradt)",
        "[a|az] <N> (zsetonjai|zsetonja|pénze|pontjai|pontja|érméi)",
        "(van|vannak) [még] <ZS> <NX>",
        "<NX> (van|vannak) [még] <ZS>",
        "(<MENNYI> <ZS>; van [a|az] <N> perselyében)",
        "(<MENNYI> <ZS>; van <ND> [a] perselyében)",
    ],
    "task": [
        "(van|lesz) <MOST> <FELADAT> <NX>",
        "<NX> (van|lesz) <MOST> <FELADAT>",
        "(mi|mik) [a|az] <N> <FELADAT> <MOST>",
        "(mi|mik) (a|az) <FELADAT> <NX> <MOST>",
        "(mi|mik) <NX> <FELADAT> <MOST>",
        "<NX> (mi|mik) [a|az] <FELADAT> <MOST>",
        "(mit;kell;<MOST>;(csinálnia|tennie);<NX>)",
        "(mit;csinál;<MOST>;<NX>)",
        "(mivel;tart;<MOST>;[a|az] <N>)",
        "(van;<MOST>;dolga;<NX>)",
    ],
    "checkpoint": [
        "(mikor;(van|lesz|jön);[a|az] <N> <KOVETKEZO> <KP>)",
        "(mikor;(van|lesz|jön);[a|az] <KOVETKEZO> <KP>;<NX>)",
        "(mikor;(van|lesz|jön);<ND> [a|az] <KOVETKEZO> <KP>)",
        "(mennyi idő;van <MEG>;[a|az] <N> <KOVETKEZO> <KPIG>)",
        "(mennyi ideje;van <MEG>;(<ND>|<N>);[a|az] <KOVETKEZO> <KPIG>)",
        "(meddig;van <MEG>;ideje;(<ND>|<N>))",
        "[a|az] <N> <KOVETKEZO> <KP>",
        "(<ND>|<N>) <KOVETKEZO> <KP>",
        "(mikor;kell;<MEG>;(elkészülnie|kész lennie|végeznie);<NX>)",
    ],
    "earnable": [
        "(<MENNYI> <ZS>;<KAPHAT> <MEG> <MA>;<NX>)",
        "(<MENNYI> <ZS>;<KAPHAT> <MEG>;<NX>)",
        "(<MENNYI> <ZS>;jár <MEG> <MA>;<NX>)",
        "(mennyit;<KAPHAT> <MEG> <MA>;<NX>)",
    ],
    "streak": [
        "(<MENNYI>|milyen hosszú|milyen) [napos] [a|az] <N> <SOROZAT>",
        "[a|az] <N> <SOROZAT>",
        "(hány napja;(hibátlan|csinálja végig|ügyes|teljesít);<NX>)",
        "(hány;hibátlan napja;van;<NX>)",
        "(hogy|hogyan) áll [a|az] <N> <SOROZAT>",
    ],
}

# Sentences per topic without a name: every child (Hungarian).
HU_ALL: dict[str, list[str]] = {
    "tokens": [
        "<MINDENKI> (mennyi|mennyei|hány) <ZS> [van]",
        "(<MENNYI> <ZS>;van;<MINDENKI>)",
        "(<MENNYI> <ZS>;van;[a|az] (kis segítőben|kis segítőn|gyerekeknél))",
        "(hogy|hogyan) állnak a gyerekek",
        "(van;<MINDENKI>;[valamennyi] <ZS>;[a] (perselyében|perselyben))",
        "(kinek;van;[a legtöbb] <ZS>)",
        "kinek mennyi (van|maradt)",
        "[mi] a gyerekek <EGYENLEG>",
        "(<MENNYI> <ZS>;van [összesen];a gyerekeknek)",
    ],
    "task": [
        "(kinek|kiknek|valakinek|mindenkinek) (van|lesz) <MOST> <FELADAT>",
        "(van|lesz) <MOST> (valakinek|kinek|a gyerekeknek) <FELADAT>",
        "(mi|mik) [a|az] <FELADAT> <MOST>",
        "(mit;kell;<MOST>;csinálni;[a gyerekeknek])",
        "(mi;a gyerekek;<FELADAT>;<MOST>)",
    ],
    "checkpoint": [
        "(mikor;(van|lesz|jön);[a|az] <KOVETKEZO> <KP0>)",
        "(mennyi idő;van <MEG>;[a|az] <KOVETKEZO> <KPIG0>)",
        "[mi] [a|az] <KOVETKEZO> <KP0>",
    ],
    "earnable": [
        "(<MENNYI> <ZS>;<KAPHATNAK> <MEG> <MA>;[a gyerekek])",
        "(ki;<MENNYI> <ZS>;<KAPHAT> <MEG> <MA>)",
        "(<MENNYI> <ZS>;jár <MEG> <MA>;a gyerekeknek)",
    ],
    "streak": [
        "(<MENNYI>|milyen hosszú) [napos] a (sorozat|sorozatuk|sorozatok)",
        "(hogy|hogyan) állnak a sorozatok",
        "(kinek;hány;hibátlan napja;van)",
    ],
}

_EN = {
    "<COINS>": "(coins|coin|tokens|token|points|money|chips)",
    "<CP>": "(checkpoint|check point|deadline)",
    "<NOW>": "[right now|now|at the moment|currently|today]",
}

EN_CHILD: dict[str, list[str]] = {
    "tokens": [
        "how many <COINS> (does|has) <N> (have|got)",
        "how many <COINS> has <N> got",
        "how much (money|coins|tokens) (does|has) <N> (have|got)",
        "(what is|what's|whats|tell me) <NS> (balance|wallet|piggy bank|savings)",
        "<NS> (balance|wallet|coins|tokens)",
        "(does|has) <N> (have|got) [any] <COINS>",
    ],
    "task": [
        "(does|has) <N> (have|got) (a task|anything to do|something to do|a job) <NOW>",
        "(what is|what's|whats) <NS> (task|job|next task) <NOW>",
        "what (does|should|must) <N> (do|be doing) <NOW>",
        "what is <N> (doing|supposed to do) <NOW>",
        "is <N> (busy|done) <NOW>",
    ],
    "checkpoint": [
        "(when is|when's|whens) <NS> next <CP>",
        "how long (until|till|before) <NS> next <CP>",
        "how much time (does|has) <N> (have|got) [left] [until the next <CP>]",
        "<NS> next <CP>",
    ],
    "earnable": [
        "how many <COINS> can <N> [still] (get|earn|win|collect) <NOW>",
        "how much can <N> [still] (get|earn) <NOW>",
    ],
    "streak": [
        "(what is|what's|whats|how long is) <NS> streak",
        "how many (perfect|good) days (does|has) <N> (have|got|had)",
        "<NS> streak",
    ],
}

EN_ALL: dict[str, list[str]] = {
    "tokens": [
        "how many <COINS> does (everyone|everybody) have",
        "how many <COINS> do the (kids|children) have",
        "who has how many <COINS>",
        "how are the (kids|children) doing",
        "(what are|what's) the (kids'|children's) balances",
        "does anyone have [any] <COINS> [in the piggy bank]",
    ],
    "task": [
        "(does|has) (anyone|anybody) (have|got) (a task|anything to do) <NOW>",
        "who has (a task|something to do) <NOW>",
        "what are the (tasks|jobs) <NOW>",
    ],
    "checkpoint": [
        "(when is|when's|whens) the next <CP>",
        "how long (until|till) the next <CP>",
    ],
    "earnable": [
        "how many <COINS> can the (kids|children) [still] (get|earn) <NOW>",
        "who can [still] (get|earn) how many <COINS> <NOW>",
    ],
    "streak": [
        "(what are|how long are) the streaks",
        "how are the streaks [going]",
    ],
}


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _clean(name: str) -> str:
    """A name usable in a sentence (no characters of the sentence syntax)."""
    return " ".join("".join(c for c in name if c not in "()[]{}<>|;").split())


def _alternatives(words: list[str]) -> str:
    unique = sorted({w for w in words if w}, key=str.casefold)
    return "(" + "|".join(unique) + ")"


def child_sentences(names: list[str], language: str) -> dict[str, list[str]]:
    """The sentences about one child, by topic, for its names."""
    names = [n for n in (_clean(x) for x in names) if n]
    names += [_plain(n) for n in names]
    if language == "hu":
        forms = [hu_all_forms(n) for n in dict.fromkeys(names)]

        def pick(*kinds: str) -> str:
            return _alternatives([w for f in forms for k in kinds for w in f[k]])

        values = {
            "<NX>": pick("base", "dative", "adessive", "possessive"),
            "<ND>": pick("dative"),
            "<NA>": pick("adessive"),
            "<NE>": pick("possessive"),
            "<N>": pick("base"),
        }
        templates, words = HU_CHILD, _HU
    else:
        values = {
            "<NS>": _alternatives([f"{n}'s" for n in names] + [f"{n}s" for n in names]),
            "<N>": _alternatives(names),
        }
        templates, words = EN_CHILD, _EN
    return {
        topic: [_fill(s, words | values) for s in sentences]
        for topic, sentences in templates.items()
    }


def all_sentences(language: str) -> dict[str, list[str]]:
    """The sentences without a name, by topic."""
    templates, words = (HU_ALL, _HU) if language == "hu" else (EN_ALL, _EN)
    return {
        topic: [_fill(s, words) for s in sentences]
        for topic, sentences in templates.items()
    }


def _fill(sentence: str, values: dict[str, str]) -> str:
    # Longer placeholders first (<NX> before <N>).
    for key in sorted(values, key=len, reverse=True):
        sentence = sentence.replace(key, values[key])
    return sentence
