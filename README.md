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

Lábkiosztás, a debug panel szabad lábai (mérve), lábazonosító firmware és
hangolási lehetőségek: [docs/hardware.md](docs/hardware.md).

Érzékelők (nem kötelező): jelenlét-, távolság- és fényérzékelővel a gomb
közelítésre felébred, sötétben éjszakai fényt mutat, a fényerejét a szoba
fényéhez igazítja. Bármelyik, az ESPHome által támogatott érzékelő a gombra
köthető (kipróbálva: LD2410C radar, VEML7700 fényérzékelő), vagy a Home
Assistant entitásai továbbíthatók neki: [docs/sensors.md](docs/sensors.md).

Más gomb: a firmware magja és a gomb hardverleírása (gombprofil) külön van, így
más gombhoz is írható profil: [docs/boards.md](docs/boards.md).

## Telepítés

### 1. Firmware a knobra (ESPHome)

**A) ESPHome package-ként (ajánlott).** A Home Assistant ESPHome Builderében hozz létre
egy új eszközt, és a YAML-ja legyen ehhez hasonló (minta: [esphome/example.yaml](esphome/example.yaml)):

```yaml
substitutions:
  name: kis-segito
  friendly_name: Kis Segito

packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@v0.9.6

api:
  encryption:
    key: !secret kis_segito_api_key

ota:
  - id: !extend kis_segito_ota
    # Updates use the API key above (encrypted and authenticated).
    encryption:

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    password: !secret ap_password
```

Az első felírás USB-n történik (debug/adapter panel), utána OTA-val frissíthető.
Szükséges ESPHome-verzió: 2026.10.0 vagy újabb.

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
-jutalmak hozhatók létre. Gombonként (**Beállítások → Gombok**) bepipálható, mely
gyerekek használhatják az adott gombot (alapból mindenki); a többiek ott szürkén, lakattal
látszanak, vagy – gombonként kapcsolható – rejtve vannak. A knob perselyképernyőjén tekeréssel választható ki,
hány zseton kerüljön a perselybe vagy onnan vissza; a gombnyomás könyveli. Háttér: a **Beállítások** oldalon egy közös
háttér választható a gombokra (6 beépített vagy saját feltöltött kép), és gombonként saját
is; cseréjekor a fizikai gomb 1 perc használaton kívüli idő után egyszer újraindul
(automatizálásból is váltható, egy vagy minden gombra: `kis_segito.set_background`). Automatizáláshoz:
[docs/automations.md](docs/automations.md), saját gombhoz vagy kijelzőhöz:
[docs/protocol.md](docs/protocol.md).

**Jóváhagyás:** egy feladatnál bekapcsolható, hogy jóváhagyás kelljen hozzá, egy
jutalomnál, hogy megerősítés kelljen hozzá (alapból egyik sem). A jóváhagyásra váró kérések
a **Ma** oldal tetején jelennek meg. A jutalom ára a döntésig félre van téve, elutasításkor
visszakerül; a feladat azonnal késznek számít, a checkpointja zsetonjai jóváhagyáskor
jönnek. Minden lépés naplózva van.

**Saját ikonok:** ahol ikont lehet választani, saját kép is feltölthető ikonnak; a
**Beállítások → Ikonok** részen cserélhető, kikapcsolható vagy törölhető. A beépített ikonok
kikapcsolhatók.

**Témák:** a **Beállítások → Téma** részen választható a kinézet (színek, betűk, ikonok,
avatarok, hátterek) a panelen és a gombokon; a kártyák kapcsolóval vehetik át. Beépített
stílustémák: „A Simpson család stílus”, „Jégvarázs stílus”, „Verdák stílus”, „Toy Story stílus”,
„Repcsik stílus” és „Micimackó stílus” (rajongói stílus-tisztelgések,
eredeti rajzokkal, lásd a jogi nyilatkozatot lent). Gyerekenként külön téma is választható a
gombra. Saját téma is készíthető: a sablont letöltve elég néhány képet lecserélni és
visszatölteni, a többi a beépített marad. Útmutató: [docs/themes.md](docs/themes.md).

**Irányítópult-kártyák:** a szülőknek kilenc kártya jön az integrációval (gyerek, mai
rutin, jutalombolt, jóváhagyások, heti statisztika, gyors +/−, eseménynapló, gomb
állapota, gyerekek röviden), vizuális szerkesztővel: [docs/cards.md](docs/cards.md).

**Assist:** a Home Assistant hangasszisztense megmondja egy gyerekről (vagy mindegyikről),
hány zsetonja van, van-e most feladata, mikor van a következő ellenőrzőpontja, hány zsetont
szerezhet még ma és hogy áll a sorozata. Magyarul és angolul érti, a gyerek nevével vagy egy
másik nevével, ragozva is. A válaszokban a számok és az időpontok szóval szerepelnek
(„negyed óra múlva, fél nyolckor”), így minden felolvasó jól mondja ki őket. Csak olvas,
nem változtat semmit. Néhány mondat, amely beállítás nélkül, LLM nélkül is működik:

- „Hány zsetonja van Alexnek?” · „Mennyi pénze van Alexnek?” · „Kinek mennyi zsetonja van?”
- „Van most feladata Alexnek?” · „Mit kell most csinálnia Alexnek?”
- „Mikor van Alex következő ellenőrzőpontja?” · „Mennyi idő van még a következő
  ellenőrzőpontig?”
- „Hány zsetont kaphat még ma Alex?” · „Hány napja hibátlan Alex?”

Ha csak a beépített ügynök fut, ezekre a mondatokra az válaszol. LLM-ügynöknél a
„Helyi parancsok előnyben részesítése” (Prefer handling commands locally) bekapcsolva a fenti mondatokra szintén a Kis
Segítő válaszol, minden másra az LLM; kikapcsolva az LLM kérdezi le a Kis Segítő eszközét.
A gyerekek szenzorai alapból meg vannak osztva az Assisttal (kikapcsolható). Teljes
mondatlista és beállítás: [docs/assist.md](docs/assist.md).

**Virtuális gomb:** a gomb képernyője irányítópult-kártyaként is használható, például
utazáskor vagy ha a gomb nem működik. Ugyanazok a képernyők, képek és animációk, csak
érintéssel: húzás balra/jobbra = tekerés, koppintás = nyomás, nyomva tartás = vissza
(egérgörgő és billentyűk is működnek). Létrehozása: panel → **Beállítások → Gombok →
Virtuális gomb hozzáadása**, majd egy irányítópulton **Kártya hozzáadása → Kis Segítő**, és
a kártya beállításaiban a gomb kiválasztása (a kártya az integrációval együtt települ).
Gyerekek ugyanúgy rendelhetők hozzá, mint egy valódi gombhoz. Telefonon a Home Assistant
alkalmazásban is működik; a gyerek kezébe adott telefonhoz egy csak ezt a kártyát mutató
irányítópult ajánlott.

A knob kijelzőjének és a panelnek a
szövegei alapból a Home Assistant nyelvén jelennek meg (jelenleg angol és magyar; ha egy
nyelvhez nincs fordítás, angolul). A panel **Beállítások** kártyáján más nyelv is
választható; ez a knobokra és a panelre is érvényes. Új nyelv:
[docs/translations.md](docs/translations.md).

## Biztonság

- **Kötelező titkos adatok** gombonként, a saját ESPHome `secrets.yaml`-odban:
  `kis_segito_api_key` – az API titkosítási kulcsa, **minden gombnak külön**;
  `ap_password` – a tartalék hozzáférési pont jelszava. A hálózati firmware-frissítés is
  az API kulcsával titkosított (`ota: encryption:`); OTA-jelszó nem kell. Átállás a
  korábbi jelszavas frissítésről: [docs/security.md](docs/security.md). A tartalék hozzáférési pont csak akkor indul el, ha a gomb
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
- **Frissítés:** a fenti mintában a package egy adott verzióra mutat (`@v0.9.6`), így a
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

Pinout, the debug board's free pins (measured), a pin probe firmware and
tuning options: [docs/hardware.md](docs/hardware.md).

Sensors (optional): with a presence, distance and light sensor the knob wakes
when someone comes near, shows a night light in the dark and sets its
brightness to the room light. Any sensor ESPHome supports can be wired to the
knob (tested: LD2410C radar, VEML7700 light sensor), or Home Assistant entities
can be forwarded to it: [docs/sensors.md](docs/sensors.md).

Other knobs: the firmware core and the knob's hardware description (board
profile) are separate, so a profile can be written for another knob:
[docs/boards.md](docs/boards.md).

### Installation

#### 1. Firmware for the knob (ESPHome)

**A) As an ESPHome package (recommended).** Create a new device in the Home Assistant
ESPHome Builder with a YAML like this (see [esphome/example.yaml](esphome/example.yaml)):

```yaml
substitutions:
  name: kis-segito
  friendly_name: Kis Segito

packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@v0.9.6

api:
  encryption:
    key: !secret kis_segito_api_key

ota:
  - id: !extend kis_segito_ota
    # Updates use the API key above (encrypted and authenticated).
    encryption:

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    password: !secret ap_password
```

The first flash is done over USB (debug/adapter board); after that it updates over the
air. Requires ESPHome 2026.10.0 or newer.

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
Rewards pages. Each knob (**Settings → Knobs**) has a ticked list of the
children who can use it (everyone by default); the others are shown greyed with a lock
there, or – switchable per knob – hidden. On the knob's piggy-bank screen, turning chooses how many tokens go
into the piggy bank or back out; pressing books it. Background: the **Settings** page has a common
background for the knobs (6 built-in or your own uploaded picture), and each knob can have
its own; after a change a physical knob restarts once, after 1 minute without use (also
from automations, for one knob or all: `kis_segito.set_background`). For automations see
[docs/automations.md](docs/automations.md), for building your own knob or display
[docs/protocol.md](docs/protocol.md).

**Approval:** a task can need approval and a reward confirmation (both off by default).
Waiting requests are shown at the top of the **Today** page. A reward's price is set aside
until the decision and returned on rejection; a task counts as done at once, and its
checkpoint's tokens come on approval. Every step is logged.

**Own icons:** wherever an icon is chosen, your own picture can be uploaded as an icon; on
**Settings → Icons** it can be replaced, switched off or deleted. Built-in icons can be
switched off.

**Themes:** under **Settings → Theme** you choose the look (colours, fonts, icons, avatars,
backgrounds) of the panel and the knobs; the cards can take it with a switch. Bundled style
themes: "The Simpsons style", "Frozen style", "Cars style", "Toy Story style",
"Planes style" and "Winnie the Pooh style" (fan-made style homages with original artwork,
see the disclaimer below). Each child can have its own theme on the knob. You can make your own
theme: download the template, replace a few pictures and upload it; the rest stays built-in.
Guide: [docs/themes.md](docs/themes.md).

**Dashboard cards:** nine cards for parents come with the integration (child, today's
routine, reward shop, approvals, weekly statistics, quick +/−, event log, knob status,
children at a glance), with a visual editor: [docs/cards.md](docs/cards.md).

**Assist:** Home Assistant's voice assistant tells about a child (or every child) how
many tokens they have, whether they have a task now, when the next checkpoint is, how many
tokens they can still earn today and how their streak is going. It understands English
and Hungarian, by the child's name or another name. Numbers and times are spoken as words
("in a quarter of an hour, at half past seven"), so every text-to-speech voice reads them
right. It only reads, it changes nothing. Some sentences that work without any setup and
without an LLM:

- "How many tokens does Alex have?" · "What's Alex's balance?" · "How many tokens do the
  kids have?"
- "Does Alex have a task now?" · "What should Alex be doing now?"
- "When is Alex's next checkpoint?" · "How long until the next checkpoint?"
- "How many coins can Alex still earn today?" · "What is Alex's streak?"

With only the built-in agent, it answers these sentences. With an LLM agent and "Prefer
handling commands locally" on, Kis Segítő still answers these sentences and the LLM
everything else; with it off, the LLM asks Kis Segítő's tool. The children's sensors are
shared with Assist by default (this can be turned off). Full sentence list and setup:
[docs/assist.md](docs/assist.md).

**Virtual knob:** the knob screen can also be used as a dashboard card, for example on a
trip or when the knob does not work. The same screens, pictures and animations, operated
by touch: swipe left/right = turn, tap = press, press and hold = back (a mouse wheel and
the keyboard work too). To create one: panel → **Settings → Knobs → Add a virtual knob**,
then on a dashboard **Add card → Kis Segítő**, and choose the knob in the card settings
(the card comes with the integration). Children can be assigned to it like to a real
knob. It works in the Home Assistant app on a phone too; for a phone handed to a child, a
dashboard showing only this card is recommended.

The texts on the knob display and in the
panel follow the Home Assistant language by default (currently English and Hungarian;
English when there is no translation for a language). Another language can be chosen on
the panel's **Settings** card; it applies to the knobs and the panel. Adding a language:
[docs/translations.md](docs/translations.md).

### Security

- **Required secrets** for each knob, in your own ESPHome `secrets.yaml`:
  `kis_segito_api_key` – the API encryption key, **a separate one for each
  knob**; `ap_password` – the password of the fallback access point. Firmware
  updates over the network are encrypted with the API key too (`ota: encryption:`); no
  OTA password is needed. Moving from the earlier password: [docs/security.md](docs/security.md). The fallback access point
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
- **Updates:** in the example above the package points to a given version (`@v0.9.6`), so
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

---

**Jogi nyilatkozat:** a Kis Segítő nem áll kapcsolatban a The Walt Disney Company, a Disney
Enterprises, Inc., a Pixar, a 20th Television, a 20th Century Studios (korábban Twentieth
Century Fox) vagy más jogtulajdonos vállalattal, és azok nem támogatják vagy szponzorálják. A
The Simpsons, a Frozen, a Cars, a Toy Story, a Planes és a Winnie the Pooh a jogtulajdonosaik
védjegyei. A nevek csak azt a vizuális stílust jelölik, amelyből egy téma ihletet merít. A
témák minden rajza eredeti: nem tartalmaznak szereplőket, logókat vagy más elemeket az
eredetiekből.

**Disclaimer:** Kis Segítő is not affiliated with, endorsed by or sponsored by The Walt Disney
Company, Disney Enterprises, Inc., Pixar, 20th Television, 20th Century Studios (formerly
Twentieth Century Fox) or any other rights holder. The Simpsons, Frozen, Cars, Toy Story,
Planes and Winnie the Pooh are trademarks of their respective owners. The names are used only
to describe the visual style that a theme is inspired by. All artwork in the themes is
original, and no characters, logos or other elements from the originals are included.
