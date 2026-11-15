# SPDX-License-Identifier: AGPL-3.0-only
"""Which theme pictures a knob needs, and whether they fit its picture store.

A knob keeps the pictures it downloads in a 4 MB flash store, decoded (a
picture of N×N pixels takes about N×N×3 bytes there, in 4 KB blocks). For
each theme it shows (the common one and the children's own themes) it needs:

- the theme's interface pictures (menu, coins, piggy bank, marks …);
- the pictures of the tasks, routines, checkpoints and rewards in use, at the
  sizes the knob shows them.

Before restarting for a new theme, the knob downloads this list
(``/api/kis_segito/knob_theme_set/<theme>``) and stores every picture in it,
so nothing has to load after the restart.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .knob_images import _from_local_network
from .themes import theme_folder

SET_URL = "/api/kis_segito/knob_theme_set/{theme_id}"
TOKEN_HEADER = "X-Kis-Segito-Token"
# The knob's picture store, and what is kept free in it for the background,
# the avatars and uploaded pictures.
STORE_BYTES = 4 * 1024 * 1024
BLOCK = 4096
SCREEN_BYTES = 480 * 480 * 2
AVATAR_BYTES = 180 * 180 * 3
CONTENT = ("task_", "routine_", "reward_")
FILE = re.compile(r"^([a-z0-9_]+)_(\d+)\.png$")
THEME_ID = re.compile(r"^[a-z0-9_]+$")
# Sizes the knob shows content pictures at: tasks (big and small),
# checkpoints, rewards and the routines in the menu.
CONTENT_SIZES = {
    "task_": (150, 40),
    "routine_": (160, 32),
    "reward_": (160,),
}
CHECKPOINT_SIZES = (32, 28)


def _stored(size: int) -> int:
    """Bytes a size×size picture takes in the store (with its header)."""
    raw = size * size * 3 + 64
    return (raw + BLOCK - 1) // BLOCK * BLOCK


@lru_cache(maxsize=64)
def _files(folder: str) -> tuple[tuple[str, int], ...]:
    """(name, size) of the knob pictures of a theme folder."""
    path = Path(folder)
    if not path.is_dir():
        return ()
    out = []
    for item in path.iterdir():
        match = FILE.match(item.name)
        if match:
            out.append((match.group(1), int(match.group(2))))
    return tuple(sorted(out))


def used_icons(manager: Any) -> set[str]:
    """Every picture name the routines, checkpoints and rewards use."""
    names: set[str] = set()
    for routine in manager.data.get("routines", []):
        names.add(routine.get("icon") or "")
        for task in routine.get("tasks", []):
            names.add(task.get("icon") or "")
        for cp in routine.get("checkpoints", []):
            names.add(cp.get("icon") or "checkpoint_flag")
    for reward in manager.data.get("rewards", []):
        names.add(reward.get("icon") or "")
    names.add("fn_rewards")
    names.add("fn_piggy")
    names.add("checkpoint_flag")
    names.discard("")
    return names


def theme_keys(theme_id: str, used: set[str], language: str = "hu") -> list[tuple[str, int]]:
    """The pictures (``name_size`` keys) a knob needs from a theme, most
    important first, with the bytes each takes in the store. The brand mark
    only in the knob's language (Hungarian, or English for the others)."""
    english = not language.lower().startswith("hu")
    folder = theme_folder(theme_id)
    if folder is None:
        return []
    files = _files(str(folder / "knob"))
    available = set(files)
    keys: list[tuple[str, int]] = []
    content: list[tuple[str, int]] = []
    for name, size in files:
        if name.startswith("avatar_"):
            continue  # a child's avatar does not change with the theme
        if name.startswith(CONTENT):
            continue
        if name.startswith("brand_mark") and (name.startswith("brand_mark_en") != english):
            continue
        keys.append((f"{name}_{size}", _stored(size)))
    for name in sorted(used):
        prefix = next((p for p in CONTENT if name.startswith(p)), None)
        sizes = CONTENT_SIZES.get(prefix, CHECKPOINT_SIZES) if prefix else CHECKPOINT_SIZES
        for size in sizes:
            if (name, size) in available:
                content.append((f"{name}_{size}", _stored(size)))
    # The big task pictures first: they are the ones a child waits for.
    content.sort(key=lambda item: (not item[0].endswith("_150"), item[0]))
    return content + keys


def knob_themes(manager: Any, device_id: str) -> list[str]:
    """The themes a knob shows: the common one and its children's own."""
    themes = []
    on_knob = manager.device_children(device_id)
    common = manager.theme["id"]
    if common and common != "kis_segito":
        themes.append(common)
    for child in manager.children(active_only=True):
        if child["id"] not in on_knob:
            continue
        own = manager.child_theme_id(child)
        if own and own != "kis_segito" and own not in themes:
            themes.append(own)
    return themes


def knob_store(manager: Any, device_id: str, language: str = "hu") -> dict[str, Any]:
    """What a knob's picture store has to hold, and whether it fits."""
    used = used_icons(manager)
    themes = knob_themes(manager, device_id)
    per_theme = {t: sum(b for _k, b in theme_keys(t, used, language)) for t in themes}
    children = manager.device_children(device_id)
    fixed = (SCREEN_BYTES + 64 + BLOCK - 1) // BLOCK * BLOCK  # the background
    fixed += len(children) * ((AVATAR_BYTES + 64 + BLOCK - 1) // BLOCK * BLOCK)
    need = fixed + sum(per_theme.values())
    return {
        "themes": themes,
        "theme_kb": {t: b // 1024 for t, b in per_theme.items()},
        "need_kb": need // 1024,
        "size_kb": STORE_BYTES // 1024,
        "fits": need <= STORE_BYTES,
    }


async def async_prime(hass: HomeAssistant, manager: Any) -> None:
    """Read the theme folders once (in the executor), so the store can be
    worked out without file access later."""

    def prime() -> None:
        for theme in {manager.theme["id"], *(c.get("theme") or "" for c in manager.children())}:
            folder = theme_folder(theme) if theme else None
            if folder is not None:
                _files(str(folder / "knob"))

    await hass.async_add_executor_job(prime)


class KnobThemeSetView(HomeAssistantView):
    """GET the list of pictures a knob stores for a theme (knob token)."""

    url = SET_URL
    name = "api:kis_segito:knob_theme_set"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, theme_id: str) -> web.Response:
        if not _from_local_network(self.hass, request):
            return web.Response(status=403)
        manager = self.hass.data[DOMAIN].manager
        if not manager.valid_device_token(request.headers.get(TOKEN_HEADER, "")):
            return web.Response(status=403)
        if not THEME_ID.match(theme_id):
            return web.Response(status=404)
        used = used_icons(manager)
        language = request.query.get("lang", "hu")
        keys = await self.hass.async_add_executor_job(theme_keys, theme_id, used, language)
        return web.json_response({"keys": [k for k, _b in keys]})
