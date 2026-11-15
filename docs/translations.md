<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# Fordítások / Translations

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>
## Magyar

A Kis Segítő a Home Assistant nyelvén mutatja a szövegeit (angol és magyar van
benne; ha egy nyelvhez nincs fordítás, angolul). Új nyelvhez csak fordítási
fájlok kellenek, részenként egy, a Home Assistant nyelvkódjával elnevezve (pl.
`de.json`), a `custom_components/kis_segito/` mappán belül:

1. `translations/` – a beállítás és magának a Home Assistantnek a szövegei
2. `frontend/translations/` – a panel
3. `device_translations/` – a gomb kijelzője
4. `notification_translations/` – az értesítések üzenetei

A hiányzó szövegek angolul jelennek meg. A gomb betűkészletei a latin és a
cirill betűket tartalmazzák (a görögöt nem). A logónak két változata van: magyar
nyelvhez magyar, minden más nyelvhez angol („Little Helper”).

---

<a id="english"></a>
## English

🇭🇺 [Magyar változat](#magyar)

Little Helper shows its texts in the Home Assistant language (English and Hungarian
are included; English when a language has no translation). A new language needs
only translation files, one per part, named by the Home Assistant language code
(e.g. `de.json`), in `custom_components/kis_segito/`:

1. `translations/` – texts of the setup and of Home Assistant itself
2. `frontend/translations/` – the panel
3. `device_translations/` – the knob's display
4. `notification_translations/` – notification messages

Missing texts fall back to English. The knob's fonts cover Latin and Cyrillic
letters (not Greek). The logo exists in two variants: Hungarian for Hungarian and
English ("Little Helper") for every other language.
