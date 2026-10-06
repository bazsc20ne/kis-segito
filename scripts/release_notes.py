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
    return 0


if __name__ == "__main__":
    sys.exit(main())
