<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# Security

Kis Segítő runs entirely on your local network: the knob talks only to your Home
Assistant, and the integration only to your knobs. This page lists what protects
that link and what you have to set up yourself.

## Required secrets for each knob

Put these in the ESPHome `secrets.yaml` next to your device config; see [esphome/example.yaml](../esphome/example.yaml):

| Secret | Used for |
|---|---|
| `kis_segito_api_key` | Encryption of the ESPHome native API. Use a **separate key for each knob**. |
| `ota_password` | Password for firmware updates over the network (OTA). |
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

A new API key is 32 random bytes in Base64, for example from
`openssl rand -base64 32`, or from the generator on
<https://esphome.io/components/api/>. After installing a config with a new or
changed key, enter the same key in Home Assistant (the ESPHome integration asks
for it, or use **Reconfigure** on the knob's ESPHome entry).

**Ready-made firmware.** The factory firmware from a release has no secrets: its
API is not encrypted and OTA has no password until you adopt it. Adopt it in the
ESPHome Builder right after the first start, add the lines above (the Builder
usually generates the API key itself) and install the result.

**Fallback access point.** It opens only when the knob cannot join your Wi-Fi,
and it is the only way to change Wi-Fi without a cable. Its setup page
(captive portal) also accepts a firmware upload, which is why it needs a
password.

## Encrypted API and the picture key

The integration sends each knob a random picture key, which the knob uses to
download uploaded pictures (avatars, rewards). The key is sent **only when the
knob's API connection is encrypted**. Without encryption the knob shows its
icons instead of pictures, and Home Assistant shows a repair issue
(**Settings → System → Repairs**) until you add an API key.

The picture endpoint:

- answers only requests from the local network (private, loopback or link-local
  addresses), never requests through Home Assistant Cloud or from the internet;
- takes the key from the `X-Kis-Segito-Token` request header only, never from
  the URL, so it does not end up in logs;
- compares keys in constant time.

A knob's key can be replaced at any time: panel → **Settings → Knobs → New
picture key**. The old key stops working at once; the knob gets the new one
automatically.

## What the integration accepts

- **Knob actions** (the knob's Action sensor) must be small, well-formed JSON
  with exactly the expected fields, types and ranges; anything else is ignored.
  Each knob can send at most 20 actions per minute, and the list of processed
  action ids is limited in age and size. Details:
  [protocol.md](protocol.md#knob--home-assistant).
- **Uploaded pictures** are always resized for the knob. Before decoding, the
  integration checks the real image type (not the file name), refuses files over
  30 MB and images over 100 megapixels, and decodes large JPEG photos at a
  reduced scale. The knob's copy contains pixels only, without the original's
  metadata (EXIF, location).

## Installing and updating safely

- Reference the ESPHome package **by its release tag** (`…/kis-segito.yaml@vX.Y.Z`),
  never `@main`: a tag does not change under you.
- Every release lists the SHA-256 checksums of its firmware files in
  `SHA256SUMS.txt`. Check a download before flashing it:

  ```sh
  sha256sum -c --ignore-missing SHA256SUMS.txt
  ```

- The release workflow uses GitHub Actions pinned to exact commits.

## Out of scope

Physical access: anyone holding the knob can read its flash memory (and the
secrets in it) or flash new firmware over USB. This is a DIY device for the
home, so flash encryption and secure boot are not part of the project.
