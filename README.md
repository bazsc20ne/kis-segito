# Kis Segítő

ESP32-S3 alapú, kerek kijelzős forgatógomb (rotary knob) Home Assistanthez – ESPHome + LVGL felülettel, és hozzá tartozó HA dashboarddal.

## Hardver

- **VIEWE UEDX48480021-MD80E** (érintés **nélküli** változat) – 2.1" kerek, 480×480 IPS kijelzős forgatógomb
  - ESP32-S3-R8: 8 MB Octal PSRAM, 16 MB flash
  - kijelző-meghajtó: ST7701S (RGB)
  - kezelés: csak forgatás + nyomás (nincs érintőpanel – a felületet enkóderre kell tervezni)
  - első felíráshoz USB-s debug/adapter panel

### Referenciák

- Gyártói minta- és doksi-repók: [VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob), [VIEWESMART/UEDX48480021-MD80ESP32-2.1inch-Touch-Knob-Display](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32-2.1inch-Touch-Knob-Display)
- Közösségi ESPHome konfig (érintés nélküli változat, referencia): [Greg-79/UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-](https://github.com/Greg-79/UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-)
- ESPHome feature request: [esphome/feature-requests#3254](https://github.com/esphome/feature-requests/issues/3254)
- Spotpear wiki: <https://spotpear.com/wiki/ESP32-S3-2.1-inch-Round-Rotary-LCD-Screen-Knob-Display.html>

## Felépítés (terv)

- `esphome/` – ESPHome package a knobhoz (a HA ESPHome Builderében egy vékony helyi YAML húzza be `packages: github://…`-tal)
- `homeassistant/` – Lovelace dashboard, scriptek, automációk
- `docs/` – fotók, bekötés, jegyzetek

## Titkok

WiFi-jelszó, API-kulcs, token **soha** nem kerül a repóba – mindig `!secret`, a `secrets.yaml` a HA-ban marad.

## Köszönet és források

- **VIEWESMART** – gyári mintakód, kapcsolási rajz, lábkiosztás és kijelző-inicializálás (MIT licenc): [UEDX48480021-MD80ESP32_2.1inch-Knob](https://github.com/VIEWESMART/UEDX48480021-MD80ESP32_2.1inch-Knob)
- **Greg-79** – ESPHome-konfiguráció ehhez a kijelzőhöz (a README szerint MIT licenc): [UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-](https://github.com/Greg-79/UEDX48480021-MD80ESP32-2.1inch-Knob-Display-no-touch-)

## Licenc / License

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

**GNU Affero General Public License v3.0** – szabadon használható, forkolható és módosítható. Aki módosított változatot terjeszt vagy hálózati szolgáltatásként futtat, köteles a teljes forráskódot ugyanezen licenc alatt közzétenni.

*English:* Free to use, fork and modify. Anyone who distributes a modified version, or runs it as a network service, must publish the complete source code under the same license.

A felhasznált harmadik féltől származó anyagok a saját licencük alatt maradnak (pl. VIEWESMART – MIT, ESPHome – GPLv3/MIT).

## Hozzájárulás / Contributing

Ez egy személyes projekt: **pull requestet nem fogadok el**. Hibajelentést és ötletet issue-ként szívesen látok, és bárki szabadon forkolhatja a licenc szerint.

*English:* This is a personal project: **pull requests are not accepted**. Bug reports and ideas are welcome as issues, and you are free to fork it under the license terms.
