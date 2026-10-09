# Hardware / Hardver

**VIEWE UEDX48480021-MD80E** – 2.1" round 480×480 IPS knob, no touch panel.

- ESP32-S3 (WROOM-1 N16R8): 16 MB flash, 8 MB octal PSRAM
- Display controller: GC9503CV, RGB interface (16 data lines used) + 3-wire SPI for the init sequence
- Input: rotary encoder (A/B) and push button – no touch

## Display settings / Kijelző-beállítások

Defaults that work for this knob; each can be changed with a substitution (see
Tuning below).

| Setting | Value | Substitution |
|---|---|---|
| Init sequence | GC9503 table | `display_controller` (`gc9503` or `st7701`) |
| PCLK | 18 MHz, not inverted | `display_pclk_frequency`, `display_pclk_inverted` |
| HSYNC pulse / back / front | 8 / 20 / 40 | `display_hsync_pulse_width`, `display_hsync_back_porch`, `display_hsync_front_porch` |
| VSYNC pulse / back / front | 8 / 20 / 50 | `display_vsync_pulse_width`, `display_vsync_back_porch`, `display_vsync_front_porch` |
| COLMOD after the table | none | `display_colmod` (`"0"`, `"0x55"`, `"0x66"`, `"0x77"`) |
| Serial log on UART0 (GPIO43/44) | 115200 baud | `logger_baud_rate` (`"0"` = off, frees UART0) |
| RGB bus drive strength | ESP-IDF default | `display_drive_strength` (`"-1"` = default, `"0"`…`"3"` ≈ 5/10/20/40 mA) |

## USB

USB is needed only for the first flash; after that the firmware is updated over
the network, and its logs are visible in Home Assistant / the ESPHome Builder.
The knob also works from a plain USB charger.

Az USB csak az első felíráshoz kell; utána a firmware hálózaton frissíthető, a
napló a Home Assistantben / az ESPHome Builderben látható. A knob sima USB-s
töltőről is működik.

## Picture cache / Képgyorsítótár

The knob keeps the pictures it downloads from Home Assistant (avatars, icons,
backgrounds) in a 4 MB area of its flash, so after a restart they appear at once
and are not downloaded again; once after each start the knob only checks with
Home Assistant whether they changed. When the area is full, the pictures not
used for the longest time make room.

The area is a partition of its own. An update over the network keeps the
partition table, so a knob first installed with version 0.7.6 or older gets the
cache only after flashing the factory firmware (`*.factory.bin`) over USB once.
Until then everything works the same, only the pictures are downloaded again
after each start. Flashing the factory firmware resets the knob's own settings
(e.g. encoder clicks per step) to their defaults.

A knob a Home Assistanttől letöltött képeket (avatarok, ikonok, hátterek) a
flash egy 4 MB-os részében tárolja, így újraindulás után azonnal megjelennek, és
nem kell újra letölteni őket; indulásonként egyszer csak azt kérdezi meg a Home
Assistanttől, változtak-e. Ha a terület megtelik, a legrégebben nem használt
képek adnak helyet.

A terület külön partíció. A hálózati frissítés a partíciótáblát nem cseréli,
ezért a 0.7.6-os vagy régebbi verzióval telepített knob csak akkor kapja meg a
gyorsítótárat, ha egyszer USB-n felírod a gyári firmware-t (`*.factory.bin`).
Addig minden ugyanúgy működik, csak a képeket minden indulás után újra letölti.
A gyári firmware felírása a knob saját beállításait (pl. lépésenkénti
kattintások) alapértékre állítja.

## Reading the serial log / Soros napló

If the knob restarts before it reaches Wi-Fi (for example after an update), its
messages are only on the serial port UART0: GPIO43 (TX) and GPIO44 (RX) on the
debug board's TX/RX pins, 115200 baud. Connect a 3.3 V USB-UART adapter (adapter
RX to knob TX, adapter TX to knob RX, GND to GND) and open it with any serial
terminal, e.g. `esphome logs` with the adapter's port. After such a restart the
knob also logs why its previous run ended ("Previous run ended by: …") once it is
back and connected to Home Assistant.

Ha a knob még a WiFi előtt újraindul (például frissítés után), az üzenetei csak a
soros porton (UART0) érhetők el: GPIO43 (TX) és GPIO44 (RX) a debug panel TX/RX
lábain, 115200 baud. Egy 3,3 V-os USB-UART adapterrel olvasható (adapter RX a knob
TX-ére, adapter TX a knob RX-ére, GND a GND-re). Ilyenkor a knob a következő sikeres
indulás után azt is naplózza, miért ért véget az előző futása.

## Pinout / Lábkiosztás

| Function | GPIO | Notes |
|---|---|---|
| LCD R3–R7 | 40, 41, 42, 2, 1 | |
| LCD G2–G7 | 21, 47, 48, 45, 38, 39 | |
| LCD B3–B7 | 10, 11, 12, 13, 14 | B5/B6 shared with SPI SDA/SCK |
| LCD PCLK | 9 | |
| LCD DE | 17 | |
| LCD HSYNC | 46 | strapping pin |
| LCD VSYNC | 3 | strapping pin |
| LCD SPI CS | 18 | 3-wire SPI, init only |
| LCD SPI SCK / SDA | 13 / 12 | shared with RGB data, software SPI |
| LCD reset | 8 | the panel RST is also tied to chip EN |
| Backlight | 7 | P-MOSFET, **low = on** (PWM, inverted) |
| Encoder A / B | 6 / 5 (vendor naming) | external 4.7 kΩ pull-ups; the firmware uses A=5, B=6 so clockwise counts up; 2 counts per click at full resolution |
| Push button | 0 | active low, external 4.7 kΩ pull-up; strapping pin |
| Free on J1/J2 | 4 (ADC) | also UART0 TX/RX (GPIO43/44, serial log by default), USB D+/D− |

## Tuning / Hangolás

Any value above can be overridden in the device config without forking, e.g.:

```yaml
substitutions:
  display_colmod: "0x55"
  display_pclk_inverted: "true"
  encoder_counts_per_click: "4"  # encoder counts per click (default 2)
  encoder_debug: "true"          # log every raw encoder count (checking detents)
  lvgl_buffer_size: "50%"        # draw buffer (default 100%; less saves PSRAM)
```

A fenti értékek fork nélkül, az eszközkonfig `substitutions` részében átírhatók.

## Display test / Kijelzőteszt

`esphome/display-test.yaml` uses the same board definition without LVGL. The
`display_test_pattern` substitution selects what it shows: `card` (ESPHome's test
card: colour bars, border, text), `black`, `white`, `grey`, `dark` (very dark
grey) or `ramp` (black-to-white horizontal ramp). Flash it over the air to the same
device, check the picture, then flash the normal firmware back. With the default
settings the test card shows sharp colour bars in the right order.

Az `esphome/display-test.yaml` ugyanazt a lapdefiníciót használja LVGL nélkül, és
az ESPHome tesztképét mutatja. OTA-val ugyanarra az eszközre tölthető, a teszt
után a normál firmware visszatölthető.

## If the picture looks wrong / Ha a kép hibás

The defaults match this knob's panel (GC9503CV controller, as the vendor's
factory firmware). If your unit behaves differently:

- only stripes or a rolling picture: check the PCLK and porch settings;
- wrong colours in the middle tones (the test card's gradient columns): try
  `display_colmod: "0x55"`;
- red missing: keep `display_controller: gc9503` (the `st7701` table leaves red
  dark on this panel);
- faint stripes on black: try a different `display_drive_strength`.

Az alapértékek ennek a knobnak a paneljéhez valók. Ha a kép hibás: csíkok vagy
gördülő kép esetén a PCLK- és porch-beállításokat, rossz középtónusoknál a
`display_colmod: "0x55"` értéket, hiányzó pirosnál a `display_controller: gc9503`
beállítást, fekete háttéren látszó halvány csíkoknál más `display_drive_strength`
értéket érdemes kipróbálni.

## Diagnostic packages / Diagnosztikai package-ek

Optional packages in `esphome/diagnostics/` for tracking down display problems.
Add one or more next to the main package in the device config, with the same
version tag:

```yaml
packages:
  kis_segito: github://bazsc20ne/kis-segito/esphome/kis-segito.yaml@vX.Y.Z
  diag_jtag: github://bazsc20ne/kis-segito/esphome/diagnostics/jtag-pins.yaml@vX.Y.Z
```

| Package | What it does |
|---|---|
| `jtag-pins.yaml` | Resets GPIO39–42 (also the pad-JTAG pins, used here as RGB data lines) to plain GPIO right before the RGB panel is created. |
| `verbose-display-log.yaml` | Very verbose logging for the display driver and LVGL (each area written to the panel buffer is logged); noisy components stay at DEBUG. |

Opcionális package-ek a kijelzőhibák kereséséhez (`esphome/diagnostics/`). Az
eszközkonfigban a fő package mellé kell felvenni őket, ugyanazzal a verziótaggel.

