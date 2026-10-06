#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render the knob's icon images from the source artwork.

Reads assets/device_assets.json (icon id -> pixel sizes) and writes
assets/device/<id>_<size>.png from assets/icons/source/<id>.png. For sizes up
to SMALL_MAX px, assets/icons/source/<id>_small.png is used when it exists.
An id listed under "_fallbacks" (id -> other id) is rendered from the other
id's source while its own source file is missing.

Resizing is done in linear light with premultiplied alpha (no dark fringes),
using a Lanczos filter, with light sharpening on small sizes.

Usage: build_device_assets.py   (requires Pillow and numpy)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icons" / "source"
OUT = ROOT / "assets" / "device"
MANIFEST = ROOT / "assets" / "device_assets.json"
SMALL_MAX = 44


def _srgb_to_linear(v: np.ndarray) -> np.ndarray:
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def resize(img: Image.Image, size: int) -> Image.Image:
    """Gamma-correct, premultiplied-alpha Lanczos resize to size x size."""
    img = img.convert("RGBA")
    if img.width != img.height:
        side = max(img.size)
        canvas = Image.new("RGBA", (side, side))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        img = canvas
    px = np.asarray(img, dtype=np.float32) / 255.0
    alpha = px[..., 3:4]
    premul = _srgb_to_linear(px[..., :3]) * alpha
    planes = [
        np.asarray(Image.fromarray(premul[..., c]).resize((size, size), Image.LANCZOS))
        for c in range(3)
    ]
    a_small = np.clip(
        np.asarray(Image.fromarray(alpha[..., 0]).resize((size, size), Image.LANCZOS)), 0.0, 1.0
    )
    rgb_lin = np.stack(planes, axis=-1) / np.maximum(a_small[..., None], 1e-6)
    rgb = _linear_to_srgb(rgb_lin)
    rgb[a_small < 1 / 255] = 0.0
    out = np.concatenate([rgb, a_small[..., None]], axis=-1)
    result = Image.fromarray(np.round(out * 255).astype(np.uint8), "RGBA")
    if size <= 64:
        sharp = result.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
        result = Image.merge("RGBA", (*sharp.split(), result.split()[3]))
    return result


def main() -> int:
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    fallbacks = manifest.get("_fallbacks", {})
    count = 0
    for icon, sizes in manifest.items():
        if icon.startswith("_"):
            continue
        name = icon
        if not (SOURCE / f"{icon}.png").exists() and icon in fallbacks:
            name = fallbacks[icon]
            print(f"{icon}: no own artwork yet, using {name}")
        source = SOURCE / f"{name}.png"
        small_source = SOURCE / f"{name}_small.png"
        if not source.exists():
            print(f"missing source: {source.relative_to(ROOT)}")
            return 1
        big = Image.open(source)
        small = Image.open(small_source) if small_source.exists() else big
        for size in sizes:
            img = resize(small if size <= SMALL_MAX else big, size)
            img.save(OUT / f"{icon}_{size}.png", optimize=True)
            count += 1
    print(f"wrote {count} images to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
