# SPDX-License-Identifier: AGPL-3.0-only
"""Uploaded pictures (avatars, rewards) for the knob.

Pictures are uploaded through Home Assistant's own image_upload integration.
The knob cannot decode PNG/JPEG cheaply, so this view serves a square,
resized copy in LVGL's RGB565A8 layout:

    b"KSI1" + width (uint16 LE) + height (uint16 LE)
    + width*height RGB565 pixels (LE) + width*height alpha bytes

Backgrounds (the size of the whole round screen: 240, 360, 466 or 480) are
opaque, without alpha:

    b"KSI2" + width (uint16 LE) + height (uint16 LE)
    + width*height RGB565 pixels (LE)

A background is a built-in preset (frontend/backgrounds/bg_<n>.jpg) or an
uploaded picture. Own icons (``own_…``) are uploaded pictures too. The icons
that are not compiled into the firmware
(knob_icons/) and the built-in avatars (knob_avatars/avatar_<nn>.png) are served
the same way, so they are not part of the firmware.

The rendition holds pixels only, no metadata (EXIF, GPS) of the original.

Each answer carries an ETag. The knob keeps the pictures in its flash and asks
again with ``If-None-Match``; an unchanged picture is answered with 304 (Not
Modified) without converting it again.

The knob authenticates with its own random token, sent in the state snapshot
only over an encrypted ESPHome API connection. The knob sends it back in the
``X-Kis-Segito-Token`` header (never in the URL), and the view answers only
requests from the local network, never through Home Assistant Cloud.
"""

from __future__ import annotations

import hashlib
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
from .themes import theme_folder

URL = "/api/kis_segito/knob_image/{image_id}/{size}"
TOKEN_HEADER = "X-Kis-Segito-Token"
# The display sizes of the knobs: a background is the whole screen.
BACKGROUND_SIZES = (240, 360, 466, 480)
PRESETS_DIR = Path(__file__).parent / "frontend" / "backgrounds"
PRESET_ID = re.compile(r"^bg_[1-6]$")
# A theme's own picture: "t_<theme>__<picture>".
THEMED_ID = re.compile(r"^t_([a-z0-9_]+?)__([a-z0-9_]+)$")
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
# Part of every ETag: changes when the knob format or the conversion changes.
RENDER_VERSION = "1"


class ImageRejected(Exception):
    """The original picture is too big or not an image."""


def convert(path: Path, size: int, opaque: bool | None = None) -> bytes:
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
    if size in BACKGROUND_SIZES if opaque is None else opaque:
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
def _cached(
    path: str, mtime: float, size: int, opaque: bool | None = None
) -> bytes | None:
    try:
        return convert(Path(path), size, opaque)
    except ImageRejected:
        return None


def _icon_path(icon: str, size: int, folder: Path = ICONS_DIR) -> Path | None:
    """The rendered icon for ``icon`` at ``size``, else its nearest larger size."""
    if size not in ICON_SIZES:
        return None
    exact = folder / f"{icon}_{size}.png"
    if exact.is_file():
        return exact
    sizes = sorted(
        int(p.stem.rsplit("_", 1)[1])
        for p in folder.glob(f"{icon}_*.png")
        if p.stem.rsplit("_", 1)[1].isdigit() and p.stem.rsplit("_", 1)[0] == icon
    )
    if not sizes:
        return None
    best = next((s for s in sizes if s >= size), sizes[-1])
    return folder / f"{icon}_{best}.png"


def _theme_path(image_id: str, size: int) -> Path | None:
    """A picture of a theme: "t_<theme>__<picture>" (a built-in icon, avatar or
    background preset in that theme's style)."""
    match = THEMED_ID.match(image_id)
    if match is None:
        return None
    theme_id, name = match.groups()
    folder = theme_folder(theme_id)
    if folder is None:
        return None  # the default theme, or one that cannot be chosen
    if PRESET_ID.match(name):
        path = folder / "backgrounds" / f"{name}.jpg"
        return path if size in BACKGROUND_SIZES and path.is_file() else None
    return _icon_path(name, size, folder / "knob")


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
        opaque: bool | None = None
        if THEMED_ID.match(image_id):
            path = await self.hass.async_add_executor_job(
                _theme_path, image_id, int(size)
            )
            if path is None:
                return web.Response(status=404)
            # Only a background is the whole screen (stored without alpha).
            opaque = bool(PRESET_ID.match(THEMED_ID.match(image_id).group(2)))
        elif int(size) in BACKGROUND_SIZES:
            path = (
                PRESETS_DIR / f"{image_id}.jpg"
                if PRESET_ID.match(image_id)
                else Path(self.hass.config.path("image", image_id, "original"))
            )
        elif AVATAR_ID.match(image_id) and int(size) in ICON_SIZES:
            path = AVATARS_DIR / f"{image_id}.png"
        elif image_id.startswith("own_") and int(size) in ICON_SIZES:
            # An own (uploaded) icon, at any size the knob shows icons.
            own = manager.own_icon(image_id)
            if own is None:
                return web.Response(status=404)
            path = Path(self.hass.config.path("image", own["image"], "original"))
        elif (
            icon := await self.hass.async_add_executor_job(
                _icon_path, image_id, int(size)
            )
        ) is not None:
            path = icon
        elif int(size) in ICON_SIZES:
            path = Path(self.hass.config.path("image", image_id, "original"))
        else:
            return web.Response(status=404)
        if not path.is_file():
            return web.Response(status=404)
        mtime = path.stat().st_mtime
        etag = await self.hass.async_add_executor_job(
            _etag, str(path), mtime, int(size)
        )
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers=headers)
        data = await self.hass.async_add_executor_job(
            _cached, str(path), mtime, int(size), opaque
        )
        if data is None:
            return web.Response(status=415)
        return web.Response(
            body=data, content_type="application/octet-stream", headers=headers
        )


@lru_cache(maxsize=256)
def _etag(path: str, mtime: float, size: int) -> str:
    """Identifies one rendition: the source file's content and the size.

    Taken from the content, not the file's time, so reinstalling or restoring
    the same files does not make the knob load every picture again. ``mtime``
    only keys the memo, so a changed file is read again.
    """
    digest = hashlib.sha256(f"{RENDER_VERSION}|{size}|".encode())
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return f'"{digest.hexdigest()[:24]}"'
