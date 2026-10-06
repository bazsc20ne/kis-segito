# Changelog

All notable changes to this project are documented here, in English and Hungarian.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

Minden lényeges változás itt szerepel, angolul és magyarul.

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

[0.1.0]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.0
