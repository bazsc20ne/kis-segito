#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Print the CHANGELOG.md section of one version (for the GitHub Release body).

Usage: release_notes.py vX.Y.Z
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    version = sys.argv[1].removeprefix("v")
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    pattern = rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)"
    match = re.search(pattern, changelog, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"No CHANGELOG.md section for {version}", file=sys.stderr)
        return 1
    print(match.group(1).strip())
    tested = tested_with()
    if tested:
        print(f"\n---\n\n{tested}")
    return 0


def tested_with() -> str:
    """The ESPHome and Home Assistant versions this release was tested with."""
    release = (ROOT / ".github/workflows/release.yml").read_text("utf-8")
    esphome = re.search(r"^\s+version:\s*([\d.]+)\s*$", release, re.MULTILINE)
    requirements = (ROOT / "requirements_test.txt").read_text("utf-8")
    hass = re.search(r"^homeassistant==([\d.]+)", requirements, re.MULTILINE)
    if not (esphome and hass):
        return ""
    return (
        f"Built and tested with ESPHome {esphome.group(1)} and Home Assistant "
        f"{hass.group(1)}. / Az ESPHome {esphome.group(1)} és a Home Assistant "
        f"{hass.group(1)} verzióval fordítva és tesztelve."
    )


if __name__ == "__main__":
    sys.exit(main())
