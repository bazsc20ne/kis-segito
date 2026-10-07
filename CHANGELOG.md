# Changelog

All notable changes to this project are documented here, in English and Hungarian.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

Minden lényeges változás itt szerepel, angolul és magyarul.

## [0.3.0] - 2026-10-07

### English

Real data: the knob now shows what is set up in Home Assistant instead of test
data (the test data remains only until Home Assistant first sends data).

- Home Assistant panel with Today, Children, Routines, Rewards, Tokens, History
  and Settings pages:
  - children: name, birth date, colour (presets, colour picker, hint when it is
    close to a time-zone colour), avatar, knob assignment, piggy bank, order;
  - routines: days of the week, start and end, children, colour zones,
    checkpoints (shared or per child, reward bands by how early, counts for the
    streak), tasks linked to checkpoints; one-click example routines;
  - rewards: icon, price shown as a token pile, piggy-bank unlock; examples;
  - tokens: manual bonus and debit; history with reversal and amount change;
  - settings: language, animations, daily streak, weekly piggy-bank interest,
    knobs with the avatars of their children.
- Append-only token ledger (wallet and piggy bank): balances are always the
  sum of the history; reversals and corrections never delete anything.
- Checkpoint rewards by time bands, daily streak (evaluated after midnight,
  bonus at the target), weekly compound piggy-bank interest with optional
  minimum and maximum.
- Device-child assignment: a child belongs to at most one knob; on a knob with
  assigned children the others are shown greyed and locked; a knob without
  children (or with all of them) works for everyone.
- Knob protocol (docs/protocol.md): Home Assistant sends a compact state
  snapshot (`set_state`); the knob reports completed tasks and bought rewards
  as JSON actions with a unique id on its new Action text sensor, booked at
  most once.
- On the knob: the function carousel lists the child's routines of today; the
  time track shows the routine's colour zones, shared checkpoints on the outer
  and the child's own on the inner track, and the reward available now.
- Home Assistant actions for automations (`kis_segito.complete_task`,
  `complete_checkpoint`, `adjust_tokens`, `redeem_reward`, `piggy_deposit`,
  `piggy_withdraw`, `reverse_transaction`) and the `kis_segito_event` event
  (docs/automations.md).
- Every icon of the set is now available on the knob and in the panel.

### Magyar

Valódi adatok: a knob most a Home Assistantben beállított adatokat mutatja a
tesztadatok helyett (a tesztadatok csak addig látszanak, amíg a Home Assistant
először adatot nem küld).

- Home Assistant panel Ma, Gyerekek, Rutinok, Jutalmak, Zsetonok, Előzmények és
  Beállítások oldallal:
  - gyerekek: név, születési dátum, szín (előre megadott színek, színválasztó,
    figyelmeztetés, ha közel van egy időzóna-színhez), avatar, gomb-hozzárendelés,
    persely, sorrend;
  - rutinok: a hét napjai, kezdés és vége, gyerekek, színzónák, checkpointok
    (közös vagy gyerekenkénti, jutalomsávok aszerint, mennyivel előtte, beleszámít-e
    a sorozatba), checkpointokhoz kötött feladatok; példa-rutinok egy gombnyomásra;
  - jutalmak: ikon, zsetonkupacként mutatott ár, perselyfeloldás; példák;
  - zsetonok: kézi jóváírás és levonás; előzmények visszavonással és
    összegmódosítással;
  - beállítások: nyelv, animációk, napi sorozat, heti perselykamat, a gombok a
    hozzájuk rendelt gyerekek avatarjaival.
- Csak bővülő zsetonnapló (pénztárca és persely): az egyenleg mindig az
  előzmények összege; visszavonás és módosítás soha nem töröl semmit.
- Checkpoint-jutalom időbeli sávok szerint, napi sorozat (éjfél után értékelve,
  a cél elérésekor jutalommal), heti kamatos perselykamat opcionális minimummal
  és maximummal.
- Eszköz–gyerek hozzárendelés: egy gyerek legfeljebb egy gombhoz tartozik; ha egy
  gombhoz vannak gyerekek rendelve, a többiek szürkén, zárolva látszanak; a gyerek
  nélküli (vagy mindenkihez rendelt) gomb mindenkinek működik.
- Knob-protokoll (docs/protocol.md): a Home Assistant tömör állapotképet küld
  (`set_state`); a knob az elvégzett feladatokat és a beváltott jutalmakat egyedi
  azonosítójú JSON-műveletként jelenti az új Action szenzorán, és ezek legfeljebb
  egyszer könyvelődnek.
- A knobon a funkció-körhinta a gyerek mai rutinjait mutatja; az időív a rutin
  színzónáit, a közös checkpointokat a külső, a gyerek sajátjait a belső íven, és az
  éppen elérhető jutalmat.
- Home Assistant műveletek automatizáláshoz (`kis_segito.complete_task`,
  `complete_checkpoint`, `adjust_tokens`, `redeem_reward`, `piggy_deposit`,
  `piggy_withdraw`, `reverse_transaction`) és a `kis_segito_event` esemény
  (docs/automations.md).
- Az ikonkészlet minden ikonja elérhető a knobon és a panelen.

## [0.2.2] - 2026-10-07

### English

- The time track is shown on every screen, above the content, on a band in
  the background colour with a soft inner edge, so sliding carousel items do
  not disturb it: the shared outer track (colour zones, elapsed time, now
  marker, global checkpoints) and the selected child's inner track (also on
  the child carousel, following the centred child).
- The top gap shows the brand mark on every screen; on a routine it shows
  the reward available now instead. Screen content moved inside the track.
- The child carousel slides smoothly: each slot (avatar, token pile, number)
  is rendered into one image (#10).
- Language changes apply live (texts, brand mark, boot screen) without a
  restart, and are written to flash right away.
- The offline marker moved to the right of the top gap.
- Screen saver against burn-in: the backlight dims after 60 s and switches
  off after 120 s without knob input; any input wakes it without acting.
  "Screen dim after" and "Screen off after" are adjustable from Home
  Assistant (0 disables a step).
- Whenever the backlight is off (switch, screen saver, automation), the screen
  content is black and drawing pauses; it comes back when the backlight is on.

### Magyar

- Az időív minden képernyőn látszik, a tartalom fölött, egy háttérszínű,
  átmenetes peremű sávon, így a csúszó körhinta-elemek nem zavarják: a közös
  külső ív (színzónák, eltelt idő, „most” jelölő, közös checkpointok) és a
  kiválasztott gyerek belső íve (a gyerek-körhintán is, a középső gyerekhez
  igazodva).
- A felső résben minden képernyőn a márkajel látszik; rutin közben helyette
  az éppen elérhető jutalom. A képernyők tartalma az íven belülre került.
- A gyerek-körhinta egyenletesen csúszik: minden hely (avatar, zsetonkupac,
  szám) egyetlen képpé renderelődik (#10).
- A nyelvváltás élőben érvényesül (feliratok, márkajel, indítóképernyő)
  újraindítás nélkül, és azonnal flash-be íródik.
- A kapcsolat-hiány jelzése a felső rés jobb oldalára került.
- Képernyővédő a beégés ellen: 60 s tétlenség után a háttérvilágítás
  elhalványul, 120 s után kikapcsol; bármilyen tekerés vagy gombnyomás
  felébreszti, de nem lép vele. A „Screen dim after” és „Screen off after” idő
  a Home Assistantből állítható (a 0 kikapcsolja az adott lépést).
- Ha a háttérvilágítás bármilyen módon kikapcsol (kapcsoló, képernyővédő,
  automatizmus), a kijelző tartalma fekete, és a rajzolás szünetel;
  bekapcsoláskor visszajön.

## [0.2.1] - 2026-10-07

### English

- Boot screen: the Kis Segítő brand mark in the middle, the loading text below
  it, the balls bouncing behind them. The brand mark is Hungarian when the
  language is Hungarian and English ("Little Helper") otherwise. The language
  is kept in flash for the next boot.
- The routine screen's top gap uses the same language-specific brand mark.
- Logo at the top of the README (Hungarian and English section).
- `tools/build_device_assets.py`: `_fallbacks` in `assets/device_assets.json`
  render an icon from another source while its own artwork is missing.

### Magyar

- Indítóképernyő: középen a Kis Segítő márkajel, alatta a betöltés felirat,
  mögöttük pattognak a labdák. Magyar nyelv esetén a magyar, minden más
  nyelven az angol („Little Helper”) márkajel látszik. A nyelvet a knob a
  következő indításhoz flash-ben tárolja.
- Az időív felső résében is ez a nyelvfüggő márkajel látszik.
- Logó a README tetején (a magyar és az angol részben is).
- `tools/build_device_assets.py`: az `assets/device_assets.json` `_fallbacks`
  részében megadott ikonok saját rajz hiányában egy másik forrásból készülnek.

## [0.2.0] - 2026-10-06

### English

First version of the child UI on the knob, with built-in test data (Home
Assistant data follows in a later version):

- Child carousel (infinite) with avatar and a real token pile of exactly the
  wallet balance; large balances spread sideways and "flow" off the screen.
  The last selected child is remembered across reboots.
- Function carousel per child: morning and evening routine, rewards, piggy bank
  (when unlocked), tokens and streak.
- Routine screen: open time track from 11 to 1 o'clock with the future colour
  zones visible from the start, elapsed time dimmed, checkpoint markers on the
  outer and inner track, the reward available now in the top gap, the current
  task large and the others on a curved timeline (done on the left, grey).
  Completing a task bounces and checks it; finishing the routine celebrates.
- Reward store carousel with prices shown as token piles, locked rewards
  greyed out, and an X/✓ confirmation with a ring around the selected choice;
  the exact number of spent tokens fly away.
- Short press selects, long press goes back one level; after 60 s without input
  the knob returns to the child carousel. Without a Home Assistant connection an
  offline marker is shown and token transactions are refused.
- Animation level (full / reduced / off) as a setting in Home Assistant.
- Loading screen balls are now layered images: a recoloured round ball that
  briefly turns into a dented ball on impact (the dent faces the contact point),
  and a highlight that never rotates or deforms. The highlight position is
  adjustable with the `ball_highlight_dx` / `ball_highlight_dy` substitutions.
- Language setting in the Kis Segítő panel: "Automatic" (the Home Assistant
  language, English when there is no translation) or any available
  translation. It applies to the knobs and to the panel; the list comes from the
  translation files.
- Icon pipeline: source artwork in `assets/icons/source`, rendered by
  `tools/build_device_assets.py`; the icon list is in `docs/icons.md`. The icons
  are placeholder sketches for now.

### Magyar

A knob gyerekfelületének első változata, beépített tesztadatokkal (a Home
Assistant adatai egy későbbi verzióban jönnek):

- Gyerek-körhinta (végtelen) avatarral és valódi zsetonkupaccal, pontosan a tárca
  egyenlegével; nagy egyenlegnél a kupac szétterül, majd „lefolyik” a
  kijelzőről. Az utoljára kiválasztott gyerek újraindítás után is megmarad.
- Gyerekenkénti funkció-körhinta: reggeli és esti rutin, jutalmak, persely (ha
  feloldották), zsetonok és sorozat.
- Rutinképernyő: nyitott időív 11 órától 1 óráig, a jövőbeli színzónák az
  elejétől látszanak, az eltelt idő elhalványul, checkpoint-jelölők a külső és a
  belső íven, a most járó jutalom a felső résben, az aktuális feladat nagyban, a
  többi egy íves idővonalon (a kész feladatok balra, szürkén). Feladat
  teljesítésekor pattanás és pipa, a rutin végén ünneplés.
- Jutalombolt-körhinta, az árak zsetonkupacként, a nem megfizethető jutalmak
  szürkén, X/✓ megerősítés gyűrűvel a kiválasztott elem körül; a pontos számú
  elköltött zseton elrepül.
- Rövid nyomás: kiválasztás, hosszú nyomás: egy szinttel vissza; 60 s tétlenség
  után vissza a gyerek-körhintára. Home Assistant-kapcsolat nélkül offline jelzés
  látszik, és a zseton-tranzakciók le vannak tiltva.
- Animációs szint (teljes / csökkentett / ki) beállításként a Home Assistantben.
- A betöltőképernyő labdái rétegzett képek: színezett kerek labda, amely
  ütközéskor rövid időre horpadt labdára vált (a horpadás az ütközési pont felé
  néz), és egy csillanás, amely sosem forog és nem torzul. A csillanás helye a
  `ball_highlight_dx` / `ball_highlight_dy` helyettesítésekkel állítható.
- Nyelvválasztó a Kis Segítő panelen: „Automatikus” (a Home Assistant nyelve,
  fordítás hiányában angol) vagy bármelyik elérhető fordítás. A knobokra és a
  panelre is érvényes; a lista a fordítási fájlokból jön.
- Ikon-csővezeték: forrásrajzok az `assets/icons/source` mappában, a méreteket a
  `tools/build_device_assets.py` készíti; az ikonlista a `docs/icons.md`-ben.
  Az ikonok egyelőre helyettesítő vázlatok.

## [0.1.11] - 2026-10-06

### English

- Loading screen: five bouncing balls (one more), and they now also bounce off
  each other, not only off the round edge.

### Magyar

- Betöltőképernyő: öt pattogó labda (eggyel több), és most már egymásról is
  visszapattannak, nem csak a kerek szélről.

## [0.1.10] - 2026-10-06

### English

- Fix: the display stayed blank on USB chargers and only worked with a PC (#8).
  The cause was ESP-IDF's secondary console on the native USB port. It is now
  off, and the serial log moved to UART0 (GPIO43/44); `logger_baud_rate: "0"`
  turns it off and frees UART0 for other hardware. Logs remain available over
  the network.
- Improv over USB is removed (it needs the native USB port); Wi-Fi is set up
  through the knob's own access point (captive portal).
- The `no-usb-console.yaml` diagnostic package is removed, as this is now the
  default.
- The loading screen shows colourful bouncing balls instead of the spinner
  (#9). They bounce off the round edge with a small squash; the animation stops
  and its timer is freed once the content arrives.

### Magyar

- Javítás: töltőről a kijelző üres maradt, csak számítógépről működött (#8). Az
  ok az ESP-IDF másodlagos konzolja volt a natív USB-porton. Ez most ki van
  kapcsolva, a soros napló az UART0-ra (GPIO43/44) került; a
  `logger_baud_rate: "0"` kikapcsolja, és felszabadítja az UART0-t más
  hardvernek. A napló hálózaton továbbra is elérhető.
- Az USB-s Improv kikerült (a natív USB-portot használná); a WiFi a knob saját
  hozzáférési pontján (captive portal) állítható be.
- A `no-usb-console.yaml` diagnosztikai package kikerült, mert ez lett az
  alapállapot.
- A betöltőképernyőn a forgó jel helyett színes pattogó labdák vannak (#9). A
  kerek kijelző szélén pattannak vissza, kicsit összenyomódva; a tartalom
  megérkezésekor az animáció leáll, és az időzítője felszabadul.

## [0.1.9] - 2026-10-06

### English

- Diagnostic packages for the display staying blank on USB chargers (#8, still
  open), in `esphome/diagnostics/`: `no-usb-console.yaml` (native USB port
  unused, logs over the network only), `jtag-pins.yaml` (GPIO39–42 reset to
  plain GPIO before the RGB panel starts) and `verbose-display-log.yaml`
  (verbose display/LVGL logs). See `docs/hardware.md`. The normal firmware is
  unchanged.

### Magyar

- Diagnosztikai package-ek ahhoz a hibához, hogy töltőről a kijelző nem
  működik (#8, még nyitott), az `esphome/diagnostics/` mappában:
  `no-usb-console.yaml` (a natív USB-port nincs használatban, napló csak
  hálózaton), `jtag-pins.yaml` (a GPIO39–42 sima GPIO-ra állítása az RGB-panel
  indulása előtt) és `verbose-display-log.yaml` (részletes kijelző/LVGL-napló).
  Lásd: `docs/hardware.md`. A normál firmware nem változott.

## [0.1.8] - 2026-10-06

### English

- The encoder sensitivity is adjustable from Home Assistant (#7): a new
  **Encoder clicks per step** setting (1–5, default 1) on the device, kept
  across reboots. The encoder now counts at full resolution and the firmware
  turns clicks into steps. The `encoder_resolution` substitution is replaced by
  `encoder_counts_per_click` (default `"2"`) for other encoders. The raw
  encoder counter is no longer exposed to Home Assistant.

### Magyar

- Az enkóder érzékenysége a Home Assistantből állítható (#7): új **Encoder
  clicks per step** beállítás (1–5, alapból 1) az eszközön, újraindítás után is
  megmarad. Az enkóder most teljes felbontással számol, a kattanásokat a
  firmware alakítja lépésekké. Az `encoder_resolution` substitution helyett
  más enkóderhez az `encoder_counts_per_click` állítható (alapból `"2"`). A nyers
  enkóderszámláló már nem jelenik meg a Home Assistantben.

## [0.1.7] - 2026-10-06

### English

- Fix: one encoder click is now one step; `encoder_resolution` defaults to `"2"`
  (#7). The README explains how to tune it for other encoders.
- Display diagnostics for the faint stripes on black (#6, still open):
  `display-test.yaml` can show solid black, white, grey, very dark grey or a
  grey ramp (`display_test_pattern`), and the new `display_drive_strength`
  substitution sets the drive strength of the RGB bus pins. COLMOD 0x77 can be
  tested with `display_colmod: "0x77"`.

### Magyar

- Javítás: egy kattanás most egy lépés; az `encoder_resolution` alapértéke `"2"`
  (#7). A README leírja, hogyan hangolható más enkóderhez.
- Kijelző-diagnosztika a fekete háttér halvány csíkjaihoz (#6, még nyitott): a
  `display-test.yaml` teli fekete, fehér, szürke, nagyon sötét szürke képet vagy
  szürke átmenetet tud mutatni (`display_test_pattern`), és az új
  `display_drive_strength` substitution az RGB-busz lábainak meghajtóerejét
  állítja. A COLMOD 0x77 a `display_colmod: "0x77"` beállítással próbálható.

## [0.1.6] - 2026-10-06

### English

- Fix attempt for wrong mid-tone colours on the MD80E (#4). The panel init now
  follows the factory demo exactly: init table, 120 ms, DISPON, with **no
  COLMOD**, so the panel stays in its 24-bit power-on mode, which matches the
  board wiring. ESPHome's own COLMOD/MADCTL/INVOFF are no longer sent (the
  sequence is replaced at boot, before the display starts).
- New substitution `display_colmod` (`"0"` = none, default; `"0x55"` restores
  the v0.1.5 behaviour). It replaces `display_pixel_mode`; the no-longer-used
  `display_color_order` and `display_invert_colors` are removed.
- Fix: the encoder counted down when turned clockwise; A/B pins swapped (#5).

### Magyar

- Javítási kísérlet a rossz középtónusokra az MD80E-n (#4). A panel initje most
  pontosan a gyári demót követi: init tábla, 120 ms, DISPON, **COLMOD nélkül**,
  így a panel a bekapcsolási 24 bites módjában marad, ami egyezik a lap
  bekötésével. Az ESPHome saját COLMOD/MADCTL/INVOFF parancsai már nem mennek
  ki (a szekvencia bootkor, a kijelző indulása előtt cserélődik).
- Új substitution: `display_colmod` (`"0"` = nincs, alapértelmezett; `"0x55"`
  a v0.1.5 viselkedését adja vissza). Ez váltja a `display_pixel_mode`-ot; a
  használaton kívüli `display_color_order` és `display_invert_colors` kikerült.
- Javítás: az enkóder jobbra forgatásra csökkent; az A/B láb felcserélve (#5).

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

[0.2.0]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.2.0
[0.1.11]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.11
[0.1.10]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.10
[0.1.9]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.9
[0.1.8]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.8
[0.1.7]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.7
[0.1.6]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.6
[0.1.5]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.5
[0.1.4]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.4
[0.1.3]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.3
[0.1.2]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.2
[0.1.1]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.1
[0.1.0]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.0
