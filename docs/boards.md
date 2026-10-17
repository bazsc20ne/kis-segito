<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Board profiles / Gombprofilok

The knob firmware has two parts:

- **Core** (`esphome/kis-segito-core.yaml`): the Kis Segítő software – child
  screen, screen power, sensor inputs, night light, Home Assistant connection.
  It does not know the hardware.
- **Board profile**: the hardware of one knob – display, backlight, encoder,
  button, chip and memory settings.

`esphome/kis-segito.yaml` is the core together with the tested profile of the
VIEWE UEDX48480021-MD80E knob (`esphome/hardware/board.yaml`). With that knob
nothing changes: keep using `kis-segito.yaml` as in `esphome/example.yaml`.

A gomb firmware-e két részből áll: a **magból** (`esphome/kis-segito-core.yaml`:
a Kis Segítő szoftvere – gyerekképernyő, képernyő-energiagazdálkodás,
érzékelőbemenetek, éjszakai fény, Home Assistant-kapcsolat; a hardvert nem
ismeri) és a **gombprofilból** (egy gomb hardvere – kijelző, háttérvilágítás,
enkóder, gomb, chip- és memóriabeállítások). Az `esphome/kis-segito.yaml` a mag
és a kipróbált VIEWE UEDX48480021-MD80E profil (`esphome/hardware/board.yaml`)
együtt; ezzel a gombbal semmi nem változik.

## Your own knob / Saját gomb

For another knob, write a profile for it and include it next to the core:

```yaml
packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito-core.yaml@v0.8.0
  board: !include my-board.yaml
```

The profile must provide these IDs (the core adds the knob's behaviour to
them):

| ID / substitution | What |
|---|---|
| `knob_display` | The display, used by LVGL. |
| `backlight` | A `light` that switches and dims the display backlight. |
| `knob_encoder` | A `rotary_encoder` sensor at its finest resolution (`resolution: 4`). |
| `knob_button` | A `binary_sensor`, on while the button is pressed. |
| `encoder_counts_per_click` | Substitution: encoder counts per mechanical click. |

and everything the chip needs: `esp32` (with the framework), `psram` and
`logger`. Use `esphome/hardware/board.yaml` as an example.

Requirements: an ESP32-S3 with at least 8 MB PSRAM and 16 MB flash. The child
screen is drawn for a round 480×480 display; other display sizes are not
supported yet.

Profiles tested by the project on real hardware are officially supported
(currently the VIEWE MD80E). Profiles written by users work the same way but
are not tested by the project.

Más gombhoz írj hozzá profilt, és a mag mellé vedd fel (lásd a fenti példát). A
profilnak a fenti azonosítókat kell adnia – `knob_display` (kijelző az LVGL-nek),
`backlight` (a háttérvilágítást kapcsoló és szabályzó `light`), `knob_encoder`
(`rotary_encoder` a legfinomabb felbontással), `knob_button` (`binary_sensor`,
nyomva be), valamint az `encoder_counts_per_click` substitutiont –, és mindent,
amire a chipnek szüksége van (`esp32`, `psram`, `logger`). Mintának az
`esphome/hardware/board.yaml` használható. Feltétel: ESP32-S3 legalább 8 MB
PSRAM-mal és 16 MB flash-sel. A gyerekképernyő kerek, 480×480-as kijelzőre
készül; más kijelzőméret egyelőre nem támogatott. Hivatalosan a projekt által
valódi hardveren kipróbált profilok támogatottak (jelenleg a VIEWE MD80E); a
felhasználók által írt profilok ugyanígy működnek, de a projekt nem teszteli
őket.
