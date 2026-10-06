#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check that all version numbers agree (and match the git tag, if given).

Usage: check_versions.py [vX.Y.Z]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    manifest = json.loads(
        (ROOT / "custom_components/kis_segito/manifest.json").read_text("utf-8")
    )
    versions = {"manifest.json": manifest["version"]}

    esphome = (ROOT / "esphome/kis-segito.yaml").read_text("utf-8")
    match = re.search(r'^\s+version:\s*"([^"]+)"', esphome, re.MULTILINE)
    versions["esphome project"] = match.group(1) if match else "<missing>"

    for label, pattern in (
        ("esphome components ref", r"kis_segito_components: github://bazsc20ne/kis-segito@v([\d.]+)"),
        ("esphome assets ref", r"kis_segito_assets: https://raw\.githubusercontent\.com/bazsc20ne/kis-segito/v([\d.]+)/"),
    ):
        match = re.search(pattern, esphome)
        versions[label] = match.group(1) if match else "<missing>"

    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    versions["CHANGELOG.md (latest)"] = match.group(1) if match else "<missing>"

    if len(sys.argv) > 1:
        versions["git tag"] = sys.argv[1].removeprefix("v")

    for source, version in versions.items():
        print(f"{source}: {version}")
    if len(set(versions.values())) != 1:
        print("Version mismatch", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
