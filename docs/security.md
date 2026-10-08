<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# Security

Kis Segítő runs entirely on your local network: the knob talks only to your Home
Assistant, and the integration only to your knobs.

## Secrets for each knob

Put these in the ESPHome `secrets.yaml` next to your device config; see
[esphome/example.yaml](../esphome/example.yaml):

| Secret | Used for |
|---|---|
| `kis_segito_api_key` | Encryption of the connection to Home Assistant. Use a **separate key for each knob**. |
| `ota_password` | Password for firmware updates over the network. |
| `ap_password` | Password of the knob's fallback access point. |
| `wifi_ssid`, `wifi_password` | Your Wi-Fi. |

```yaml
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

A new encryption key can be generated on <https://esphome.io/components/api/>
(or with `openssl rand -base64 32`). After installing a config with a new or
changed key, enter the same key in Home Assistant: the ESPHome integration asks
for it, or use **Reconfigure** on the knob's ESPHome entry.

**Ready-made firmware.** The firmware attached to a release has no secrets: until
you adopt it, its connection is not encrypted and updates need no password. Adopt
it in the ESPHome Builder right after the first start, add the lines above and
install it again.

**Fallback access point.** It opens only when the knob cannot join your Wi-Fi,
and it is the only way to change Wi-Fi without a cable. Its setup page also
accepts a firmware upload, which is why it needs a password.

## Pictures

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

## Messages from the knob

Home Assistant accepts only well-formed messages from a knob (at most 255 bytes,
exactly the expected fields, types and ranges) and at most 20 per minute per
knob; anything else is ignored. Each action is booked at most once, even if the
knob sends it again after a reconnect.

## Updates and downloads

The example config points to a given version of the package (`@vX.Y.Z`), so the
knob's firmware changes only when you change it to a newer version.

Every release lists the SHA-256 checksums of its firmware files in
`SHA256SUMS.txt`. To check a downloaded file, put it next to that file and run
`sha256sum -c --ignore-missing SHA256SUMS.txt` (Linux, macOS); "OK" means the file
is exactly the released one. The release builds use build steps pinned to exact
versions.

## Out of scope

Anyone holding the knob can read its flash memory (and the secrets in it) or
install other firmware over USB. This is a DIY device for the home, so flash
encryption and secure boot are not part of the project.
