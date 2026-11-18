#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the integration's zip for a release (what HACS installs in one
download) and check that it holds the whole integration.

Usage: integration_zip.py <output.zip> [vX.Y.Z]
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "custom_components" / "kis_segito"


def files() -> list[Path]:
    """The integration's files (without Python caches)."""
    return sorted(
        p
        for p in SOURCE.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )


def main() -> int:
    out = Path(sys.argv[1])
    tag = sys.argv[2] if len(sys.argv) > 2 else None
    expected = files()
    out.parent.mkdir(parents=True, exist_ok=True)
    # The files sit at the zip's root: HACS unpacks it into the
    # custom_components/kis_segito folder.
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in expected:
            archive.write(path, path.relative_to(SOURCE).as_posix())
    with zipfile.ZipFile(out) as archive:
        names = set(archive.namelist())
        if archive.testzip() is not None:
            print("The zip is damaged", file=sys.stderr)
            return 1
        manifest = json.loads(archive.read("manifest.json"))
    wanted = {p.relative_to(SOURCE).as_posix() for p in expected}
    if names != wanted:
        print(f"The zip differs from the integration: {sorted(names ^ wanted)[:10]}", file=sys.stderr)
        return 1
    for required in ("manifest.json", "__init__.py", "frontend/kis-segito-panel.js"):
        if required not in names:
            print(f"{required} is missing from the zip", file=sys.stderr)
            return 1
    if tag and manifest.get("version") != tag.removeprefix("v"):
        print(f"manifest.json says {manifest.get('version')}, not {tag}", file=sys.stderr)
        return 1
    print(f"{out}: {len(names)} files, {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
