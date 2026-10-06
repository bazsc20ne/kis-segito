# Changelog

All notable changes to this project are documented here, in English and Hungarian.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

Minden lényeges változás itt szerepel, angolul és magyarul.

## [0.1.5] - 2026-10-06

### English

- Fix: correct colours on the MD80E display (#3). The cause was the COLMOD the
  display driver sends after the init table: 18-bit (0x66) breaks the colours
  on this panel, 16-bit (0x55) gives a correct picture. `display_pixel_mode` now
  defaults to `16bit`.
- The v0.1.4 change (sending the init with custom bit-banged SPI) is reverted:
  the init already reached the panel. The board definition is the tested v0.1.3
  one again (GC9503 table, 26 MHz, non-inverted PCLK, 8/20/40, 8/20/50).

### Magyar

- Javítás: helyes színek az MD80E kijelzőn (#3). Az ok a kijelző-meghajtó által
  az init tábla után küldött COLMOD volt: a 18 bit (0x66) elrontja a színeket
  ezen a panelen, a 16 bit (0x55) helyes képet ad. A `display_pixel_mode`
  alapértéke most `16bit`.
- A v0.1.4 változtatása (az init saját, bit-bang SPI-vel) visszavonva: az init
  eddig is eljutott a panelhez. A lapdefiníció újra a tesztelt v0.1.3-as (GC9503
  tábla, 26 MHz, nem invertált PCLK, 8/20/40, 8/20/50).

## [0.1.4] - 2026-10-06

### English

- Fix attempt for the MD80E display (#3): the panel init is now sent exactly the
  way the vendor code does it (bit-banged 9-bit 3-wire SPI with idle-high lines
  at about 50 kHz, no reset pulse, 120 ms, DISPON, then GPIO12/13 released) from
  an `on_boot` step before the display starts. The `mipi_rgb` display uses
  ESPHome's generic `RPI` model and sends no init of its own.
- New diagnostic substitution `display_init_test_invert`: sends INVON after the
  init table, so a colour inversion proves the init reaches the panel.
- Removed the substitutions that no longer have an effect
  (`display_pixel_mode`, `display_color_order`, `display_invert_colors`).

### Magyar

- Javítási kísérlet az MD80E kijelzőhöz (#3): a panel initje most pontosan úgy
  megy ki, mint a gyártói kódban (bit-bang 9 bites 3-vezetékes SPI, magas
  nyugalmi szint, kb. 50 kHz, reset-impulzus nélkül, 120 ms, DISPON, utána a
  GPIO12/13 felszabadítása), egy `on_boot` lépésből a kijelző indulása előtt. A
  `mipi_rgb` kijelző az ESPHome általános `RPI` modelljét használja, saját init
  nélkül.
- Új diagnosztikai substitution: `display_init_test_invert`. Az init tábla után
  INVON-t küld, így ha a színek megfordulnak, az init eljut a panelhez.
- Kikerültek a már hatástalan substitutionök (`display_pixel_mode`,
  `display_color_order`, `display_invert_colors`).

## [0.1.3] - 2026-10-06

### English

- Fix: red was missing and the test card was wrong on the MD80E (#2). The panel
  has a GC9503CV controller; the display now uses the vendor's GC9503 init
  table (the one the factory demo runs) with the vendor timings (26 MHz,
  non-inverted PCLK, 8/20/40, 8/20/50). The previous ST7701-style table stays
  available with `display_controller: st7701`.
- Init tables moved to `esphome/hardware/panel/`.

### Magyar

- Javítás: az MD80E-n hiányzott a piros szín, és hibás volt a tesztkép (#2). A
  panel vezérlője GC9503CV; a kijelző most a gyártói GC9503 init táblát
  használja (ezt futtatja a gyári demó is), a gyártói időzítésekkel (26 MHz,
  nem invertált PCLK, 8/20/40, 8/20/50). Az előző, ST7701-es tábla
  `display_controller: st7701` beállítással továbbra is elérhető.
- Az init táblák az `esphome/hardware/panel/` mappába kerültek.

## [0.1.2] - 2026-10-06

### English

- Fix: the MD80E (non-touch) panel showed only stripes. The display now uses
  the vendor's MD80E ESP-IDF example setup instead of ESPHome's built-in
  `UEDX48480021-MD80ET` model: 26 MHz non-inverted PCLK, porches 8/20/40 and
  8/20/50, the vendor init sequence, and the vendor's PSRAM/cache settings.
  All timing values are substitutions, so they can be tuned from the device
  config (#1).
- New `esphome/display-test.yaml`: the same board without LVGL, showing
  ESPHome's test card, for checking the panel on its own.
- The board definition moved to `esphome/hardware/board.yaml`.

### Magyar

- Javítás: az MD80E (nem érintős) kijelzőn csak csíkok látszottak. A kijelző
  most a gyártói MD80E ESP-IDF példa beállításait használja az ESPHome beépített
  `UEDX48480021-MD80ET` modellje helyett: 26 MHz, nem invertált PCLK, 8/20/40 és
  8/20/50 porch, a gyártói init szekvencia, valamint a gyártói PSRAM/cache
  beállítások. Minden időzítés substitution, így az eszközkonfigból hangolható (#1).
- Új `esphome/display-test.yaml`: ugyanaz a lap LVGL nélkül, az ESPHome
  tesztképével (test card), a kijelző önálló ellenőrzéséhez.
- A lapdefiníció az `esphome/hardware/board.yaml` fájlba került.

## [0.1.1] - 2026-10-06

### English

- Knob: loading screen from boot until Home Assistant sends the content
  (spinner; place for a future logo). Its text ("Loading...") is kept in flash
  in the last language received from Home Assistant, so it is shown in that
  language after a power cut too. Empty before the first connection.

### Magyar

- Knob: betöltőképernyő a bekapcsolástól addig, amíg a Home Assistant el nem
  küldi a tartalmat (forgó jel; később ide kerül a logó). A felirata
  („Betöltés...”) a Home Assistanttől utoljára kapott nyelven a flash-ben
  marad, így áramszünet után is ezen a nyelven jelenik meg. Az első
  csatlakozás előtt üres.

## [0.1.0] - 2026-10-06

### English

First testable skeleton.

- **ESPHome firmware** (`esphome/kis-segito.yaml`), usable as a package: ST7701S
  480×480 display (built-in `UEDX48480021-MD80ET` model), dimmable backlight,
  rotary encoder, push button, and an LVGL test screen: turning changes a number,
  pressing gives visual feedback. On-screen texts come from Home Assistant in its
  language (`set_ui_strings` API action); fonts cover Latin, Greek and Cyrillic.
- **Home Assistant integration** `kis_segito` (HACS): config flow that links an
  ESPHome knob, an empty "Kis Segítő" sidebar panel, versioned storage, English
  and Hungarian translations. Sends the knob texts on connect and on language change.
- GitHub Actions: hassfest, HACS validation, tests, ESPHome build; tagged releases
  attach the factory and OTA firmware.

### Magyar

Első, tesztelhető váz.

- **ESPHome firmware** (`esphome/kis-segito.yaml`), package-ként behúzható:
  ST7701S 480×480 kijelző (beépített `UEDX48480021-MD80ET` modell), dimmelhető
  háttérvilágítás, forgó enkóder, nyomógomb és LVGL tesztképernyő: forgatásra
  változó szám, nyomásra visszajelzés. A kijelző szövegeit a Home Assistant küldi
  a saját nyelvén (`set_ui_strings` API action); a betűkészlet latin, görög és
  cirill betűket tartalmaz.
- **Home Assistant integráció** `kis_segito` (HACS): config flow az ESPHome-os
  knob kiválasztásához, üres „Kis Segítő” oldalsáv-panel, verziózott adattárolás,
  angol és magyar fordítás. Csatlakozáskor és nyelvváltáskor elküldi a knob szövegeit.
- GitHub Actions: hassfest, HACS-validáció, tesztek, ESPHome-fordítás; a tagelt
  release-ekhez csatolva a factory és az OTA firmware.

[0.1.5]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.5
[0.1.4]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.4
[0.1.3]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.3
[0.1.2]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.2
[0.1.1]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.1
[0.1.0]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.0
