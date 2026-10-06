# Hardware / Hardver

**VIEWE UEDX48480021-MD80E** – 2.1" round 480×480 IPS knob, no touch panel.

- ESP32-S3 (WROOM-1 N16R8): 16 MB flash, 8 MB octal PSRAM
- Display controller: GC9503CV, RGB interface (16 data lines used) + 3-wire SPI for the init sequence
- Input: rotary encoder (A/B) and push button – no touch

Source: VIEWESMART schematic `MD80E.SCH.20240725_00` and the vendor's ESP-IDF
example for this board, `examples/ESP-IDF/UEDX48480021-MD80E-SDK`
([VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob), MIT).
The panel (UE021WV-RB40-L002B) uses a **GC9503CV** controller per its datasheet.
The vendor example contains two init tables: an active ST7701-style one and a
commented-out GC9503 one. The factory demo firmware runs the **GC9503** table at
26 MHz, so that is the default (`esphome/hardware/panel/gc9503.yaml`). The
ST7701-style table (`panel/st7701.yaml`) leaves the red channel dark on this
panel, and ESPHome's built-in `UEDX48480021-MD80ET` model gives only stripes.

The init table is sent the way the vendor code does it, from an `on_boot` step
in `esphome/hardware/board.yaml` that runs before the display: bit-banged 9-bit
3-wire SPI (CS/SCK/SDA idle high, about 50 kHz), no reset pulse, 120 ms, DISPON,
then GPIO12/13 are released to the RGB driver. ESPHome's `mipi_rgb` display runs
with its generic `RPI` model, which sends no init and uses no SPI.

## Display timings / Kijelző-időzítés

From the vendor `esp-bsp.h`; all are substitutions in `esphome/hardware/board.yaml`.

| Setting | Value | Substitution |
|---|---|---|
| Init sequence | GC9503 table | `display_controller` (`gc9503` or `st7701`) |
| PCLK | 26 MHz, not inverted | `display_pclk_frequency`, `display_pclk_inverted` |
| HSYNC pulse / back / front | 8 / 20 / 40 | `display_hsync_pulse_width`, `display_hsync_back_porch`, `display_hsync_front_porch` |
| VSYNC pulse / back / front | 8 / 20 / 50 | `display_vsync_pulse_width`, `display_vsync_back_porch`, `display_vsync_front_porch` |
| Init diagnostic: send INVON after the table | off | `display_init_test_invert` (`"true"` inverts the colours if the init reaches the panel) |

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
| LCD SPI SCK / SDA | 13 / 12 | shared with RGB data; bit-banged init, then released |
| LCD reset | 8 | driven high only (as the vendor code); the panel RST is tied to chip EN |
| Backlight | 7 | P-MOSFET, **low = on** (PWM, inverted) |
| Encoder A / B | 6 / 5 | external 4.7 kΩ pull-ups |
| Push button | 0 | active low, external 4.7 kΩ pull-up; strapping pin |
| Free on J1/J2 | 4 (ADC) | also UART TX/RX, USB D+/D− |

## Tuning / Hangolás

Any value above can be overridden in the device config without forking, e.g.:

```yaml
substitutions:
  display_controller: st7701
  display_pclk_inverted: "true"
  display_init_test_invert: "true"
  encoder_resolution: "2"        # encoder steps per detent: 1 (default), 2 or 4
```

A fenti értékek fork nélkül, az eszközkonfig `substitutions` részében átírhatók.

## Display test / Kijelzőteszt

`esphome/display-test.yaml` uses the same board definition without LVGL and shows
ESPHome's test card (colour bars, border, text). Flash it over the air to the same
device, check the picture, then flash the normal firmware back. With the default
settings the test card should show sharp colour bars in the right order; stripes
or a rolling image point to PCLK/porch settings. With
`display_init_test_invert: "true"` the colours must invert; if they do not, the
init does not reach the panel.

Az `esphome/display-test.yaml` ugyanazt a lapdefiníciót használja LVGL nélkül, és
az ESPHome tesztképét mutatja. OTA-val ugyanarra az eszközre tölthető, a teszt
után a normál firmware visszatölthető.
