# SPDX-License-Identifier: AGPL-3.0-only
"""Sidebar panel registration."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL,
)

FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_register_static_files(hass: HomeAssistant) -> None:
    """Serve the frontend files (can only be done once per HA run)."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
    )


async def async_register_panel(hass: HomeAssistant, version: str) -> None:
    """Add the sidebar entry."""
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_ELEMENT,
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{STATIC_URL}/kis-segito-panel.js?v={version}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"domain": DOMAIN, "static_url": STATIC_URL, "version": version},
    )


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)


def panel_language_names() -> dict[str, str]:
    """Native language names from the panel translations ("language.name")."""
    names: dict[str, str] = {}
    for path in (FRONTEND_DIR / "translations").glob("*.json"):
        with path.open(encoding="utf-8") as file:
            name = json.load(file).get("language.name")
        if name:
            names[path.stem] = str(name)
    return names
