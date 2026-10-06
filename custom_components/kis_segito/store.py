# SPDX-License-Identifier: AGPL-3.0-only
"""Persistent storage for Kis Segito data.

All user data of the integration (later: routines, tasks, ...) lives in a single
JSON document under ``.storage/kis_segito``. The schema is versioned so later
releases can migrate it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


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
