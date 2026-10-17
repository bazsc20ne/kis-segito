<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Sensors / Érzékelők

With a presence, distance or light sensor the knob reacts to the room by
itself: it wakes when someone comes near, shows a night light in the dark and
sets its brightness to the room light. The logic runs on the knob, so it works
even while Home Assistant is busy or restarting.

Jelenlét-, távolság- vagy fényérzékelővel a gomb magától reagál a szobára:
felébred, ha valaki közel jön, sötétben éjszakai fényt mutat, és a fényerejét a
szoba fényéhez igazítja. A logika a gombon fut, így akkor is működik, ha a Home
Assistant éppen foglalt vagy újraindul.

## What the knob does / Mit csinál a gomb

The settings are on the panel: **Settings → Sensors**. Each part can be switched
off.

- **Presence wakes the screen.** When someone comes near, the screensaver
  stops and the screen fades in softly. With a distance sensor, "near" means
  closer than the set distance (default 80 cm); without one, anyone detected.
- **Screensaver from absence.** With a presence sensor the screen stages
  (screensaver, dimming, drawing off, backlight off) count from when someone
  was last near the knob, not from the last turn or press. Without a presence
  sensor they count from the last input, as before.
- **Night light.** Below the set light level (default 5 lx) someone in the
  room gets a white light (colour temperature and brightness are settings)
  with a small black crescent moon in the middle, instead of the child screen.
  - With a distance sensor, distance decides: closer than the set distance the
    child screen comes up, further away only the night light shows. Without a
    distance sensor (e.g. a PIR), a turn or press brings up the child screen.
  - Once the child screen has been shown it does not go back to the night
    light; it continues with the screensaver and then switches off.
  - When the night light starts, the white background appears first and the
    light fades up quickly. When nobody has been there for the set time
    (default 1 minute), the light fades out first, then the background is
    cleared.
- **Daytime.** Above the light level the child screen comes up only for
  someone near; otherwise the screen stays in the screensaver or off.
- **Brightness from the room light.** The backlight follows the room light
  between the lowest and highest brightness setting, smoothly, so it never
  dazzles in the dark.

A beállítások a panelen vannak: **Beállítások → Érzékelők**. Mindegyik rész
kikapcsolható.

- **Jelenlétre felébred a képernyő.** Ha valaki közel jön, a képernyővédő
  leáll, és a képernyő lágyan bejön. Távolságérzékelővel a „közel” a beállított
  távolságnál közelebbit jelenti (alapból 80 cm), anélkül bárkit, akit érzékel.
- **Képernyővédő távollétre.** Jelenlétérzékelővel a képernyő lépései
  (képernyővédő, halványítás, rajzolás leállítása, háttérvilágítás ki) attól
  számítanak, hogy utoljára valaki a gomb közelében volt, nem az utolsó
  tekeréstől vagy nyomástól. Jelenlétérzékelő nélkül az utolsó használattól,
  mint eddig.
- **Éjszakai fény.** A beállított fényszint alatt (alapból 5 lx) a szobában
  lévő a gyerekképernyő helyett fehér fényt kap (színhőmérséklete és erőssége
  beállítható), közepén egy kis fekete holdsarlóval.
  - Távolságérzékelővel a távolság dönt: a beállított távolságnál közelebb a
    gyerekképernyő jön elő, távolabb csak az éjszakai fény. Távolságérzékelő
    nélkül (pl. PIR) tekeréssel vagy gombnyomással jön elő a gyerekképernyő.
  - Ha a gyerekképernyő egyszer megjelent, nem tér vissza az éjszakai fényre:
    képernyővédővel folytatja, majd kikapcsol.
  - Induláskor előbb a fehér háttér jelenik meg, aztán a fény gyorsan
    felerősödik. Ha a beállított ideig (alapból 1 perc) senki sincs ott, előbb
    a fény halványul el, aztán tűnik el a háttér.
- **Nappal.** A fényszint felett a gyerekképernyő csak a közel lévőnek jön elő;
  egyébként a képernyő képernyővédőn vagy kikapcsolva marad.
- **Fényerő a szoba fényéből.** A háttérvilágítás a legkisebb és a legnagyobb
  beállított fényerő között követi a szoba fényét, lágyan, így sötétben sosem
  vakít.

## Wiring a sensor to the knob / Érzékelő bekötése a gombra

The firmware has three inputs: **presence** (`ks_presence`, on/off),
**distance** (`ks_distance`, cm) and **illuminance** (`ks_illuminance`, lx). It
does not depend on the sensor type: wire any sensor ESPHome supports to a free
pin and pass its value to the input in your device config:

```yaml
binary_sensor:
  - platform: …            # your presence sensor
    on_state:
      - binary_sensor.template.publish:
          id: ks_presence
          state: !lambda return x;

sensor:
  - platform: …            # your distance sensor, in cm
    on_value:
      - sensor.template.publish:
          id: ks_distance
          state: !lambda return x;
  - platform: …            # your light sensor, in lx
    on_value:
      - sensor.template.publish:
          id: ks_illuminance
          state: !lambda return x;
```

A firmware-nek három bemenete van: **jelenlét** (`ks_presence`, be/ki),
**távolság** (`ks_distance`, cm) és **megvilágítás** (`ks_illuminance`, lx).
Nem függ az érzékelő típusától: bármelyik, az ESPHome által támogatott
érzékelőt bekötheted egy szabad lábra, és az eszközkonfigodban átadod az értékét
a bemenetnek (lásd fent).

The free pins of the VIEWE MD80E knob and its debug board are in
[hardware.md](hardware.md#free-pins--szabad-lábak). GPIO43/44 are free for
sensors only with `logger_uart: UART1` in the substitutions.

A VIEWE MD80E gomb és a debug panel szabad lábai a
[hardware.md](hardware.md#free-pins--szabad-lábak)-ben vannak. A GPIO43/44
csak `logger_uart: UART1` beállítással szabad az érzékelőknek.

### LD2410C radar + VEML7700 light sensor (tested) / LD2410C radar + VEML7700 fényérzékelő (kipróbálva)

Wiring on the MD80E debug board / Bekötés az MD80E debug paneljén:

| Sensor pin | Debug board pin | GPIO |
|---|---|---|
| LD2410C TX | RX2 | GPIO15 |
| LD2410C RX | TX2 | GPIO16 |
| LD2410C VCC / GND | 5V / GND | – |
| VEML7700 SDA | TX1 | GPIO43 |
| VEML7700 SCL | RX1 | GPIO44 |
| VEML7700 VIN / GND | see below / lásd lent | – |

```yaml
substitutions:
  logger_uart: UART1   # frees GPIO43/44 (TX1/RX1); the log stays on the network

uart:
  id: radar_uart
  rx_pin: GPIO15
  tx_pin: GPIO16
  baud_rate: 256000
  parity: NONE
  stop_bits: 1

ld2410:
  uart_id: radar_uart

i2c:
  sda: GPIO43
  scl: GPIO44
  frequency: 100kHz

binary_sensor:
  - platform: ld2410
    has_target:
      name: Radar presence
      on_state:
        - binary_sensor.template.publish:
            id: ks_presence
            state: !lambda return x;

sensor:
  - platform: ld2410
    detection_distance:
      name: Radar distance
      on_value:
        - sensor.template.publish:
            id: ks_distance
            state: !lambda return x;
  - platform: veml7700
    update_interval: 10s
    ambient_light:
      name: Room light
      on_value:
        - sensor.template.publish:
            id: ks_illuminance
            state: !lambda return x;
```

**VEML7700-type breakouts with a level shifter** pull SDA and SCL up to their
VIN (10 kΩ on the module). The ESP32-S3 pins take at most 3.3 V. Two tested
ways:

1. VIN = 3.3 V from a small step-down converter (Mini360 or similar) set to
   3.3 V.
2. VIN = 5 V, plus a 15 kΩ resistor from SDA to GND and one from SCL to GND:
   with the module's 10 kΩ pull-ups the lines stay at about 3.0 V.

**A szintillesztős VEML7700-típusú modulok** az SDA-t és az SCL-t a saját
VIN-jükre húzzák fel (10 kΩ a modulon). Az ESP32-S3 lábai legfeljebb 3,3 V-ot
bírnak. Két kipróbált megoldás:

1. VIN = 3,3 V egy kis, 3,3 V-ra állított step-down átalakítóról (Mini360 vagy
   hasonló).
2. VIN = 5 V, és egy-egy 15 kΩ-os ellenállás az SDA és a GND, valamint az SCL
   és a GND közé: a modul 10 kΩ-os felhúzóival a vonalakon kb. 3,0 V marad.

### PIR motion sensor (presence only) / PIR mozgásérzékelő (csak jelenlét)

A PIR has no distance: in the dark it gives the night light, and a turn or
press of the knob brings up the child screen. GPIO4 (PB7 on the debug board)
has a filter on the board, too slow for I²C but fine for a PIR.

A PIR-nek nincs távolsága: sötétben éjszakai fényt ad, a gyerekképernyőt a gomb
tekerése vagy megnyomása hozza elő. A GPIO4 (a debug panelen PB7) a panelen
szűrve van: I²C-hez túl lassú, PIR-hez megfelel.

```yaml
binary_sensor:
  - platform: gpio
    name: Motion
    device_class: motion
    pin: GPIO4
    on_state:
      - binary_sensor.template.publish:
          id: ks_presence
          state: !lambda return x;
```

### LD2450 radar

Distance of the first target; the LD2450 reports millimetres.

Az első célpont távolsága; az LD2450 milliméterben mér.

```yaml
uart:
  id: radar_uart
  rx_pin: GPIO15
  tx_pin: GPIO16
  baud_rate: 256000

ld2450:
  uart_id: radar_uart

binary_sensor:
  - platform: ld2450
    has_target:
      name: Radar presence
      on_state:
        - binary_sensor.template.publish:
            id: ks_presence
            state: !lambda return x;

sensor:
  - platform: ld2450
    target_1:
      distance:
        name: Radar distance
        on_value:
          - sensor.template.publish:
              id: ks_distance
              state: !lambda return x / 10.0f;   # mm -> cm
```

### BH1750 light sensor / BH1750 fényérzékelő

```yaml
i2c:
  sda: GPIO43
  scl: GPIO44
  frequency: 100kHz

sensor:
  - platform: bh1750
    name: Room light
    update_interval: 10s
    on_value:
      - sensor.template.publish:
          id: ks_illuminance
          state: !lambda return x;
```

Other light sensors (TSL2561, TSL2591, VEML6030 …) work the same way.

Más fényérzékelők (TSL2561, TSL2591, VEML6030 …) ugyanígy működnek.

### VL53L0X distance sensor / VL53L0X távolságérzékelő

A small time-of-flight sensor on the I²C bus; it measures metres. Use it
together with a presence sensor: distance alone does not set presence.

Kis, I²C-s fényidő-mérő; méterben mér. Jelenlétérzékelővel együtt használd: a
távolság önmagában nem jelez jelenlétet.

```yaml
sensor:
  - platform: vl53l0x
    name: Distance to the knob
    update_interval: 1s
    on_value:
      - sensor.template.publish:
          id: ks_distance
          state: !lambda return x * 100.0f;   # m -> cm
```

## Sensors from Home Assistant / Érzékelők a Home Assistantból

A knob without its own sensors can use Home Assistant entities: panel →
**Settings → Knobs → Sensors from Home Assistant**. Choose a presence entity
(occupancy or motion binary sensor, person or device tracker), a distance
sensor and an illuminance sensor; the integration forwards their values to the
knob whenever they change. Distances in m or mm are converted to cm. The
behaviour is the same as with sensors on the knob, but it depends on Home
Assistant and the network.

Saját érzékelő nélküli gomb Home Assistant-entitásokat is használhat: panel →
**Beállítások → Gombok → Érzékelők a Home Assistantból**. Válassz
jelenlét-entitást (jelenlét- vagy mozgásérzékelő, személy vagy eszközkövető),
távolság- és megvilágításérzékelőt; az integráció minden változáskor átküldi
az értéküket a gombnak. A m-ben vagy mm-ben megadott távolságot cm-re váltja.
A működés ugyanaz, mint a gombra kötött érzékelőkkel, de a Home Assistanttől és
a hálózattól függ.

## In Home Assistant / A Home Assistantban

The knob's device shows **Presence**, **Distance**, **Illuminance**, **Night
light**, **Screensaver** and **Screen brightness**. Automations can wake the
screen, start or end the screensaver and switch the night light: see
[automations.md](automations.md#knob-screen--a-gomb-képernyője).

A gomb eszközén látható a **Presence** (jelenlét), **Distance** (távolság),
**Illuminance** (megvilágítás), **Night light** (éjszakai fény), **Screensaver**
(képernyővédő) és **Screen brightness** (fényerő). Automatizálással a képernyő
felébreszthető, a képernyővédő és az éjszakai fény be- és kikapcsolható: lásd
[automations.md](automations.md#knob-screen--a-gomb-képernyője).

## Tips / Tippek

- Place the light sensor where the screen does not shine on it, otherwise the
  knob's own light raises the reading.
- A radar also sees a child sleeping in its range: the night light then stays
  on. Limit the radar's range (its gate settings) to the area in front of the
  knob.

- A fényérzékelőt úgy helyezd el, hogy ne érje a képernyő fénye, különben a gomb
  saját fénye megemeli a mért értéket.
- A radar az alvó gyereket is látja a hatótávolságán belül: ilyenkor az
  éjszakai fény bekapcsolva marad. A radar hatótávolságát (kapubeállításait)
  korlátozd a gomb előtti területre.
