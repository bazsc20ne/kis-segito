#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render a theme's pictures from its source artwork.

Usage: build_theme_assets.py <theme id> <source folder>

The source folder holds the theme's master pictures under the same names as
assets/icons/source/ (see THEME_SOURCES) and backgrounds/bg_1 … bg_6 (PNG or
JPEG). Everything is written to
custom_components/kis_segito/frontend/themes/<theme id>/:

- icons/<name>.png (panel, 96 px), icons/small/<name>.png (88 px),
  icons/brand_logo.webp and brand_logo_en.webp (header wordmarks);
- knob/<icon>_<size>.png: every picture at every size the knob shows it
  (assets/device_assets.json), and knob/avatar_<nn>_180.png;
- backgrounds/bg_<n>.jpg (1024 px, for the panel and the knob).

A theme is offered only when all of these exist (see themes.py).

Requires Pillow and numpy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_device_assets import (
    AVATAR_SIZE,
    MANIFEST,
    ROOT,
)

THEMES = ROOT / "custom_components" / "kis_segito" / "frontend" / "themes"
sys.path.insert(0, str(ROOT / "custom_components" / "kis_segito"))
import theme_build


def build(theme: str, source: Path) -> list[str]:
    """Write the theme's pictures; returns the source names that are missing."""
    return theme_build.build(theme_build.find_sources(source), THEMES / theme)


def knob_pictures() -> list[str]:
    """The knob picture files every theme has (knob/<name>)."""
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    names = [
        f"{icon}_{size}.png"
        for icon, sizes in manifest.items()
        if not icon.startswith("_")
        for size in sizes
    ]
    names += [
        f"{path.stem}_{AVATAR_SIZE}.png"
        for path in (ROOT / "assets" / "icons" / "source").glob("avatar_[0-9][0-9].png")
    ]
    return sorted(names)


def write_knob_list() -> None:
    """themes/knob_pictures.json: what themes.py checks a theme for."""
    THEMES.mkdir(parents=True, exist_ok=True)
    (THEMES / "knob_pictures.json").write_text(
        json.dumps(knob_pictures(), indent=1) + "\n", "utf-8"
    )


def theme_sources() -> list[str]:
    """The source pictures a theme redraws: the built-in set without the
    pictures nothing shows."""
    unused = {
        "arrow_flow",
        "brand_app_icon",
        "placeholder_image",
        "token_coin_edge",
        "token_coin_top",
        "token_pile_shadow",
    }
    return sorted(
        path.stem
        for path in (ROOT / "assets" / "icons" / "source").glob("*.png")
        if path.stem not in unused
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    theme, source = sys.argv[1], Path(sys.argv[2])
    write_knob_list()
    missing = build(theme, source)
    if missing:
        print(f"{theme}: {len(missing)} source pictures missing:")
        for name in missing:
            print(f"  {name}")
        return 1
    print(f"{theme}: all pictures written to {(THEMES / theme).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
