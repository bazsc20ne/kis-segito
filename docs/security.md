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

Uploaded pictures (children's photos, rewards) reach the knob only on the local
network and only over an encrypted connection; they cannot be reached through
Home Assistant Cloud or the internet. If a knob's connection is not encrypted,
Home Assistant shows a repair issue (**Settings → System → Repairs**) and the
knob shows icons instead of the pictures until you add an encryption key.

A knob's access to the pictures can be renewed at any time: panel → **Settings →
Knobs → New picture key**. The knob gets the new key automatically.

Pictures are resized for the knob automatically; images over 100 megapixels are
refused. The knob's copy contains no metadata (EXIF, location).

## Updates

The example config points to a given version of the package (`@vX.Y.Z`), so the
knob's firmware changes only when you change it to a newer version.

## Out of scope

Anyone holding the knob can read its flash memory (and the secrets in it) or
install other firmware over USB. This is a DIY device for the home, so flash
encryption and secure boot are not part of the project.
