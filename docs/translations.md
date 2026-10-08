<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# Translations / Fordítások

Kis Segítő shows its texts in the Home Assistant language (English and Hungarian
are included; English when a language has no translation). A new language needs
only translation files, one per part, named by the Home Assistant language code
(e.g. `de.json`), in `custom_components/kis_segito/`:

1. `translations/` – texts of the setup and of Home Assistant itself
2. `frontend/translations/` – the panel
3. `device_translations/` – the knob's display
4. `notification_translations/` – notification messages

Missing texts fall back to English. The knob's fonts cover Latin, Greek and
Cyrillic letters. The logo exists in two variants: Hungarian for Hungarian and
English ("Little Helper") for every other language.

A Kis Segítő a Home Assistant nyelvén mutatja a szövegeit (angol és magyar van
benne; ha egy nyelvhez nincs fordítás, angolul). Új nyelvhez csak fordítási
fájlok kellenek, részenként egy, a Home Assistant nyelvkódjával elnevezve (pl.
`de.json`), a fenti mappákban. A hiányzó szövegek angolul jelennek meg. A logónak
két változata van: magyar nyelvhez magyar, minden más nyelvhez angol.
