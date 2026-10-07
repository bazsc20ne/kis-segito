# SPDX-License-Identifier: AGPL-3.0-only
"""The Kis Segito integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import CONF_DEVICE_ID, DOMAIN
from .device_link import DeviceLink
from .knob_images import KnobImageView
from .logic import parse_hhmm
from .manager import KisSegitoManager
from .notify import Notifier
from .panel import (
    async_register_panel,
    async_register_static_files,
    async_unregister_panel,
)
from .services import async_register_services
from .store import KisSegitoStore
from .websocket_api import async_register_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type KisSegitoConfigEntry = ConfigEntry[DeviceLink]


@dataclass
class KisSegitoData:
    """Integration-wide state shared by all config entries."""

    version: str
    store: KisSegitoStore
    manager: KisSegitoManager
    static_registered: bool = False
    panel_registered: bool = False
    entry_ids: set[str] = field(default_factory=set)
    # The knob entry that carries the integration-wide entities (summary
    # sensors, calendar); another one takes over if it is removed.
    entities_entry_id: str | None = None


PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration-wide parts that do not depend on a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    store = KisSegitoStore(hass)
    await store.async_load()
    manager = KisSegitoManager(hass, store)
    manager.notifier = Notifier(
        hass,
        lambda: store.data["notifications"],
        lambda: store.effective_language(None, hass.config.language),
    )
    hass.data[DOMAIN] = KisSegitoData(
        version=str(integration.version), store=store, manager=manager
    )
    async_register_commands(hass)
    hass.http.register_view(KnobImageView(hass))
    async_register_services(hass, manager)
    _async_schedule_jobs(hass, manager)
    return True


@callback
def _async_schedule_jobs(hass: HomeAssistant, manager: KisSegitoManager) -> None:
    """Daily streak evaluation and the weekly piggy-bank interest."""

    async def _after_midnight(now: datetime) -> None:
        await manager.async_evaluate_day(now.date() - timedelta(days=1))

    async def _every_minute(now: datetime) -> None:
        settings = manager.settings
        try:
            due = parse_hhmm(str(settings.get("piggy_interest_time", "18:00")))
        except ValueError:
            return
        if now.weekday() == int(settings.get("piggy_interest_weekday", 6)) and (
            now.hour,
            now.minute,
        ) == (due.hour, due.minute):
            await manager.async_pay_interest()

    async_track_time_change(hass, _after_midnight, hour=0, minute=0, second=30)
    async_track_time_change(hass, _every_minute, second=5)
    # Catch up a missed evaluation (Home Assistant was off at midnight).
    hass.async_create_task(
        manager.async_evaluate_day(dt_util.now().date() - timedelta(days=1))
    )


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

    device_id = entry.data[CONF_DEVICE_ID]
    link = DeviceLink(
        hass,
        device_id,
        lambda: data.store.effective_language(device_id, hass.config.language),
        data.manager,
    )
    entry.runtime_data = link
    link.async_start()
    if data.entities_entry_id is None:
        data.entities_entry_id = entry.entry_id
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KisSegitoConfigEntry) -> bool:
    """Unload one knob; remove the panel with the last one."""
    entry.runtime_data.async_stop()
    data: KisSegitoData = hass.data[DOMAIN]
    if data.entities_entry_id == entry.entry_id:
        if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
            return False
        data.entities_entry_id = None
        # Another knob entry takes over the integration-wide entities.
        if others := [e for e in data.entry_ids if e != entry.entry_id]:
            hass.config_entries.async_schedule_reload(others[0])
    data.entry_ids.discard(entry.entry_id)
    if not data.entry_ids and data.panel_registered:
        async_unregister_panel(hass)
        data.panel_registered = False
    return True
