# SPDX-License-Identifier: AGPL-3.0-only
"""Persistent storage for Kis Segito data.

All user data of the integration (later: routines, tasks, ...) lives in a single
JSON document under ``.storage/kis_segito``. The schema is versioned so later
releases can migrate it.

Layout so far::

    {
      "settings": {"language": "auto" | "<code>"},
      "devices": {"<device_id>": {"language": "auto" | "<code>"}}
    }

A per-device language overrides the global one; "auto" (or a missing value)
defers to the next level, ending at the Home Assistant language.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import LANGUAGE_AUTO, STORAGE_KEY, STORAGE_VERSION


def _empty_data() -> dict[str, Any]:
    return {}


class KisSegitoStore:
    """Thin wrapper around the Home Assistant Store helper."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self.data: dict[str, Any] = _empty_data()

    async def async_load(self) -> None:
        """Load data from disk, starting empty when nothing is stored yet."""
        stored = await self._store.async_load()
        self.data = stored if isinstance(stored, dict) else _empty_data()

    async def async_save(self) -> None:
        """Write the current data to disk."""
        await self._store.async_save(self.data)

    @property
    def language(self) -> str:
        """Global language setting ("auto" or a language code)."""
        return str(self.data.get("settings", {}).get("language", LANGUAGE_AUTO))

    def set_language(self, language: str) -> None:
        """Change the global language setting (call async_save afterwards)."""
        self.data.setdefault("settings", {})["language"] = language

    def device_language(self, device_id: str) -> str:
        """Per-device language override ("auto" when none)."""
        device = self.data.get("devices", {}).get(device_id, {})
        return str(device.get("language", LANGUAGE_AUTO))

    def effective_language(
        self, device_id: str | None, ha_language: str | None
    ) -> str | None:
        """Language to use: device override, then global setting, then HA."""
        for value in (
            self.device_language(device_id) if device_id else LANGUAGE_AUTO,
            self.language,
        ):
            if value != LANGUAGE_AUTO:
                return value
        return ha_language
