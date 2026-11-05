# SPDX-License-Identifier: AGPL-3.0-only
"""Own themes: the template download, the upload, and the theme manager.

A theme package is a ZIP with a theme.json (name, colours) and pictures named
like the built-in ones (see the template and docs/themes.md). Any picture may
be left out: the built-in one is shown instead. Uploaded themes are stored in
Home Assistant's configuration folder (themes.own_dir()).
"""

from __future__ import annotations

import io
import json
import re
import secrets
import shutil
import unicodedata
import zipfile
from functools import cache
from pathlib import Path
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from . import theme_build
from .const import DOMAIN
from .themes import (
    DEFAULT_THEME,
    OWN_PREFIX,
    load_themes,
    own_dir,
    reload,
    theme_folder,
)

MAX_UPLOAD = 150 * 1024 * 1024  # the ZIP
MAX_ENTRY = 40 * 1024 * 1024  # one unpacked file
MAX_TOTAL = 600 * 1024 * 1024  # everything unpacked
MAX_SIDE = 4096  # pixels per side of a picture
FRONTEND = Path(__file__).parent / "frontend"

TEMPLATE_README = """Kis Segito / Little Helper - own theme
======================================

English
-------
1. Edit theme.json: the theme's name (English and Hungarian) and, if you
   like, its colours ("#RRGGBB"). "panel" is the admin panel (light and dark
   mode), "knob" the knob screen.
2. Replace any of the pictures in the "pictures" folder with your own, under
   the same file name. Pictures you do not replace (or delete) stay the
   built-in ones, so a theme can be just a few pictures.
   - Icons and avatars: square PNG with a transparent background, 512 x 512
     or larger, the subject filling most of the square.
   - <name>_small.png (optional): a simpler version for small places.
   - Backgrounds bg_1 ... bg_6: square, no transparency, 1024 x 1024 or
     larger; keep the middle calm (the knob draws on it).
   - brand_logo / brand_logo_en: the header logo, transparent, any width.
   Use only pictures you made or may use, without other brands' logos or
   characters.
3. Zip theme.json and the pictures and upload the ZIP in the panel:
   Settings -> Theme -> Upload a theme. Everything is resized there.
Details: docs/themes.md in the project's repository.

Magyar
------
1. Szerkeszd a theme.json-t: a téma neve (angolul és magyarul), és ha
   szeretnéd, a színei ("#RRGGBB"). A "panel" a kezelőpanel (világos és sötét
   mód), a "knob" a gomb képernyője.
2. Cseréld le a "pictures" mappa bármelyik képét a sajátodra, ugyanazzal a
   fájlnévvel. Amit nem cserélsz le (vagy törölsz), az a beépített kép marad,
   így egy téma akár csak néhány kép is lehet.
   - Ikonok és avatarok: négyzetes PNG átlátszó háttérrel, legalább 512 x 512,
     a téma töltse ki a négyzet nagy részét.
   - <név>_small.png (nem kötelező): egyszerűbb változat kis helyekre.
   - Hátterek bg_1 ... bg_6: négyzetes, átlátszóság nélkül, legalább
     1024 x 1024; a közepe legyen nyugodt (arra rajzol a gomb).
   - brand_logo / brand_logo_en: a fejléc logója, átlátszó, bármilyen széles.
   Csak saját vagy felhasználható képet használj, más márkák logója és
   szereplői nélkül.
3. Tömörítsd ZIP-be a theme.json-t és a képeket, és töltsd fel a panelen:
   Beállítások -> Téma -> Téma feltöltése. Az átméretezés ott történik.
Részletek: docs/themes.md a projekt repójában.
"""

THEME_JSON_TEMPLATE = {
    "name": {"en": "My theme", "hu": "Saját téma"},
    "panel": {
        "light": {
            "--bg": "#F2F6FC",
            "--surface": "#FFFFFF",
            "--surface-2": "#EAF1FA",
            "--ink": "#18213D",
            "--muted": "#5A6684",
            "--line": "#D9E2EF",
            "--accent": "#2C78F0",
            "--accent-ink": "#FFFFFF",
            "--accent-soft": "#DCE9FF",
        },
        "dark": {
            "--bg": "#0A0F24",
            "--surface": "#131A35",
            "--surface-2": "#1A2244",
            "--ink": "#EDF0FF",
            "--muted": "#A2ABCF",
            "--line": "#29335F",
            "--accent": "#7DB2FF",
            "--accent-ink": "#0A1230",
            "--accent-soft": "#1F3466",
        },
    },
    "knob": {
        "bg": "#1B2140",
        "track": "#3A4066",
        "pill": "#0F1330",
        "number": "#FFE08A",
        "deposit": "#6BCB77",
        "withdraw": "#FF9F43",
    },
}


class ThemeError(Exception):
    """An uploaded theme that cannot be installed (code for the panel)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "_".join(re.findall(r"[a-z0-9]+", text.lower()))[:24]


def _reference(name: str) -> Path | None:
    """The largest built-in rendition of a picture, as a sample."""
    if name.startswith("bg_"):
        return FRONTEND / "backgrounds" / f"{name}.jpg"
    if name in theme_build.LOGOS:
        path = FRONTEND / "icons" / f"{name}.webp"
        return path if path.is_file() else None
    base = Path(__file__).parent
    # theme_samples: pictures that are otherwise only in the knob firmware.
    candidates = [
        base / "theme_samples" / f"{name}.png",
        base / "knob_avatars" / f"{name}.png",
    ]
    candidates += sorted(
        (base / "knob_icons").glob(f"{name}_[0-9]*.png"),
        key=lambda p: -int(p.stem.rsplit("_", 1)[1]),
    )
    candidates.append(FRONTEND / "icons" / f"{name}.png")
    return next((p for p in candidates if p.is_file()), None)


@cache
def template_zip() -> bytes:
    """The theme template: theme.json, a short guide and every picture."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "theme.json", json.dumps(THEME_JSON_TEMPLATE, indent=2, ensure_ascii=False)
        )
        zf.writestr("README.txt", TEMPLATE_README)
        for name in theme_build.source_names():
            path = _reference(name)
            if path is not None:
                zf.write(path, f"pictures/{name}{path.suffix}")
    return buf.getvalue()


def install(data: bytes) -> dict[str, Any]:
    """Unpack, check and install a theme package; returns the theme."""
    from PIL import Image, UnidentifiedImageError

    folder = own_dir()
    if folder is None:
        raise ThemeError("no_storage")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as err:
        raise ThemeError("not_a_zip") from err
    allowed = set(theme_build.source_names())
    allowed |= {f"{name}_small" for name in theme_build.small_names()}
    meta: dict[str, Any] | None = None
    pictures: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in archive.infolist():
        name = Path(info.filename).name
        if info.is_dir() or name.startswith(".") or "__MACOSX" in info.filename:
            continue
        if info.file_size > MAX_ENTRY:
            raise ThemeError("file_too_large")
        total += info.file_size
        if total > MAX_TOTAL:
            raise ThemeError("too_large")
        stem, suffix = Path(name.lower()).stem, Path(name.lower()).suffix
        if name.lower() == "theme.json":
            try:
                meta = json.loads(archive.read(info).decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as err:
                raise ThemeError("bad_theme_json") from err
        elif suffix in theme_build.EXTENSIONS and stem in allowed:
            pictures[stem] = info
    if not isinstance(meta, dict):
        raise ThemeError("no_theme_json")
    names = meta.get("name") if isinstance(meta.get("name"), dict) else {}
    title = next((str(names[k]).strip() for k in ("en", "hu") if names.get(k)), "")
    slug = _slug(str(meta.get("id") or title))
    if not slug:
        raise ThemeError("no_name")
    theme_id = OWN_PREFIX + slug
    work = folder / f".upload_{secrets.token_hex(4)}"
    try:
        source = work / "source"
        source.mkdir(parents=True)
        sources: dict[str, Path] = {}
        for stem, info in pictures.items():
            path = source / f"{stem}{Path(info.filename.lower()).suffix}"
            path.write_bytes(archive.read(info))
            try:
                with Image.open(path) as img:
                    if max(img.size) > MAX_SIDE:
                        raise ThemeError("picture_too_large")
                    img.verify()
            except (UnidentifiedImageError, OSError) as err:
                raise ThemeError("bad_picture") from err
            sources[stem] = path
        out = work / "theme"
        theme_build.build(sources, out)
        (out / "theme.json").write_text(
            json.dumps(
                {k: meta[k] for k in ("name", "panel", "fonts", "knob") if k in meta}
                | {"name": names},
                ensure_ascii=False,
                indent=1,
            ),
            "utf-8",
        )
        target = folder / theme_id
        if target.exists():
            shutil.rmtree(target)
        out.rename(target)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    reload()
    return load_themes()[theme_id]


def delete(theme_id: str) -> None:
    """Remove an own theme."""
    folder = theme_folder(theme_id)
    if folder is None or not theme_id.startswith(OWN_PREFIX):
        raise ThemeError("not_own_theme")
    shutil.rmtree(folder)
    reload()


# ---------------------------------------------------------------- HTTP


class ThemeTemplateView(HomeAssistantView):
    """GET the theme template ZIP."""

    url = "/api/kis_segito/theme/template"
    name = "api:kis_segito:theme_template"

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        data = await hass.async_add_executor_job(template_zip)
        return web.Response(
            body=data,
            content_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="kis-segito-theme.zip"'
            },
        )


class ThemeUploadView(HomeAssistantView):
    """POST a theme package (multipart field "file"); administrators only."""

    url = "/api/kis_segito/theme/upload"
    name = "api:kis_segito:theme_upload"

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message("Only administrators", status_code=403)
        if request.content_length and request.content_length > MAX_UPLOAD:
            return self.json({"code": "too_large"}, status_code=413)
        reader = await request.multipart()
        field = await reader.next()
        if field is None or getattr(field, "name", None) != "file":
            return self.json({"code": "no_file"}, status_code=400)
        data = bytearray()
        while chunk := await field.read_chunk():
            data.extend(chunk)
            if len(data) > MAX_UPLOAD:
                return self.json({"code": "too_large"}, status_code=413)
        try:
            theme = await hass.async_add_executor_job(install, bytes(data))
        except ThemeError as err:
            return self.json({"code": err.code}, status_code=400)
        manager = hass.data[DOMAIN].manager
        if manager.settings.get("theme") == theme["id"]:
            # The knobs restart to fetch the new pictures.
            await manager.async_theme_updated()
        manager.async_notify_listeners()
        return self.json(
            {
                "id": theme["id"],
                "count": theme.get("count"),
                "total": theme.get("total"),
            }
        )


# ---------------------------------------------------------------- WebSocket


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/themes/active",
        vol.Required("theme_id"): str,
        vol.Required("active"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_theme_active(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Switch a theme off (not offered in the picker) or on again."""
    manager = hass.data[DOMAIN].manager
    theme_id = msg["theme_id"]
    if theme_id == DEFAULT_THEME:
        connection.send_error(msg["id"], "default_theme", "The default theme stays on")
        return
    off = set(manager.settings.get("themes_off", []))
    off = off - {theme_id} if msg["active"] else off | {theme_id}
    changes: dict[str, Any] = {"themes_off": sorted(off)}
    if not msg["active"] and manager.settings.get("theme") == theme_id:
        changes["theme"] = DEFAULT_THEME
    user = connection.user.name if connection.user else None
    await manager.async_update_settings(changes, who=user or "parent")
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/themes/delete", vol.Required("theme_id"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_theme_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete an own theme (the built-in ones stay)."""
    manager = hass.data[DOMAIN].manager
    try:
        await hass.async_add_executor_job(delete, msg["theme_id"])
    except ThemeError as err:
        connection.send_error(msg["id"], err.code, "Not an own theme")
        return
    changes: dict[str, Any] = {
        "themes_off": [
            t for t in manager.settings.get("themes_off", []) if t != msg["theme_id"]
        ]
    }
    if manager.settings.get("theme") == msg["theme_id"]:
        changes["theme"] = DEFAULT_THEME
    user = connection.user.name if connection.user else None
    await manager.async_update_settings(changes, who=user or "parent")
    connection.send_result(msg["id"])


@callback
def async_register_theme_api(hass: HomeAssistant) -> None:
    """Register the theme views and commands."""
    hass.http.register_view(ThemeTemplateView())
    hass.http.register_view(ThemeUploadView())
    websocket_api.async_register_command(hass, ws_theme_active)
    websocket_api.async_register_command(hass, ws_theme_delete)
