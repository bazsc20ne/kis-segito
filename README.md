# Kis Segítő / Little Helper

<p align="center"><img src="docs/images/logo_hu.png" alt="Kis Segítő" width="480"></p>

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>

[![Validate](https://github.com/bazsc20ne/kis-segito/actions/workflows/validate.yml/badge.svg)](https://github.com/bazsc20ne/kis-segito/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

## Mi ez?

A Kis Segítő egy nyílt forrású eszköz, amely a gyerekeket segíti a napi rutinjukban.
Két, egymással együttműködő részből áll:

- **Knob** – egy kerek kijelzős forgatógomb ESPHome firmware-rel. Forgatással és
  nyomással kezelhető, érintőképernyő nélkül.
- **Home Assistant integráció** – HACS-ból telepíthető, saját adattárolással és saját
  „Kis Segítő” oldalsáv-menüponttal. A knobot az ESPHome natív API-n keresztül kezeli.

Mindkét rész független a Home Assistant többi beállításától. A szülő a Home Assistant
panelen állítja be a gyerekeket, a rutinokat (feladatok, időzített checkpointok, színzónák,
időalapú zsetonjutalom), a jutalmakat és a perselyt; a gyerek a knobon követi a rutinját,
zsetont gyűjt és jutalmat vált be. Minden zsetonmozgás visszakereshető, visszavonható
előzményként tárolódik. A projekt aktív fejlesztés alatt áll; a naptár, a napi sablonok és
az értesítési szabályok később jönnek.

## Hardver

- **VIEWE UEDX48480021-MD80E** (érintés **nélküli** változat) – 2.1" kerek, 480×480 IPS
  kijelzős forgatógomb
  - ESP32-S3-R8: 8 MB Octal PSRAM, 16 MB flash
  - kijelző-meghajtó: GC9503CV (RGB)
  - kezelés: csak forgatás + nyomás
  - első felíráshoz USB-s debug/adapter panel

Lábkiosztás és hangolási lehetőségek: [docs/hardware.md](docs/hardware.md).

## Telepítés

### 1. Firmware a knobra (ESPHome)

**A) ESPHome package-ként (ajánlott).** A Home Assistant ESPHome Builderében hozz létre
egy új eszközt, és a YAML-ja legyen ehhez hasonló (minta: [esphome/example.yaml](esphome/example.yaml)):

```yaml
substitutions:
  name: kis-segito
  friendly_name: Kis Segito

packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@v0.3.1

api:
  encryption:
    key: !secret kis_segito_api_key

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
```

Az első felírás USB-n történik (debug/adapter panel), utána OTA-val frissíthető.
Szükséges ESPHome-verzió: 2026.9.0 vagy újabb.

Az enkóder érzékenysége a Home Assistantből állítható: az eszköz **Encoder clicks per
step** beállítása (1–5, alapból 1 = egy kattanás egy lépés), és újraindítás után is
megmarad. Más enkóderhez a `substitutions` részben az `encoder_counts_per_click`
állítható (alapból `"2"`). A kijelző beállításai: [docs/hardware.md](docs/hardware.md).

Képernyővédő: a kijelző a **Screen dim after** idő (alapból 60 s) után elhalványul, a
**Screen off after** idő (alapból 120 s) után kikapcsol; bármelyik tekerés vagy
gombnyomás felébreszti (ez a mozdulat még nem lép a menüben). A 0 érték az adott
lépést kikapcsolja. Amíg a háttérvilágítás ki van kapcsolva (bármilyen módon), a
kijelző tartalma fekete.

**B) Kész firmware.** Minden [release](https://github.com/bazsc20ne/kis-segito/releases)
mellett ott van a lefordított firmware: a `*.factory.bin` USB-s első felíráshoz
(pl. [ESPHome Web](https://web.esphome.io/)), az `*.ota.bin` frissítéshez. A WiFi
ilyenkor a knob saját hozzáférési pontján állítható be (a telefonnal rá kell
csatlakozni, és megnyílik a beállítóoldal), utána az eszköz átvehető az ESPHome Builderbe. Böngészős telepítő később jön.

Ezután add hozzá a knobot a Home Assistanthez az **ESPHome** integrációval.

### 2. Home Assistant integráció (HACS)

1. HACS → jobb felső menü → **Egyéni tárolók** → URL: `https://github.com/bazsc20ne/kis-segito`,
   típus: **Integráció**.
2. Telepítsd a **Kis Segítő** integrációt, majd indítsd újra a Home Assistantet.
3. **Beállítások → Eszközök és szolgáltatások → Integráció hozzáadása → Kis Segítő**,
   és válaszd ki a knobot.

Az oldalsávban megjelenik a **Kis Segítő** menüpont: **Ma** (gyerekenkénti áttekintés),
**Gyerekek**, **Rutinok**, **Jutalmak**, **Zsetonok**, **Előzmények**, **Beállítások**.
Üres rendszerben a Rutinok és a Jutalmak oldalon egy gombnyomással példa-rutinok és
-jutalmak hozhatók létre. Egy gyerek legfeljebb egy knobhoz rendelhető (a gyerek oldalán);
egy knobon a hozzá rendelt gyerekek választhatók, a többiek zárolva látszanak, a gyerek
nélküli knob mindenkinek működik. Automatizáláshoz: [docs/automations.md](docs/automations.md),
a knob és a HA kapcsolata: [docs/protocol.md](docs/protocol.md).

A knob kijelzőjének és a panelnek a
szövegei alapból a Home Assistant nyelvén jelennek meg (jelenleg angol és magyar; ha egy
nyelvhez nincs fordítás, angolul). A panel **Beállítások** kártyáján más nyelv is
választható; ez a knobokra és a panelre is érvényes. Új nyelvet fordítási fájlok
hozzáadásával lehet felvenni.

## Köszönet és források

- **VIEWESMART** – gyári mintakód, kapcsolási rajz, lábkiosztás és kijelző-inicializálás
  (MIT licenc): [UEDX48480021-MD80ESP32_2.1inch-Knob](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob),
  [UEDX48480021-MD80ESP32-2.1inch-Touch-Knob-Display](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32-2.1inch-Touch-Knob-Display)
- **Greg-79** – ESPHome-konfiguráció ehhez a kijelzőhöz (a README szerint MIT licenc; csak referencia):
  [UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-](https://github.com/Greg-79/UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-)
- **ESPHome** – a kijelző-meghajtó (`mipi_rgb`)
- ESPHome feature request: [esphome/feature-requests#3254](https://github.com/esphome/feature-requests/issues/3254)
- Spotpear wiki: <https://spotpear.com/wiki/ESP32-S3-2.1-inch-Round-Rotary-LCD-Screen-Knob-Display.html>

## Licenc

**GNU Affero General Public License v3.0** – szabadon használható, forkolható és
módosítható. Aki módosított változatot terjeszt vagy hálózati szolgáltatásként futtat,
köteles a teljes forráskódot ugyanezen licenc alatt közzétenni.

A felhasznált harmadik féltől származó anyagok a saját licencük alatt maradnak
(pl. VIEWESMART – MIT, lásd [NOTICE](NOTICE); ESPHome – GPLv3/MIT).

---

<a id="english"></a>

## English

<p align="center"><img src="docs/images/logo_en.png" alt="Little Helper" width="480"></p>

🇭🇺 [Magyar változat](#magyar)

### What is this?

Little Helper is an open-source device that helps children with their
daily routine. It has two parts that work together:

- **Knob** – a rotary knob with a round display, running ESPHome firmware. It is
  operated by turning and pressing; there is no touch screen.
- **Home Assistant integration** – installable from HACS, with its own storage and its
  own "Kis Segítő" sidebar entry. It controls the knob through the ESPHome native API.

Both parts are independent of the rest of your Home Assistant setup. Parents set up
children, routines (tasks, timed checkpoints, colour zones, time-based token rewards),
rewards and the piggy bank in the Home Assistant panel; the child follows the routine on
the knob, collects tokens and buys rewards. Every token movement is kept as history that
can be reviewed and reversed. The project is under active development; the calendar, day
templates and notification rules come later.

### Hardware

- **VIEWE UEDX48480021-MD80E** (variant **without** touch) – 2.1" round 480×480 IPS
  rotary knob
  - ESP32-S3-R8: 8 MB octal PSRAM, 16 MB flash
  - display controller: GC9503CV (RGB)
  - input: turn + press only
  - USB debug/adapter board for the first flash

Pinout and tuning options: [docs/hardware.md](docs/hardware.md).

### Installation

#### 1. Firmware for the knob (ESPHome)

**A) As an ESPHome package (recommended).** Create a new device in the Home Assistant
ESPHome Builder with a YAML like this (see [esphome/example.yaml](esphome/example.yaml)):

```yaml
substitutions:
  name: kis-segito
  friendly_name: Kis Segito

packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@v0.3.1

api:
  encryption:
    key: !secret kis_segito_api_key

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
```

The first flash is done over USB (debug/adapter board); after that it updates over the
air. Requires ESPHome 2026.9.0 or newer.

The encoder sensitivity is set from Home Assistant: the device's **Encoder clicks per
step** setting (1–5, default 1 = one step per click), kept across reboots. For a
different encoder, set `encoder_counts_per_click` in `substitutions` (default `"2"`).
Display settings: [docs/hardware.md](docs/hardware.md).

Screen saver: the display dims after **Screen dim after** (default 60 s) and switches
off after **Screen off after** (default 120 s); any turn or press wakes it (that input
is not passed to the menu). 0 disables a step. While the backlight is off (however it
was switched off), the screen content is black.

**B) Prebuilt firmware.** Every [release](https://github.com/bazsc20ne/kis-segito/releases)
includes the compiled firmware: `*.factory.bin` for the first USB flash (e.g. with
[ESPHome Web](https://web.esphome.io/)) and `*.ota.bin` for updates. Wi-Fi is then set up
through the knob's own access point (connect with a phone and the setup page opens),
and the device can be adopted in the ESPHome Builder. A browser installer will follow later.

Then add the knob to Home Assistant with the **ESPHome** integration.

#### 2. Home Assistant integration (HACS)

1. HACS → top-right menu → **Custom repositories** → URL:
   `https://github.com/bazsc20ne/kis-segito`, type: **Integration**.
2. Install **Kis Segítő** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Kis Segítő**, then select the knob.

A **Kis Segítő** entry appears in the sidebar: **Today** (per-child overview),
**Children**, **Routines**, **Rewards**, **Tokens**, **History**, **Settings**. In an empty
setup, example routines and rewards can be created with one click on the Routines and
Rewards pages. A child can be assigned to at most one knob (on the child's page); on a knob
its children can be selected and the others are shown locked; a knob without children
works for everyone. For automations see [docs/automations.md](docs/automations.md), for
the knob link [docs/protocol.md](docs/protocol.md).

The texts on the knob display and in the
panel follow the Home Assistant language by default (currently English and Hungarian;
English when there is no translation for a language). Another language can be chosen on
the panel's **Settings** card; it applies to the knobs and the panel. A new language only
needs new translation files.

### Credits and sources

- **VIEWESMART** – vendor sample code, schematic, pinout and display initialisation
  (MIT license): [UEDX48480021-MD80ESP32_2.1inch-Knob](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob),
  [UEDX48480021-MD80ESP32-2.1inch-Touch-Knob-Display](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32-2.1inch-Touch-Knob-Display)
- **Greg-79** – ESPHome configuration for this display (MIT according to its README; reference only):
  [UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-](https://github.com/Greg-79/UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-)
- **ESPHome** – the display driver (`mipi_rgb`)
- ESPHome feature request: [esphome/feature-requests#3254](https://github.com/esphome/feature-requests/issues/3254)
- Spotpear wiki: <https://spotpear.com/wiki/ESP32-S3-2.1-inch-Round-Rotary-LCD-Screen-Knob-Display.html>

### License

**GNU Affero General Public License v3.0** – free to use, fork and modify. Anyone who
distributes a modified version, or runs it as a network service, must publish the
complete source code under the same license.

Third-party material keeps its own license (e.g. VIEWESMART – MIT, see
[NOTICE](NOTICE); ESPHome – GPLv3/MIT).
