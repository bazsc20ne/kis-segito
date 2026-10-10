# Kis Segítő / Little Helper

<p align="center"><img src="docs/images/logo_hu.png" alt="Kis Segítő" width="480"></p>

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>

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
előzményként tárolódik. A projekt aktív fejlesztés alatt áll.

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
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@v0.7.19

api:
  encryption:
    key: !secret kis_segito_api_key

ota:
  - id: !extend kis_segito_ota
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    password: !secret ap_password
```

Az első felírás USB-n történik (debug/adapter panel), utána OTA-val frissíthető.
Szükséges ESPHome-verzió: 2026.9.0 vagy újabb.

Az enkóder érzékenysége a Home Assistantből állítható: az eszköz **Encoder clicks per
step** beállítása (1–5, alapból 1 = egy kattanás egy lépés), és újraindítás után is
megmarad. Más enkóderhez a `substitutions` részben az `encoder_counts_per_click`
állítható (alapból `"2"`). A kijelző beállításai: [docs/hardware.md](docs/hardware.md).

Képernyő: a panel **Beállítások** oldalán a **Gomb képernyője** kártyán állítható, mennyi
tétlenség után induljon a képernyővédő (pattogó labdák vagy folyamatos konfetti), halványuljon el a kijelző (és
milyen fényerőre), álljon le a rajzolás (fekete képernyő), illetve kapcsoljon ki a
háttérvilágítás; a 0 az adott lépést kikapcsolja. Gombonként saját értékek is
megadhatók. Bármelyik tekerés vagy gombnyomás felébreszti a gombot (ez a mozdulat még nem
lép a menüben). Amíg a háttérvilágítás ki van kapcsolva (bármilyen módon), a kijelző
tartalma fekete.

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

Az oldalsávban megjelenik a **Kis Segítő** menüpont: **Ma** (gyerekenkénti áttekintés és
a mai nap módosítása: egy rutin mára kihagyható vagy eltolható), **Naptár** (heti nézet),
**Gyerekek** (fénykép is feltölthető), **Rutinok**, **Jutalmak** (saját kép is), **Zsetonok**,
**Előzmények** (szűrhető, sorszámozott, hivatkozásokkal), **Értesítések** (szabályok bármely
Home Assistant értesítési célponthoz vagy címkével megjelölt scripthez), **Beállítások**
(többek között adatexport JSON-ba). A **Naptár** oldalon napsablonok (pl. hétköznap, hétvége,
szünet) is megadhatók: a hét napjaihoz alapértelmezett sablon, egy-egy naphoz eltérő sablon
rendelhető. A Home Assistantben egy összesítő szenzor (`sensor.kis_segito`), gyerekenként egy
szenzor és egy naptár (`calendar.kis_segito`) jelenik meg.
Üres rendszerben a Rutinok és a Jutalmak oldalon egy gombnyomással példa-rutinok és
-jutalmak hozhatók létre. Egy gyerek legfeljebb egy knobhoz rendelhető (a gyerek oldalán);
egy knobon a hozzá rendelt gyerekek választhatók, a többiek zárolva látszanak, a gyerek
nélküli knob mindenkinek működik. A knob perselyképernyőjén tekeréssel választható ki,
hány zseton kerüljön a perselybe vagy onnan vissza; a gombnyomás könyveli. Háttér: a **Beállítások** oldalon egy
háttér választható a gombokra (6 beépített vagy saját feltöltött kép), minden gyereknek
ugyanaz; cseréjekor a gombok egyszer újraindulnak. Automatizáláshoz:
[docs/automations.md](docs/automations.md), saját gombhoz vagy kijelzőhöz:
[docs/protocol.md](docs/protocol.md).

A knob kijelzőjének és a panelnek a
szövegei alapból a Home Assistant nyelvén jelennek meg (jelenleg angol és magyar; ha egy
nyelvhez nincs fordítás, angolul). A panel **Beállítások** kártyáján más nyelv is
választható; ez a knobokra és a panelre is érvényes. Új nyelv:
[docs/translations.md](docs/translations.md).

## Biztonság

- **Kötelező titkos adatok** gombonként, a saját ESPHome `secrets.yaml`-odban:
  `kis_segito_api_key` – az API titkosítási kulcsa, **minden gombnak külön**;
  `ota_password` – a hálózati firmware-frissítés jelszava; `ap_password` – a tartalék
  hozzáférési pont jelszava. A tartalék hozzáférési pont csak akkor indul el, ha a gomb
  nem tud csatlakozni a WiFi-hez; a beállítóoldala firmware-feltöltést is fogad, ezért kell
  hozzá jelszó.
- **Kész firmware:** a release-ben lévő gyári firmware-ben nincs titkos adat (titkosítatlan
  API, jelszó nélküli OTA). Az első indítás után vedd át az ESPHome Builderbe, add hozzá a
  fenti sorokat, és telepítsd újra.
- **Képek:** a feltöltött képeket (gyerekfotók, jutalmak) a gomb csak a helyi hálózaton
  és csak titkosított kapcsolat mellett kapja meg; Home Assistant Cloudon és az interneten
  át nem érhetők el. Ha egy gomb kapcsolata nem titkosított, a Home Assistant javítási
  értesítést mutat, és a gomb a képek helyett ikonokat jelenít meg. A gomb hozzáférése a
  képekhez megújítható: panel → **Beállítások → Gombok → Új képkulcs**.
- **Frissítés:** a fenti mintában a package egy adott verzióra mutat (`@v0.7.19`), így a
  gomb firmware-e csak akkor változik, amikor ezt átírod egy újabb verzióra.
- **Nem része a projektnek:** aki fizikailag hozzáfér a gombhoz, kiolvashatja a
  flash-memóriáját (és a benne lévő titkos adatokat). Ez egy otthoni, házilag épített
  eszköz, ezért a flash-titkosítás és a secure boot nem cél.

Részletek: [docs/security.md](docs/security.md).

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
can be reviewed and reversed. The project is under active development.

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
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@v0.7.19

api:
  encryption:
    key: !secret kis_segito_api_key

ota:
  - id: !extend kis_segito_ota
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    password: !secret ap_password
```

The first flash is done over USB (debug/adapter board); after that it updates over the
air. Requires ESPHome 2026.9.0 or newer.

The encoder sensitivity is set from Home Assistant: the device's **Encoder clicks per
step** setting (1–5, default 1 = one step per click), kept across reboots. For a
different encoder, set `encoder_counts_per_click` in `substitutions` (default `"2"`).
Display settings: [docs/hardware.md](docs/hardware.md).

Screen: on the panel's **Settings** page, the **Knob screen** card sets after how long
without use the screensaver starts (bouncing balls or continuous confetti), the display dims (and to which
brightness), drawing stops (black screen) and the backlight switches off; 0 disables a
step. Each knob can have its own values. Any turn or press wakes the knob (that input is
not passed to the menu). While the backlight is off (however it was switched off), the
screen content is black.

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

A **Kis Segítő** entry appears in the sidebar: **Today** (per-child overview and "Modify
today": skip or shift a routine for today only), **Calendar** (week view), **Children**,
**Routines**, **Rewards** (own pictures too), **Tokens**, **History** (filterable, numbered,
with links), **Notifications** (rules for any Home Assistant notify target or labelled
script), **Settings** (including a JSON export). Children can have a photo. The **Calendar**
page also holds day templates (e.g. weekday, weekend, holiday): a default per weekday and
a different one for a single day. Home Assistant gets a summary sensor
(`sensor.kis_segito`), one sensor per child and a calendar (`calendar.kis_segito`). In an empty
setup, example routines and rewards can be created with one click on the Routines and
Rewards pages. A child can be assigned to at most one knob (on the child's page); on a knob
its children can be selected and the others are shown locked; a knob without children
works for everyone. On the knob's piggy-bank screen, turning chooses how many tokens go
into the piggy bank or back out; pressing books it. Background: the **Settings** page has a
background for the knobs (6 built-in or your own uploaded picture), the same for every
child; changing it restarts the knobs once. For automations see
[docs/automations.md](docs/automations.md), for building your own knob or display
[docs/protocol.md](docs/protocol.md).

The texts on the knob display and in the
panel follow the Home Assistant language by default (currently English and Hungarian;
English when there is no translation for a language). Another language can be chosen on
the panel's **Settings** card; it applies to the knobs and the panel. Adding a language:
[docs/translations.md](docs/translations.md).

### Security

- **Required secrets** for each knob, in your own ESPHome `secrets.yaml`:
  `kis_segito_api_key` – the API encryption key, **a separate one for each
  knob**; `ota_password` – the password for firmware updates over the network;
  `ap_password` – the password of the fallback access point. The fallback access point
  opens only when the knob cannot join Wi-Fi; its setup page also accepts a firmware
  upload, which is why it needs a password.
- **Ready-made firmware:** the factory firmware in a release has no secrets (unencrypted
  API, OTA without a password). After the first start, adopt it in the ESPHome Builder,
  add the lines above and install it again.
- **Pictures:** the knob gets uploaded pictures (children's photos, rewards) only on the
  local network and only over an encrypted connection; they cannot be reached through
  Home Assistant Cloud or the internet. If a knob's connection is not encrypted, Home
  Assistant shows a repair issue and the knob shows icons instead of the pictures. A
  knob's access to the pictures can be renewed: panel → **Settings → Knobs → New picture
  key**.
- **Updates:** in the example above the package points to a given version (`@v0.7.19`), so
  the knob's firmware changes only when you change it to a newer version.
- **Out of scope:** anyone with physical access to the knob can read its flash memory (and
  the secrets in it). This is a DIY device for the home, so flash encryption and secure
  boot are not goals.

Details: [docs/security.md](docs/security.md).

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
