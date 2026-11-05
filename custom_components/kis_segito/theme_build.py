# SPDX-License-Identifier: AGPL-3.0-only
"""Make a theme's pictures from its source pictures.

Used for the bundled themes (tools/build_theme_assets.py) and for themes
uploaded in the panel. The source pictures are named like the built-in ones
(e.g. task_shoes.png, avatar_01.png, brand_logo.png, bg_1.jpg); each one is
rendered at every size the panel, the cards and the knob show it:

- icons/<name>.png (96 px) and icons/small/<name>.png (88 px, from
  <name>_small when there is one), icons/brand_logo*.webp (160 px high);
- knob/<icon>_<size>.png (themes/knob_pictures.json);
- backgrounds/bg_<n>.jpg (1024 px).

Resizing is done in linear light with premultiplied alpha (no dark fringes)
and a Lanczos filter, with light sharpening on small sizes.
"""

from __future__ import annotations

import json
from functools import cache
from collections.abc import Mapping
from pathlib import Path

FRONTEND = Path(__file__).parent / "frontend"
ICONS_DIR = FRONTEND / "icons"
KNOB_LIST = FRONTEND / "themes" / "knob_pictures.json"
WEB_SIZE = 96
WEB_SMALL_SIZE = 88
SMALL_MAX = 44
LOGOS = ("brand_logo", "brand_logo_en")
LOGO_HEIGHT = 160
BACKGROUND_SIZE = 1024
BACKGROUNDS = tuple(f"bg_{n}" for n in range(1, 7))
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


@cache
def knob_list() -> tuple[str, ...]:
    """The knob picture files of a theme (read once; files do not change
    while Home Assistant runs)."""
    return tuple(json.loads(KNOB_LIST.read_text("utf-8")))


@cache
def source_names() -> list[str]:
    """Every source picture a theme can have (without the _small variants)."""
    names = {path.stem for path in ICONS_DIR.glob("*.png")}
    for item in knob_list():
        names.add(item.rsplit("_", 1)[0])
    names.update(LOGOS)
    names.update(BACKGROUNDS)
    return sorted(names)


@cache
def small_names() -> list[str]:
    """Pictures with a simplified variant for small places (<name>_small)."""
    small = {path.stem for path in (ICONS_DIR / "small").glob("*.png")}
    small.update(
        item.rsplit("_", 1)[0]
        for item in knob_list()
        if int(item.rsplit("_", 1)[1][:-4]) <= SMALL_MAX
    )
    return sorted(small)


def resize(img, size: int):
    """Gamma-correct, premultiplied-alpha Lanczos resize to size x size
    (a picture that is not square is centred on a transparent square)."""
    import numpy as np
    from PIL import Image, ImageFilter

    def to_linear(v):
        return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)

    def to_srgb(v):
        v = np.clip(v, 0.0, 1.0)
        return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)

    img = img.convert("RGBA")
    if img.width != img.height:
        side = max(img.size)
        canvas = Image.new("RGBA", (side, side))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        img = canvas
    px = np.asarray(img, dtype=np.float32) / 255.0
    alpha = px[..., 3:4]
    premul = to_linear(px[..., :3]) * alpha
    planes = [
        np.asarray(Image.fromarray(premul[..., c]).resize((size, size), Image.LANCZOS))
        for c in range(3)
    ]
    a_small = np.clip(
        np.asarray(Image.fromarray(alpha[..., 0]).resize((size, size), Image.LANCZOS)),
        0.0,
        1.0,
    )
    rgb = to_srgb(np.stack(planes, axis=-1) / np.maximum(a_small[..., None], 1e-6))
    rgb[a_small < 1 / 255] = 0.0
    out = np.concatenate([rgb, a_small[..., None]], axis=-1)
    result = Image.fromarray(np.round(out * 255).astype(np.uint8), "RGBA")
    if size <= 64:
        sharp = result.convert("RGB").filter(
            ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1)
        )
        result = Image.merge("RGBA", (*sharp.split(), result.split()[3]))
    return result


def find_sources(folder: Path) -> dict[str, Path]:
    """The source pictures in a folder (any of EXTENSIONS, also in a
    backgrounds/ subfolder), by name."""
    found: dict[str, Path] = {}
    for path in [*folder.glob("*"), *(folder / "backgrounds").glob("*")]:
        if path.is_file() and path.suffix.lower() in EXTENSIONS:
            found.setdefault(path.stem.lower(), path)
    return found


def build(sources: Mapping[str, Path], out: Path) -> list[str]:
    """Write every picture that has a source; returns the source names that
    are missing."""
    from PIL import Image

    cache: dict[str, Image.Image] = {}

    def open_(name: str):
        if name not in sources:
            return None
        if name not in cache:
            cache[name] = Image.open(sources[name])
            cache[name].load()
        return cache[name]

    (out / "icons" / "small").mkdir(parents=True, exist_ok=True)
    (out / "knob").mkdir(parents=True, exist_ok=True)
    (out / "backgrounds").mkdir(parents=True, exist_ok=True)

    for path in ICONS_DIR.glob("*.png"):
        img = open_(path.stem)
        if img is not None:
            resize(img, WEB_SIZE).save(out / "icons" / path.name, optimize=True)
    for path in (ICONS_DIR / "small").glob("*.png"):
        img = open_(f"{path.stem}_small") or open_(path.stem)
        if img is not None:
            resize(img, WEB_SMALL_SIZE).save(
                out / "icons" / "small" / path.name, optimize=True
            )
    for item in knob_list():
        name, size = item.rsplit("_", 1)
        size_px = int(size[:-4])
        img = (open_(f"{name}_small") if size_px <= SMALL_MAX else None) or open_(name)
        if img is not None:
            resize(img, size_px).save(out / "knob" / item, optimize=True)
    for name in LOGOS:
        img = open_(name)
        if img is None:
            continue
        img = img.convert("RGBA")
        box = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if box:
            img = img.crop(box)
        width = max(1, round(img.width * LOGO_HEIGHT / img.height))
        img.resize((width, LOGO_HEIGHT), Image.LANCZOS).save(
            out / "icons" / f"{name}.webp", "WEBP", quality=90, method=6
        )
    for name in BACKGROUNDS:
        img = open_(name)
        if img is None:
            continue
        img = img.convert("RGB")
        side = min(img.size)
        left, top = (img.width - side) // 2, (img.height - side) // 2
        img.crop((left, top, left + side, top + side)).resize(
            (BACKGROUND_SIZE, BACKGROUND_SIZE), Image.LANCZOS
        ).save(out / "backgrounds" / f"{name}.jpg", quality=90, optimize=True)
    return [name for name in source_names() if name not in sources]
