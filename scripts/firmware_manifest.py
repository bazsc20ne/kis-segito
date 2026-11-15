#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Print the firmware manifest of a release (ESP Web Tools format), read by
the knob's "Release firmware" update entity.

Usage: firmware_manifest.py vX.Y.Z <md5 of the OTA file>
"""

from __future__ import annotations

import json
import sys

REPO = "https://github.com/bazsc20ne/kis-segito"


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
                },
            }
        ],
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
