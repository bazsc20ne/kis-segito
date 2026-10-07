# SPDX-License-Identifier: AGPL-3.0-only
"""Uploaded pictures (avatars, rewards) for the knob.

Pictures are uploaded through Home Assistant's own image_upload integration.
The knob cannot decode PNG/JPEG cheaply, so this view serves a square,
resized copy in LVGL's RGB565A8 layout:

    b"KSI1" + width (uint16 LE) + height (uint16 LE)
    + width*height RGB565 pixels (LE) + width*height alpha bytes

The knob authenticates with its own random token (sent in the state
snapshot over the encrypted ESPHome API), not with a Home Assistant token.
"""

from __future__ import annotations

import re
import struct
from functools import lru_cache
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

URL = "/api/kis_segito/knob_image/{image_id}/{size}"
SIZES = (64, 160, 180)
IMAGE_ID = re.compile(r"^[a-z0-9_]{1,64}$")


def convert(path: Path, size: int) -> bytes:
    """Read an uploaded picture and return it in the knob's raw format."""
    from PIL import Image, ImageOps

    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    image = ImageOps.fit(image, (size, size), Image.LANCZOS)
    pixels = bytearray()
    alpha = bytearray()
    for r, g, b, a in image.getdata():
        value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        pixels += struct.pack("<H", value)
        alpha.append(a)
    return b"KSI1" + struct.pack("<HH", size, size) + bytes(pixels) + bytes(alpha)


@lru_cache(maxsize=64)
def _cached(path: str, mtime: float, size: int) -> bytes:
    return convert(Path(path), size)


class KnobImageView(HomeAssistantView):
    """GET a picture for the knob, authenticated by the knob's token."""

    url = URL
    name = "api:kis_segito:knob_image"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, image_id: str, size: str) -> web.Response:
        manager = self.hass.data[DOMAIN].manager
        token = request.query.get("t", "")
        if not token or token not in manager.device_tokens():
            return web.Response(status=403)
        if not IMAGE_ID.match(image_id) or not size.isdigit() or int(size) not in SIZES:
            return web.Response(status=404)
        path = Path(self.hass.config.path("image", image_id, "original"))
        if not path.is_file():
            return web.Response(status=404)
        data = await self.hass.async_add_executor_job(
            _cached, str(path), path.stat().st_mtime, int(size)
        )
        return web.Response(body=data, content_type="application/octet-stream")
