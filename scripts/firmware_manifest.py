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
# The notes Home Assistant's update dialog shows (Markdown); kept short.
SUMMARY_MAX = 1500


def summary(tag: str) -> str:
    """Release notes for Home Assistant's update dialog, in Markdown: the
    version, then the Hungarian and the English list, one short sentence per
    change (the bold first sentence of each change in CHANGELOG.md)."""
    version = tag.removeprefix("v")
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    section = re.search(
        rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL
    )
    if not section:
        return ""
    parts = [f"**Kis Segítő – Little Helper {version}**"]
    for language in ("Magyar", "English"):
        part = re.search(
            rf"^### {language}\s*$(.*?)(?=^### |\Z)", section.group(1), re.MULTILINE | re.DOTALL
        )
        if not part:
            continue
        titles = [t.strip() for t in re.findall(r"^- \*\*(.+?)\*\*", part.group(1), re.MULTILINE)]
        if titles:
            parts.append(f"**{language}**\n\n" + "\n".join(f"- {t}" for t in titles))
    text = "\n\n".join(parts)
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
