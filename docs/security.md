<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Biztonság / Security

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>

## Magyar

A Kis Segítő teljes egészében a helyi hálózatodon fut: a gomb csak a saját Home
Assistantoddal beszél, az integráció pedig csak a saját gombjaiddal.

### Titkok gombonként

Ezeket az ESPHome `secrets.yaml` fájlba írd, az eszközkonfigurációd mellé; lásd
[esphome/example.yaml](../esphome/example.yaml):

| Titok | Mire való |
|---|---|
| `kis_segito_api_key` | A Home Assistant felé menő kapcsolat titkosítása. **Minden gombhoz külön kulcsot** használj. |
| `ap_password` | A gomb tartalék hozzáférési pontjának jelszava. |
| `wifi_ssid`, `wifi_password` | A Wi-Fi-d. |

```yaml
api:
  encryption:
    key: !secret kis_segito_api_key

ota:
  - id: !extend kis_segito_ota
    # A frissítések a fenti API-kulcsot használják (titkosítva és hitelesítve).
    encryption:

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    password: !secret ap_password
```

Új titkosítási kulcsot a <https://esphome.io/components/api/> oldalon lehet
generálni (vagy az `openssl rand -base64 32` paranccsal). Miután új vagy
megváltozott kulccsal telepítettél egy konfigurációt, add meg ugyanazt a kulcsot
a Home Assistantben: az ESPHome integráció rákérdez, vagy használd az
**Újrakonfigurálás** lehetőséget a gomb ESPHome-bejegyzésén.

**A hálózaton keresztüli frissítések** ugyanazt az API-kulcsot használják: az
`ota` alatti `encryption:` sorral minden firmware-feltöltés titkosított, és csak
a kulcs birtokában lévő feltöltőt fogadja el a gomb. OTA-jelszóra nincs szükség
(és nem is kombinálható az `encryption`-nel). Vigyázz a kulcsra: egy gombot,
amelynek a kulcsa elveszett, csak USB-n lehet újra flashelni, és a kulcs a
levegőn keresztül nem változtatható meg.

**Átállás OTA-jelszóról** (a 0.9.3 előtti konfigurációkban
`password: !secret ota_password` szerepelt). A még a régi firmware-rel futó gomb
még egyszer kéri a jelszót, ezért a változás utáni első telepítés mindkettőt
tartalmazza:

```yaml
ota:
  - id: !extend kis_segito_ota
    password: !secret ota_password
    encryption:
      allow_plaintext_upload: true   # csak erre az egy telepítésre
```

E telepítés után a gomb már csak titkosított feltöltést fogad el. Ezután töröld
a `password` és az `allow_plaintext_upload` sort, hogy a blokk csak
`encryption:` legyen, mint fent, és töröld az `ota_password` titkot a
`secrets.yaml` fájlból. Ha az első lépést kihagyod, a feltöltés hitelesítési
hibával meghiúsul, és a gomb megtartja a firmware-ét; semmi nem romlik el.

**Kész firmware.** A kiadásokhoz csatolt firmware-ben nincsenek titkok: amíg át
nem veszed, a kapcsolata nincs titkosítva, és a frissítésekhez nem kell jelszó.
Vedd át az ESPHome Builderbe rögtön az első indítás után, add hozzá a fenti
sorokat, és telepítsd újra.

<a id="tartalek-hozzaferesi-pont"></a>

### Tartalék hozzáférési pont

**Mire való.** Ha a gomb kb. másfél percig nem tud csatlakozni a WiFi-dhez,
megnyitja a saját WiFi-jét (a neve a gomb neve, alapból `kis-segito`). Erre a
telefonnal csatlakozva megnyílik egy beállítóoldal, ahol új WiFi-hálózat adható
meg; ez az egyetlen kábel nélküli módja a WiFi cseréjének. Ha egy frissítés után
a gomb nem jön vissza, a lépések a README-ben vannak
([magyarul](../README.md#3-a-gomb-frissítése)). A beállítóoldal firmware-feltöltést
is elfogad, ezért a hozzáférési pontnak mindig van jelszava.

**Saját konfiggal (ESPHome Builder).** A jelszó a `secrets.yaml` `ap_password`
értéke (a konfigban: `wifi: ap: password: !secret ap_password`). A Builderben a
jobb felső **Secrets** gombbal nézheted meg és változtathatod; az új jelszó a
következő telepítéssel kerül a gombra. A gomb kijelzője ilyenkor csak a
hozzáférési pont nevét mutatja, a jelszót nem. A 0.9.17-es és újabb firmware a
jelszót a gombon is elmenti, így egy kiadási frissítés után is ugyanez marad.

**Kész firmware, saját jelszó nélkül.** A gomb első induláskor egy 10 karakteres
véletlen jelszót készít, és elmenti. Amíg a hozzáférési pont nyitva van, a gomb
kijelzője mutatja a nevét és ezt a jelszót. A jelszó újraindítás és frissítés után
is megmarad; másikat úgy adhatsz meg, hogy a gombot saját konfiggal, `ap_password`-del
telepíted (a Builderből), új véletlen jelszót pedig a gomb törlésével (USB-s
telepítés törléssel) kap.

**Jó jelszó.** Legalább 8 karakter (a WiFi ennél rövidebbet nem fogad el), és ne
az otthoni WiFi-d jelszava legyen: aki a gomb hozzáférési pontjára csatlakozik, ne
tudja meg vele az otthoni hálózatodét.

**Kiadási frissítés.** A kiadás firmware-ében nincs WiFi-adat és API-kulcs. A
0.9.16-os és újabb firmware ezért a saját konfigodban megadott WiFi-hálózatot és
API-kulcsot elmenti a gomb saját tárolójába (ahol a firmware-ben is benne voltak),
és a kiadásból telepített firmware ezeket használja; a hálózati frissítés is az
API-kulccsal titkosított marad.

### Ki mit módosíthat

A Kis Segítő panelje minden Home Assistant-felhasználónak megnyílik. A Home
Assistant adminjai mindent módosíthatnak. A többi felhasználó a **Beállítások →
Általános → Felhasználók és hozzáférés** részen szerkesztő vagy csak megtekintő
lehet; aki nincs beállítva, az csak megtekintő.

- **Szerkesztő:** gyerekek, rutinok, jutalmak, sablonok, naptár és napi
  módosítások, zsetonok és javítások, jóváhagyások, valamint a kártyákon a
  feladatok és a jutalmak.
- **Csak admin:** a Beállítások oldal (gombok, képernyő, témák, háttér, ikonok,
  nyelv, Assist, felhasználók), az értesítések, a virtuális gombok, az adatexport
  és -import.

### Képek

A feltöltött képek (a gyerekek fényképei, jutalmak, hátterek) csak a helyi
hálózaton és csak titkosított kapcsolaton jutnak el a gombhoz:

- Minden gomb saját, véletlenszerű képkulcsot kap, és csak addig, amíg a Home
  Assistant felé menő kapcsolata titkosított. Ha nem az, a Home Assistant
  javítandó problémát jelez (**Beállítások → Rendszer → Javítások**), és a gomb
  a képek helyett ikonokat mutat, amíg titkosítási kulcsot nem adsz hozzá.
- A gomb képcíme csak a helyi hálózatról érkező kérésekre válaszol (privát,
  loopback vagy link-local címekről), sosem a Home Assistant Cloudon keresztül
  vagy az internetről érkezőkre.
- A gomb a kulcsát kérésfejlécben küldi, sosem a címben, így a kulcs nem kerül
  naplókba; a kulcsok összehasonlítása állandó idejű.
- Egy gomb kulcsa bármikor lecserélhető: panel → **Beállítások → Gombok → Új
  képkulcs**. A régi kulcs azonnal érvényét veszti; a gomb automatikusan
  megkapja az újat.

A képeket a rendszer automatikusan átméretezi a gombhoz. Mielőtt egy képet
beolvasna, ellenőrzi a valódi típusát (nem csak a fájlnevét), és elutasítja a
30 MB-nál nagyobb fájlokat és a 100 megapixelnél nagyobb képeket; a nagy
fényképeket csökkentett felbontásban olvassa be. A gombra kerülő példány csak
képpontokat tartalmaz, metaadatokat (EXIF, helyadatok) nem.

### Üzenetek a gombtól

A Home Assistant csak a szabályos üzeneteket fogadja el egy gombtól (legfeljebb
255 bájt, pontosan a várt mezők, típusok és értéktartományok), és gombonként
legfeljebb percenként 20-at; minden mást figyelmen kívül hagy. Minden műveletet
legfeljebb egyszer könyvel, akkor is, ha a gomb újracsatlakozás után újra
elküldi.

### Frissítések és letöltések

A gomb firmware-e csak akkor változik, ha te telepítesz egy új verziót: a gomb
**Release firmware** frissítés-entitásával, vagy saját buildnél a csomag
verziójának (`@vX.Y.Z`) átírásával. A frissítés-entitás a kiadást HTTPS-en, a GitHub
tanúsítványának ellenőrzésével tölti le, és telepítés előtt összeveti a fájlt a
kiadás leíró fájljában (`update.json`) szereplő MD5-összeggel; eltérés vagy
megszakadt letöltés esetén a gomb a régi firmware-rel fut tovább.

Minden kiadás felsorolja a firmware-fájljai SHA-256 ellenőrzőösszegét a
`SHA256SUMS.txt` fájlban. Egy letöltött fájl ellenőrzéséhez tedd e fájl mellé,
és futtasd: `sha256sum -c --ignore-missing SHA256SUMS.txt` (Linux, macOS); az
„OK” azt jelenti, hogy a fájl pontosan a kiadott fájl. A kiadások pontos
verziókra rögzített build-lépésekkel készülnek.

### Ami nem része a projektnek

Aki kézben tartja a gombot, ki tudja olvasni a flash-memóriáját (és a benne lévő
titkokat), vagy USB-n más firmware-t telepíthet rá. Ez egy otthoni, saját
készítésű eszköz, ezért a flash-titkosítás és a biztonságos rendszerindítás
(secure boot) nem része a projektnek.

---

<a id="english"></a>

## English

🇭🇺 [Magyar változat](#magyar)

Little Helper runs entirely on your local network: the knob talks only to your Home
Assistant, and the integration only to your knobs.

### Secrets for each knob

Put these in the ESPHome `secrets.yaml` next to your device config; see
[esphome/example.yaml](../esphome/example.yaml):

| Secret | Used for |
|---|---|
| `kis_segito_api_key` | Encryption of the connection to Home Assistant. Use a **separate key for each knob**. |
| `ap_password` | Password of the knob's fallback access point. |
| `wifi_ssid`, `wifi_password` | Your Wi-Fi. |

```yaml
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

A new encryption key can be generated on <https://esphome.io/components/api/>
(or with `openssl rand -base64 32`). After installing a config with a new or
changed key, enter the same key in Home Assistant: the ESPHome integration asks
for it, or use **Reconfigure** on the knob's ESPHome entry.

**Updates over the network** use the same API key: with `encryption:` under
`ota`, every firmware upload is encrypted and only an uploader with the key is
accepted. No OTA password is needed (and it cannot be combined with
`encryption`). Keep the key safe: a knob whose key is lost can only be flashed
again over USB, and the key cannot be changed over the air.

**Moving from an OTA password** (configs before 0.9.3 had
`password: !secret ota_password`). The knob still running the old firmware asks
for the password once more, so the first install after the change carries both:

```yaml
ota:
  - id: !extend kis_segito_ota
    password: !secret ota_password
    encryption:
      allow_plaintext_upload: true   # only for this one install
```

After that install the knob accepts encrypted uploads only. Then remove the
`password` and `allow_plaintext_upload` lines, so the block is just
`encryption:` as above, and delete `ota_password` from `secrets.yaml`. If you
skip the first step, the upload fails with an authentication error and the
knob keeps its firmware; nothing breaks.

**Ready-made firmware.** The firmware attached to a release has no secrets: until
you adopt it, its connection is not encrypted and updates need no password. Adopt
it in the ESPHome Builder right after the first start, add the lines above and
install it again.

<a id="fallback-access-point"></a>

### Fallback access point

**What it is for.** When the knob cannot join your Wi-Fi for about a minute and
a half, it opens its own Wi-Fi (named after the knob, `kis-segito` by default).
Connecting to it with a phone opens a setup page where a new Wi-Fi network can be
entered; this is the only way to change Wi-Fi without a cable. If the knob does
not come back after an update, the steps are in the README
([English](../README.md#3-updating-the-knob)). The setup page also accepts a
firmware upload, so the access point always has a password.

**With your own config (ESPHome Builder).** The password is `ap_password` in
`secrets.yaml` (in the config: `wifi: ap: password: !secret ap_password`). In the
Builder, the **Secrets** button at the top right shows and changes it; the new
password reaches the knob with the next install. The knob's screen then shows only
the access point's name, not the password. Firmware 0.9.17 and newer also saves the
password on the knob, so it stays the same after a release update.

**Prebuilt firmware without your own password.** At its first start the knob makes
a random 10-character password and saves it. While the access point is open, the
knob's screen shows its name and this password. The password stays over restarts
and updates; to set another, install the knob with your own config and an
`ap_password` (from the Builder), and to get a new random one, erase the knob (a USB
install with erase).

**A good password.** At least 8 characters (Wi-Fi does not accept a shorter one),
and not your home Wi-Fi password: someone who joins the knob's access point should
not learn your home network's password from it.

**Release updates.** The release firmware has no Wi-Fi details and no API key.
Firmware 0.9.16 and newer therefore saves the Wi-Fi network and the API key from
your own config in the knob's own storage (where they already were, inside the
firmware), and the firmware installed from a release uses them; network updates
stay encrypted with the API key.

### Who can change what

The Little Helper panel opens for every Home Assistant user. Home Assistant
admins can change everything. Other users can be editors or view only under
**Settings → General → Users and access**; anyone not set is view only.

- **Editors:** children, routines, rewards, templates, the calendar and one-day
  changes, tokens and corrections, approvals, and tasks and rewards on the
  dashboard cards.
- **Admins only:** the Settings page (knobs, screen, themes, background, icons,
  language, Assist, users), notifications, virtual knobs, data export and import.

### Pictures

Uploaded pictures (children's photos, rewards, backgrounds) reach the knob only on
the local network and only over an encrypted connection:

- Each knob gets its own random picture key, and only while its connection to
  Home Assistant is encrypted. If it is not, Home Assistant shows a repair issue
  (**Settings → System → Repairs**) and the knob shows icons instead of the
  pictures until you add an encryption key.
- The knob's picture address answers only requests from the local network
  (private, loopback or link-local addresses), never requests through Home
  Assistant Cloud or from the internet.
- The knob sends its key in a request header, never in the address, so the key
  does not end up in logs; keys are compared in constant time.
- A knob's key can be replaced at any time: panel → **Settings → Knobs → New
  picture key**. The old key stops working at once; the knob gets the new one
  automatically.

Pictures are resized for the knob automatically. Before a picture is read, its
real type is checked (not only its file name), and files over 30 MB or images
over 100 megapixels are refused; large photos are read at a reduced resolution.
The knob's copy contains pixels only, no metadata (EXIF, location).

### Messages from the knob

Home Assistant accepts only well-formed messages from a knob (at most 255 bytes,
exactly the expected fields, types and ranges) and at most 20 per minute per
knob; anything else is ignored. Each action is booked at most once, even if the
knob sends it again after a reconnect.

### Updates and downloads

The knob's firmware changes only when you install a new version: with the knob's
**Release firmware** update entity, or, with your own build, by changing the
package version (`@vX.Y.Z`). The update entity downloads the release over HTTPS,
checking GitHub's certificate, and compares the file with the MD5 checksum in the
release's manifest (`update.json`) before installing; on a mismatch or a broken
download the knob keeps running the old firmware.

Every release lists the SHA-256 checksums of its firmware files in
`SHA256SUMS.txt`. To check a downloaded file, put it next to that file and run
`sha256sum -c --ignore-missing SHA256SUMS.txt` (Linux, macOS); "OK" means the file
is exactly the released one. The release builds use build steps pinned to exact
versions.

### Out of scope

Anyone holding the knob can read its flash memory (and the secrets in it) or
install other firmware over USB. This is a DIY device for the home, so flash
encryption and secure boot are not part of the project.
