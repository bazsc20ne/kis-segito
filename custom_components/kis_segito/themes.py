# SPDX-License-Identifier: AGPL-3.0-only
"""Themes: the look of the panel, the cards and the knobs.

Each theme is a folder in frontend/themes/<id>/ with a theme.json:

    {
      "name": {"en": "…", "hu": "…"},
      "panel": {"light": {"--bg": "#…", …}, "dark": {…}},   # CSS variables
      "fonts": {"display": "display.woff2", "body": "body.woff2"},
      "knob": {"bg": "#…", "track": "#…", …}                # see KNOB_COLORS
    }

and its pictures (made by tools/build_theme_assets.py): icons/, knob/ and
backgrounds/. The default theme ("kis_segito") uses the built-in pictures. A
theme is offered only when every picture is there, so a theme never mixes its
pictures with the default ones.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from .theme_build import source_names

THEMES_DIR = Path(__file__).parent / "frontend" / "themes"
ICONS_DIR = Path(__file__).parent / "frontend" / "icons"
DEFAULT_THEME = "kis_segito"
THEME_ID = re.compile(r"^[a-z0-9_]{1,32}$")
BACKGROUNDS = tuple(f"bg_{n}.jpg" for n in range(1, 7))
LOGOS = ("brand_logo.webp", "brand_logo_en.webp")
# Knob colours a theme can set ("#RRGGBB").
KNOB_COLORS = (
    "bg",  # screen background
    "track",  # time ring
    "ok",  # ring zones: on time, soon, late
    "warn",
    "late",
    "deposit",  # piggy bank: tokens in, tokens out
    "withdraw",
    "pill",  # number pills
    "number",  # numbers on the pills
)
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


@cache
def required_files() -> list[str]:
    """Every picture a theme must have, relative to its folder."""
    files = [f"icons/{path.name}" for path in ICONS_DIR.glob("*.png")]
    files += [
        f"icons/small/{path.name}" for path in (ICONS_DIR / "small").glob("*.png")
    ]
    files += [f"icons/{name}" for name in LOGOS]
    files += [f"backgrounds/{name}" for name in BACKGROUNDS]
    files += [f"knob/{name}" for name in _read_json(THEMES_DIR / "knob_pictures.json")]
    return sorted(files)


def missing_files(theme: str) -> list[str]:
    """The pictures a theme still lacks (empty for the default theme)."""
    if theme == DEFAULT_THEME:
        return []
    folder = THEMES_DIR / theme
    return [name for name in required_files() if not (folder / name).is_file()]


def _clean(theme: str, data: dict[str, Any]) -> dict[str, Any]:
    """A theme.json with only the parts this version understands."""
    names = data.get("name") or {}
    panel = data.get("panel") or {}
    fonts = data.get("fonts") or {}
    knob = data.get("knob") or {}
    order = data.get("order")
    return {
        "id": theme,
        # Place in the picker (bundled themes; own themes come after them).
        "order": order if isinstance(order, int) else 1000,
        "name": {k: str(v) for k, v in names.items() if isinstance(v, str)},
        "panel": {
            mode: {
                str(k): str(v)
                for k, v in (panel.get(mode) or {}).items()
                if str(k).startswith("--") and isinstance(v, str)
            }
            for mode in ("light", "dark")
        },
        "fonts": {
            key: str(fonts[key])
            for key in ("display", "body")
            if isinstance(fonts.get(key), str)
            and re.match(r"^[a-z0-9_.-]+\.woff2$", fonts[key])
        },
        "knob": {
            key: str(knob[key])
            for key in KNOB_COLORS
            if isinstance(knob.get(key), str) and COLOR.match(knob[key])
        },
    }


# Themes made by the user (uploaded in the panel) live in Home Assistant's
# configuration folder, so an update of the integration keeps them; they are
# served under OWN_URL. Their ids start with OWN_PREFIX. They may be partial:
# a picture they lack is the built-in one.
OWN_URL = "/kis_segito_own_themes"
OWN_PREFIX = "my_"
_own_dir: Path | None = None


def set_own_dir(path: Path | None) -> None:
    """Where the user's own themes are (set up by the integration)."""
    global _own_dir  # noqa: PLW0603 - one folder per Home Assistant
    _own_dir = path
    _scan.cache_clear()  # read again in an executor (async_load_icon_lists)


def own_dir() -> Path | None:
    return _own_dir


def reload() -> None:
    """Read the themes again (after an own theme was added or removed). Runs
    in an executor: the folders are read right away, not later in the event
    loop."""
    _scan.cache_clear()
    _scan()


def _describe(theme_id: str, folder: Path, base: str, own: bool) -> dict[str, Any]:
    data = _clean(theme_id, _read_json(folder / "theme.json"))
    required = required_files()
    present = [name for name in required if (folder / name).is_file()]
    # Counted in pictures (as in the template), not in rendered files.
    names = source_names()
    own_pictures = sum(
        1
        for name in names
        if (folder / "icons" / f"{name}.png").is_file()
        or (folder / "icons" / f"{name}.webp").is_file()
        or (folder / "backgrounds" / f"{name}.jpg").is_file()
        or any((folder / "knob").glob(f"{name}_[0-9]*.png"))
    )
    data |= {
        "own": own,
        "base": base,
        # Changes when the theme is uploaded again (the browsers' copies go).
        "rev": (folder / "theme.json").stat().st_mtime_ns // 1_000_000,
        "complete": len(present) == len(required),
        "count": own_pictures,
        "total": len(names),
    }
    if not data["complete"]:
        # What the theme has; everything else is the built-in picture.
        data["has"] = present
    return data


@cache
def _scan() -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    themes: dict[str, dict[str, Any]] = {}
    folders: dict[str, Path] = {}
    for folder in sorted(THEMES_DIR.iterdir()) if THEMES_DIR.is_dir() else []:
        if (
            not folder.is_dir()
            or not THEME_ID.match(folder.name)
            or folder.name.startswith(OWN_PREFIX)
            or not (folder / "theme.json").is_file()
        ):
            continue
        if folder.name == DEFAULT_THEME:
            themes[DEFAULT_THEME] = _clean(
                DEFAULT_THEME, _read_json(folder / "theme.json")
            )
            themes[DEFAULT_THEME] |= {"own": False, "base": "", "complete": True}
            continue
        if missing_files(folder.name):
            continue  # a bundled theme is offered only when it is complete
        themes[folder.name] = _describe(
            folder.name, folder, f"/kis_segito_static/themes/{folder.name}", own=False
        )
        folders[folder.name] = folder
    if _own_dir is not None and _own_dir.is_dir():
        for folder in sorted(_own_dir.iterdir()):
            if (
                folder.is_dir()
                and THEME_ID.match(folder.name)
                and folder.name.startswith(OWN_PREFIX)
                and (folder / "theme.json").is_file()
            ):
                themes[folder.name] = _describe(
                    folder.name, folder, f"{OWN_URL}/{folder.name}", own=True
                )
                folders[folder.name] = folder
    default = themes.pop(DEFAULT_THEME, None) or (
        _clean(DEFAULT_THEME, {}) | {"own": False, "base": "", "complete": True}
    )
    ordered = sorted(themes.values(), key=lambda t: (t["own"], t["order"], t["id"]))
    return {DEFAULT_THEME: default} | {t["id"]: t for t in ordered}, folders


def load_themes() -> dict[str, dict[str, Any]]:
    """All themes that can be chosen, the default one first."""
    return _scan()[0]


def theme_folder(theme_id: str) -> Path | None:
    """The folder of a theme's pictures (None for the default theme)."""
    return _scan()[1].get(theme_id)


def theme(theme_id: str | None) -> dict[str, Any]:
    """A theme by id; the default one when it is unknown or incomplete."""
    themes = load_themes()
    return themes.get(theme_id or DEFAULT_THEME) or themes[DEFAULT_THEME]


def has_file(theme_id: str, name: str) -> bool:
    """Whether a theme has its own version of a picture (e.g. "backgrounds/bg_2.jpg")."""
    folder = theme_folder(theme_id)
    return folder is not None and (folder / name).is_file()


def theme_assets(theme_data: dict[str, Any]) -> dict[str, Any] | None:
    """Where a theme's pictures are, for the cards and the virtual knob
    (None: the built-in ones)."""
    if theme_data["id"] == DEFAULT_THEME or not theme_data.get("base"):
        return None
    assets = {"base": theme_data["base"], "rev": theme_data.get("rev", 0)}
    if not theme_data.get("complete"):
        assets["has"] = theme_data.get("has", [])
    return assets
