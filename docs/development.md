# Development / Fejlesztés

## Layout

| Path | What |
|---|---|
| `custom_components/kis_segito/` | Home Assistant integration (HACS) |
| `custom_components/kis_segito/frontend/` | Sidebar panel (plain web component, no build step) and its translations |
| `custom_components/kis_segito/device_translations/` | Texts shown on the knob display, one JSON per language |
| `esphome/kis-segito.yaml` | ESPHome package (the firmware) |
| `esphome/kis-segito-factory.yaml` | Config built by CI for releases / web installer |
| `esphome/example.yaml` | Example device config for users |
| `tests/` | pytest tests for the integration |
| `scripts/` | Release helpers (version check, release notes) |

## Adding a language / Új nyelv

Add one file per part, named by the Home Assistant language code (e.g. `de.json`):

1. `custom_components/kis_segito/translations/` – config flow texts
2. `custom_components/kis_segito/frontend/translations/` – panel texts
3. `custom_components/kis_segito/device_translations/` – knob display texts

Missing keys fall back to English. The knob fonts cover Latin, Greek and Cyrillic
scripts; other scripts need extra glyphs in `esphome/kis-segito.yaml`.

## Local checks

```sh
pip install -r requirements_test.txt
pytest
python3 scripts/check_versions.py
cd esphome && cp secrets.example.yaml secrets.yaml && esphome config kis-segito-factory.yaml
```

## Release

1. Bump the version in `custom_components/kis_segito/manifest.json`,
   `esphome/kis-segito.yaml` (`project.version`), `esphome/example.yaml`
   (package ref) and add a `CHANGELOG.md` section (English + Hungarian).
2. Commit and push to `main`, then either push a `vX.Y.Z` tag or run the
   `Release` workflow manually (Actions → Release → Run workflow, version
   `X.Y.Z`); the manual run creates the tag on the commit it runs on.
3. The `Release` workflow checks the versions, builds the firmware and publishes
   the GitHub Release with the changelog section and the `.factory.bin` /
   `.ota.bin` files.
