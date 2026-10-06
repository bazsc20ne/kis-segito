# Hardware / Hardver

**VIEWE UEDX48480021-MD80E** – 2.1" round 480×480 IPS knob, no touch panel.

- ESP32-S3 (WROOM-1 N16R8): 16 MB flash, 8 MB octal PSRAM
- Display controller: ST7701S, 16-bit RGB (RGB565) + 3-wire SPI for the init sequence
- Input: rotary encoder (A/B) and push button – no touch

Source: VIEWESMART schematic `MD80E.SCH.20240725_00` and BSP
([VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob), MIT).
ESPHome ships the panel definition as the `UEDX48480021-MD80ET` model of the
`mipi_rgb` display platform (the touch variant has the same panel and pinout).

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
| Encoder A / B | 6 / 5 | external 4.7 kΩ pull-ups |
| Push button | 0 | active low, external 4.7 kΩ pull-up; strapping pin |
| Free on J1/J2 | 4 (ADC) | also UART TX/RX, USB D+/D− |

## Tuning / Hangolás

If a panel batch shows wrong colours or the encoder counts double, the device
config can override these substitutions without forking:

```yaml
substitutions:
  display_color_order: BGR       # RGB (default) or BGR
  display_invert_colors: "true"  # default "false"
  encoder_resolution: "2"        # 1 (default), 2 or 4
```

Ha egy panel-sorozat rossz színeket mutat, vagy az enkóder duplán számol, a fenti
`substitutions` értékekkel fork nélkül hangolható.
