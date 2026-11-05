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

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_device_assets import (
    AVATAR_SIZE,
    LOGO_HEIGHT,
    LOGOS,
    MANIFEST,
    ROOT,
    SMALL_MAX,
    WEB_SIZE,
    WEB_SKIP,
    WEB_SMALL_SIZE,
    resize,
)

THEMES = ROOT / "custom_components" / "kis_segito" / "frontend" / "themes"
BACKGROUND_SIZE = 1024
BACKGROUNDS = 6


def _open(folder: Path, stem: str) -> Image.Image | None:
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = folder / f"{stem}{ext}"
        if path.exists():
            return Image.open(path)
    return None


def build(theme: str, source: Path) -> list[str]:
    """Write the theme's pictures; returns the source names that are missing."""
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    out = THEMES / theme
    missing: list[str] = []
    masters: dict[str, Image.Image] = {}

    def master(name: str) -> Image.Image | None:
        if name not in masters:
            img = _open(source, name)
            if img is None:
                missing.append(name)
                return None
            masters[name] = img
        return masters[name]

    # Knob sizes of every picture the knob shows.
    knob = out / "knob"
    knob.mkdir(parents=True, exist_ok=True)
    for icon, sizes in manifest.items():
        if icon.startswith("_"):
            continue
        big = master(icon)
        if big is None:
            continue
        small = _open(source, f"{icon}_small") or big
        for size in sizes:
            resize(small if size <= SMALL_MAX else big, size).save(
                knob / f"{icon}_{size}.png", optimize=True
            )
    for path in sorted(
        Path(ROOT / "assets" / "icons" / "source").glob("avatar_[0-9][0-9].png")
    ):
        img = master(path.stem)
        if img is not None:
            resize(img, AVATAR_SIZE).save(
                knob / f"{path.stem}_{AVATAR_SIZE}.png", optimize=True
            )

    # Panel and card icons, from the same list as the built-in set.
    icons = out / "icons"
    (icons / "small").mkdir(parents=True, exist_ok=True)
    for name in theme_sources():
        if name.endswith("_small"):
            img = master(name)
            if img is not None:
                resize(img, WEB_SMALL_SIZE).save(
                    icons / "small" / f"{name.removesuffix('_small')}.png",
                    optimize=True,
                )
        elif not name.startswith(WEB_SKIP):
            img = master(name)
            if img is not None:
                resize(img, WEB_SIZE).save(icons / f"{name}.png", optimize=True)
    for name in LOGOS:
        img = master(name)
        if img is None:
            continue
        img = img.convert("RGBA")
        img = img.crop(
            img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        )
        width = round(img.width * LOGO_HEIGHT / img.height)
        img.resize((width, LOGO_HEIGHT), Image.LANCZOS).save(
            icons / f"{name}.webp", "WEBP", quality=90, method=6
        )

    backgrounds = out / "backgrounds"
    backgrounds.mkdir(parents=True, exist_ok=True)
    for n in range(1, BACKGROUNDS + 1):
        img = _open(source / "backgrounds", f"bg_{n}")
        if img is None:
            missing.append(f"backgrounds/bg_{n}")
            continue
        img = img.convert("RGB")
        side = min(img.size)
        left, top = (img.width - side) // 2, (img.height - side) // 2
        img.crop((left, top, left + side, top + side)).resize(
            (BACKGROUND_SIZE, BACKGROUND_SIZE), Image.LANCZOS
        ).save(backgrounds / f"bg_{n}.jpg", quality=90, optimize=True, progressive=True)
    return sorted(set(missing))


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
