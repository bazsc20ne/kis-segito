#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Print the firmware manifest of a release (ESP Web Tools format), read by
the knob's "Release firmware" update entity (as update.json; firmware before
0.9.16 looked for manifest.json and cannot keep its Wi-Fi and key across such
an update, so it is not offered one).

Usage: firmware_manifest.py vX.Y.Z <md5 of the OTA file>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = "https://github.com/bazsc20ne/kis-segito"
ROOT = Path(__file__).resolve().parent.parent
# Home Assistant shows at most 255 characters of an update's summary.
SUMMARY_MAX = 255


def summary(tag: str) -> str:
    """The bold titles of the version's changes, Hungarian line first, then
    English, for Home Assistant's update dialog."""
    version = tag.removeprefix("v")
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    section = re.search(
        rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL
    )
    if not section:
        return ""
    lines = []
    for language in ("Magyar", "English"):
        part = re.search(
            rf"^### {language}\s*$(.*?)(?=^### |\Z)", section.group(1), re.MULTILINE | re.DOTALL
        )
        if not part:
            continue
        titles = [t.rstrip(":").strip() for t in re.findall(r"^- \*\*(.+?)\*\*", part.group(1), re.MULTILINE)]
        if titles:
            lines.append("; ".join(titles) + ".")
    text = "\n".join(lines)
    return text if len(text) <= SUMMARY_MAX else text[: SUMMARY_MAX - 1].rstrip() + "…"


def main() -> int:
    tag, md5 = sys.argv[1], sys.argv[2]
    download = f"{REPO}/releases/download/{tag}"
    manifest = {
        "name": "Kis Segítő - Little Helper",
        "version": tag.removeprefix("v"),
        "home_assistant_domain": "esphome",
        "new_install_prompt_erase": False,
        "builds": [
            {
                "chipFamily": "ESP32-S3",
                "parts": [{"path": f"{download}/kis-segito-{tag}.factory.bin", "offset": 0}],
                "ota": {
                    "path": f"{download}/kis-segito-{tag}.ota.bin",
                    "md5": md5,
                    "release_url": f"{REPO}/releases/tag/{tag}",
                    "summary": summary(tag),
                },
            }
        ],
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
