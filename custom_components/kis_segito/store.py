# SPDX-License-Identifier: AGPL-3.0-only
"""Persistent storage for Kis Segito data.

Two documents under ``.storage``:

- ``kis_segito``: configuration and daily progress (settings, children,
  routines, rewards, per-day completions, streaks);
- ``kis_segito_ledger``: the append-only token ledger and the processed
  device action ids. Kept separate so configuration changes and migrations
  can never touch token history.

Both carry a schema version; ``_migrate_config`` upgrades older layouts.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import LANGUAGE_AUTO, STORAGE_KEY, STORAGE_VERSION

LEDGER_KEY = f"{STORAGE_KEY}_ledger"
SCHEMA = 2

DEFAULT_SETTINGS: dict[str, Any] = {
    "language": LANGUAGE_AUTO,
    "animation_mode": "full",
    "inactivity_s": 60,
    "streak_target": 7,
    "streak_reward": 5,
    "piggy_interest_percent": 10,
    "piggy_interest_weekday": 6,  # Sunday
    "piggy_interest_time": "18:00",
    "piggy_interest_min": None,
    "piggy_interest_max": None,
    # Scripts with this Home Assistant label are offered as notification targets.
    "notification_label": "Kis Segítő",
    # Background of the knob and the panel: "" (none), a preset ("bg_1" …) or
    # an uploaded picture id; a child's own background overrides it.
    "background": "",
}

# Configuration audit entries kept (token history is in the ledger).
AUDIT_KEPT = 1000


def _empty_config() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "settings": dict(DEFAULT_SETTINGS),
        "children": [],
        "routines": [],
        "rewards": [],
        "devices": {},
        "days": {},
        "streaks": {},
        "overrides": {},
        # Day templates: [{"id", "name", "icon", "routines": [ids]}]; weekday
        # defaults (0 = Monday) and per-date choices refer to template ids.
        "templates": [],
        "weekday_templates": {},
        "date_templates": {},
        "notifications": [],
        "audit": [],
    }


def _migrate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Bring a stored document to the current schema without losing data."""
    result = _empty_config()
    # Schema 1 (v0.2.x) only had {"settings": {"language": ...}, "devices": {...}}.
    for key, value in data.items():
        if key == "settings" and isinstance(value, dict):
            result["settings"].update(value)
        elif key in result and key != "schema":
            result[key] = value
    result["schema"] = SCHEMA
    return result


class KisSegitoStore:
    """Configuration document and ledger document."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self._ledger_store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, LEDGER_KEY, private=True, atomic_writes=True
        )
        self.data: dict[str, Any] = _empty_config()
        self.ledger: dict[str, Any] = {"transactions": [], "actions": {}}

    async def async_load(self) -> None:
        """Load both documents, starting empty when nothing is stored yet."""
        stored = await self._store.async_load()
        self.data = _migrate_config(stored if isinstance(stored, dict) else {})
        ledger = await self._ledger_store.async_load()
        if isinstance(ledger, dict):
            self.ledger = {
                "transactions": list(ledger.get("transactions", [])),
                "actions": dict(ledger.get("actions", {})),
            }

    async def async_save(self) -> None:
        """Write the configuration document."""
        await self._store.async_save(self.data)

    async def async_save_ledger(self) -> None:
        """Write the ledger document (right away: token history matters)."""
        await self._ledger_store.async_save(self.ledger)

    # Settings ------------------------------------------------------------

    @property
    def settings(self) -> dict[str, Any]:
        """Global settings."""
        return self.data["settings"]

    @property
    def language(self) -> str:
        """Global language setting ("auto" or a language code)."""
        return str(self.settings.get("language", LANGUAGE_AUTO))

    def set_language(self, language: str) -> None:
        """Change the global language setting (call async_save afterwards)."""
        self.settings["language"] = language

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
