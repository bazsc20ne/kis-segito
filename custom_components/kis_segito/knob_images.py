# SPDX-License-Identifier: AGPL-3.0-only
"""Uploaded pictures (avatars, rewards) for the knob.

Pictures are uploaded through Home Assistant's own image_upload integration.
The knob cannot decode PNG/JPEG cheaply, so this view serves a square,
resized copy in LVGL's RGB565A8 layout:

    b"KSI1" + width (uint16 LE) + height (uint16 LE)
    + width*height RGB565 pixels (LE) + width*height alpha bytes

Backgrounds (size 480, the whole round screen) are opaque, without alpha:

    b"KSI2" + width (uint16 LE) + height (uint16 LE)
    + width*height RGB565 pixels (LE)

A background is a built-in preset (frontend/backgrounds/bg_<n>.jpg) or an
uploaded picture. The icons that are not compiled into the firmware
(knob_icons/) and the built-in avatars (knob_avatars/avatar_<nn>.png) are served
the same way, so they are not part of the firmware.

The rendition holds pixels only, no metadata (EXIF, GPS) of the original.

The knob authenticates with its own random token, sent in the state snapshot
only over an encrypted ESPHome API connection. The knob sends it back in the
``X-Kis-Segito-Token`` header (never in the URL), and the view answers only
requests from the local network, never through Home Assistant Cloud.
"""

from __future__ import annotations

import re
import struct
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import is_cloud_connection
from homeassistant.util.network import is_local

from .const import DOMAIN

URL = "/api/kis_segito/knob_image/{image_id}/{size}"
TOKEN_HEADER = "X-Kis-Segito-Token"
SIZES = (64, 160, 180)
BACKGROUND_SIZE = 480
PRESETS_DIR = Path(__file__).parent / "frontend" / "backgrounds"
PRESET_ID = re.compile(r"^bg_[1-6]$")
AVATARS_DIR = Path(__file__).parent / "knob_avatars"
# Icons not compiled into the firmware, rendered at the sizes the knob uses
# (knob_icons/<id>_<size>.png); other sizes are made from the nearest one.
ICONS_DIR = Path(__file__).parent / "knob_icons"
ICON_SIZES = range(16, 241)
AVATAR_ID = re.compile(r"^avatar_[0-9]{2}$")
IMAGE_ID = re.compile(r"^[a-z0-9_]{1,64}$")
# Limits checked before a picture is decoded (decompression bombs).
MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_PIXELS = 100_000_000
FORMATS = {"JPEG", "PNG", "GIF", "WEBP", "BMP"}


class ImageRejected(Exception):
    """The original picture is too big or not an image."""


def convert(path: Path, size: int) -> bytes:
    """Read an uploaded picture and return it in the knob's raw format."""
    from PIL import Image, ImageOps

    if path.stat().st_size > MAX_FILE_BYTES:
        raise ImageRejected("file too large")
    # Pillow's own MAX_IMAGE_PIXELS guard stays on (a process-wide setting, not
    # changed here); the explicit check below is stricter and runs before decoding.
    try:
        with Image.open(path, formats=sorted(FORMATS)) as source:
            # The real type from the file content, not its name.
            if source.format not in FORMATS:
                raise ImageRejected("not an image")
            width, height = source.size
            if width * height > MAX_PIXELS:
                raise ImageRejected("too many pixels")
            if source.format == "JPEG":
                # Decode big photos at a reduced scale; much faster, less memory.
                source.draft("RGB", (size * 2, size * 2))
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except (Image.DecompressionBombError, Image.UnidentifiedImageError) as err:
        raise ImageRejected(str(err)) from err
    image = ImageOps.fit(image, (size, size), Image.LANCZOS)
    pixels, alpha = _rgb565(image)
    header = struct.pack("<HH", size, size)
    if size == BACKGROUND_SIZE:
        return b"KSI2" + header + pixels
    return b"KSI1" + header + pixels + alpha


def _rgb565(image) -> tuple[bytes, bytes]:
    """RGB565 (little endian) and alpha bytes of an RGBA image."""
    try:
        import numpy as np
    except ImportError:
        pixels = bytearray()
        alpha = bytearray()
        for r, g, b, a in image.getdata():
            value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pixels += struct.pack("<H", value)
            alpha.append(a)
        return bytes(pixels), bytes(alpha)
    rgba = np.asarray(image, dtype=np.uint16)
    r, g, b = rgba[..., 0], rgba[..., 1], rgba[..., 2]
    value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return value.astype("<u2").tobytes(), rgba[..., 3].astype(np.uint8).tobytes()


@lru_cache(maxsize=64)
def _cached(path: str, mtime: float, size: int) -> bytes | None:
    try:
        return convert(Path(path), size)
    except ImageRejected:
        return None


def _icon_path(icon: str, size: int) -> Path | None:
    """The rendered icon for ``icon`` at ``size``, else its nearest larger size."""
    if size not in ICON_SIZES:
        return None
    exact = ICONS_DIR / f"{icon}_{size}.png"
    if exact.is_file():
        return exact
    sizes = sorted(
        int(p.stem.rsplit("_", 1)[1])
        for p in ICONS_DIR.glob(f"{icon}_*.png")
        if p.stem.rsplit("_", 1)[1].isdigit() and p.stem.rsplit("_", 1)[0] == icon
    )
    if not sizes:
        return None
    best = next((s for s in sizes if s >= size), sizes[-1])
    return ICONS_DIR / f"{icon}_{best}.png"


def _from_local_network(hass: HomeAssistant, request: web.Request) -> bool:
    if is_cloud_connection(hass) or not request.remote:
        return False
    try:
        return is_local(ip_address(request.remote))
    except ValueError:
        return False


class KnobImageView(HomeAssistantView):
    """GET a picture for the knob, authenticated by the knob's token."""

    url = URL
    name = "api:kis_segito:knob_image"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, image_id: str, size: str) -> web.Response:
        if not _from_local_network(self.hass, request):
            return web.Response(status=403)
        manager = self.hass.data[DOMAIN].manager
        if not manager.valid_device_token(request.headers.get(TOKEN_HEADER, "")):
            return web.Response(status=403)
        if not IMAGE_ID.match(image_id) or not size.isdigit():
            return web.Response(status=404)
        if int(size) == BACKGROUND_SIZE:
            path = (
                PRESETS_DIR / f"{image_id}.jpg"
                if PRESET_ID.match(image_id)
                else Path(self.hass.config.path("image", image_id, "original"))
            )
        elif AVATAR_ID.match(image_id) and int(size) in SIZES:
            path = AVATARS_DIR / f"{image_id}.png"
        elif (
            icon := await self.hass.async_add_executor_job(
                _icon_path, image_id, int(size)
            )
        ) is not None:
            path = icon
        elif int(size) in SIZES:
            path = Path(self.hass.config.path("image", image_id, "original"))
        else:
            return web.Response(status=404)
        if not path.is_file():
            return web.Response(status=404)
        data = await self.hass.async_add_executor_job(
            _cached, str(path), path.stat().st_mtime, int(size)
        )
        if data is None:
            return web.Response(status=415)
        return web.Response(body=data, content_type="application/octet-stream")
