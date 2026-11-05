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
    return {
        "id": theme,
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


@cache
def load_themes() -> dict[str, dict[str, Any]]:
    """All themes whose pictures are complete, the default one first."""
    themes: dict[str, dict[str, Any]] = {}
    for folder in sorted(THEMES_DIR.iterdir()) if THEMES_DIR.is_dir() else []:
        meta = folder / "theme.json"
        if not folder.is_dir() or not THEME_ID.match(folder.name) or not meta.is_file():
            continue
        if missing_files(folder.name):
            continue
        themes[folder.name] = _clean(folder.name, _read_json(meta))
    default = themes.pop(DEFAULT_THEME, _clean(DEFAULT_THEME, {}))
    return {DEFAULT_THEME: default} | themes


def theme(theme_id: str | None) -> dict[str, Any]:
    """A theme by id; the default one when it is unknown or incomplete."""
    themes = load_themes()
    return themes.get(theme_id or DEFAULT_THEME) or themes[DEFAULT_THEME]
