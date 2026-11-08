<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Board profiles / Gombprofilok

The knob firmware has three parts:

- **Core** (`esphome/kis-segito-core.yaml`): the Kis Segítő software – child
  screen, screen power, sensor inputs, night light, Home Assistant connection.
  It does not know the hardware.
- **Board profile**: the hardware of one knob – display, backlight, chip and
  memory settings, and its input hardware (encoder, buttons).
- **Input profile** (`esphome/inputs/`): turns the input hardware into the
  core's generic inputs.

`esphome/kis-segito.yaml` is the core together with the tested profile of the
VIEWE UEDX48480021-MD80E knob (`esphome/hardware/board.yaml`) and its input
profile (`esphome/inputs/encoder-button.yaml`). With that knob nothing changes:
keep using `kis-segito.yaml` as in `esphome/example.yaml`.

## Your own knob

Write a profile for it and include it next to the core and an input profile:

```yaml
substitutions:
  screen_size: "360"
packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito-core.yaml@v0.9.9
  input: github://bazsc20ne/kis-segito/esphome/inputs/encoder-button.yaml@v0.9.9
  board: !include my-board.yaml
```

The board profile must provide:

| ID / substitution | What |
|---|---|
| `knob_display` | The round display, used by LVGL. |
| `backlight` | A `light` that switches and dims the display backlight. |
| `screen_size` | Substitution: width and height of the display in pixels – `240`, `360`, `466` or `480`. |

and everything the chip needs: `esp32` (with the framework), `psram` and
`logger`. Use `esphome/hardware/board.yaml` as an example.

### Screen sizes

The child screen is laid out for 480×480 pixels and scaled to `screen_size`:
positions, sizes, texts and the built-in pictures are made for that size when
the firmware is built, and the pictures from Home Assistant (icons, avatars,
backgrounds) are downloaded at that size.

### Inputs

The core is driven by five generic inputs (ESPHome scripts): `input_next`,
`input_previous`, `input_select`, `input_back` (a long press: back one level)
and `input_wake`. While the screen is dimmed, dark or shows the screensaver,
each of them only wakes it. Any input hardware can call them, e.g.
`on_press: - script.execute: input_next`.

The input profiles in `esphome/inputs/`:

- `encoder-button.yaml`: a rotary encoder with a push button (the MD80E). The
  board profile provides `knob_encoder` (a `rotary_encoder` sensor at its finest
  resolution, `resolution: 4`), `knob_button` (a `binary_sensor`, on while
  pressed) and the substitution `encoder_counts_per_click` (encoder counts per
  mechanical click). Turning steps, a click selects, a long press goes back,
  held longer it returns to the child selector.
- `buttons-example.yaml`: an example with three push buttons (next, previous,
  select; holding select goes back). Set `next_pin`, `previous_pin` and
  `select_pin`.

### Support

Requirements: an ESP32-S3 with at least 8 MB PSRAM and 16 MB flash, and a round
display of one of the sizes above.

Profiles tested by the project on real hardware are officially supported
(currently the VIEWE MD80E with the 480 px screen). Profiles, input profiles and
screen sizes used by others work the same way but are not tested by the
project.

---

## Saját gomb

A gomb firmware-e három részből áll: a **magból** (`esphome/kis-segito-core.yaml`:
a Kis Segítő szoftvere – gyerekképernyő, képernyő-energiagazdálkodás,
érzékelőbemenetek, éjszakai fény, Home Assistant-kapcsolat; a hardvert nem
ismeri), a **gombprofilból** (egy gomb hardvere – kijelző, háttérvilágítás, chip-
és memóriabeállítások, a bemeneti hardver) és a **bemeneti profilból**
(`esphome/inputs/`: a bemeneti hardvert a mag általános bemeneteivé alakítja).
Az `esphome/kis-segito.yaml` a mag, a kipróbált VIEWE UEDX48480021-MD80E profil
(`esphome/hardware/board.yaml`) és a bemeneti profilja
(`esphome/inputs/encoder-button.yaml`) együtt; ezzel a gombbal semmi nem változik.

Más gombhoz írj profilt, és a mag meg egy bemeneti profil mellé vedd fel (lásd a
fenti példát). A profilnak adnia kell: `knob_display` (a kerek kijelző az
LVGL-nek), `backlight` (a háttérvilágítást kapcsoló és szabályzó `light`) és a
`screen_size` substitutiont (a kijelző szélessége és magassága pixelben: `240`,
`360`, `466` vagy `480`), valamint mindent, amire a chipnek szüksége van
(`esp32`, `psram`, `logger`). Mintának az `esphome/hardware/board.yaml`
használható.

**Képernyőméret:** a gyerekképernyő 480×480 pixelre van tervezve, és a
`screen_size` méretre skálázódik: a helyzetek, méretek, szövegek és a beépített
képek a firmware fordításakor készülnek el ehhez a mérethez, a Home Assistantból
jövő képek (ikonok, avatarok, hátterek) pedig ebben a méretben töltődnek le.

**Bemenetek:** a magot öt általános bemenet vezérli (ESPHome scriptek):
`input_next`, `input_previous`, `input_select`, `input_back` (hosszú nyomás:
vissza egy szintet) és `input_wake`. Ha a képernyő halványított, sötét vagy a
képernyővédő fut, mindegyik csak felébreszti. Bármilyen bemeneti hardver hívhatja
őket, pl. `on_press: - script.execute: input_next`. Bemeneti profilok:
`encoder-button.yaml` (enkóder nyomógombbal, mint az MD80E; a gombprofil adja a
`knob_encoder` és `knob_button` azonosítót és az `encoder_counts_per_click`
substitutiont) és `buttons-example.yaml` (példa három nyomógombbal: következő,
előző, kiválasztás; a kiválasztás nyomva tartása: vissza; a `next_pin`,
`previous_pin` és `select_pin` állítandó).

**Támogatás:** feltétel egy ESP32-S3 legalább 8 MB PSRAM-mal és 16 MB
flash-sel, és egy kerek kijelző a fenti méretek egyikével. Hivatalosan a projekt
által valódi hardveren kipróbált profilok támogatottak (jelenleg a VIEWE MD80E a
480 pixeles képernyővel); a mások által használt profilok, bemeneti profilok és
képernyőméretek ugyanígy működnek, de a projekt nem teszteli őket.
