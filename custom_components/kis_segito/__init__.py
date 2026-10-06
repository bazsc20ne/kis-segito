# SPDX-License-Identifier: AGPL-3.0-only
"""The Kis Segito integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import CONF_DEVICE_ID, DOMAIN
from .device_link import DeviceLink
from .panel import (
    async_register_panel,
    async_register_static_files,
    async_unregister_panel,
)
from .store import KisSegitoStore
from .websocket_api import async_register_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type KisSegitoConfigEntry = ConfigEntry[DeviceLink]


@dataclass
class KisSegitoData:
    """Integration-wide state shared by all config entries."""

    version: str
    store: KisSegitoStore
    static_registered: bool = False
    panel_registered: bool = False
    entry_ids: set[str] = field(default_factory=set)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration-wide parts that do not depend on a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    store = KisSegitoStore(hass)
    await store.async_load()
    hass.data[DOMAIN] = KisSegitoData(version=str(integration.version), store=store)
    async_register_commands(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KisSegitoConfigEntry) -> bool:
    """Set up one knob."""
    data: KisSegitoData = hass.data[DOMAIN]
    if not data.static_registered:
        await async_register_static_files(hass)
        data.static_registered = True
    if not data.panel_registered:
        await async_register_panel(hass, data.version)
        data.panel_registered = True
    data.entry_ids.add(entry.entry_id)

    link = DeviceLink(hass, entry.data[CONF_DEVICE_ID])
    entry.runtime_data = link
    link.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KisSegitoConfigEntry) -> bool:
    """Unload one knob; remove the panel with the last one."""
    entry.runtime_data.async_stop()
    data: KisSegitoData = hass.data[DOMAIN]
    data.entry_ids.discard(entry.entry_id)
    if not data.entry_ids and data.panel_registered:
        async_unregister_panel(hass)
        data.panel_registered = False
    return True
