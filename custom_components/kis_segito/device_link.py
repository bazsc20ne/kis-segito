# SPDX-License-Identifier: AGPL-3.0-only
"""Link between a config entry and its ESPHome knob device.

The integration talks to the knob only through the ESPHome native API: the
firmware exposes API actions, which the ESPHome integration registers as
``esphome.<node_name>_<action>`` services. This module resolves those service
names and pushes the on-screen strings in the Home Assistant language.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, STATE_UNAVAILABLE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.util import slugify

from .const import DEFAULT_LANGUAGE, ESPHOME_ACTION_SET_UI_STRINGS, ESPHOME_DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_TRANSLATIONS_DIR = Path(__file__).parent / "device_translations"


def _load_strings_file(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return {str(key): str(value) for key, value in data.items()}


def load_device_strings(language: str | None) -> tuple[str, dict[str, str]]:
    """Return (language, strings) for the knob display.

    Falls back from e.g. ``pt-BR`` to ``pt`` and finally to English; missing keys
    are filled from English so the device always gets a complete set.
    """
    available = {path.stem for path in DEVICE_TRANSLATIONS_DIR.glob("*.json")}
    chosen = DEFAULT_LANGUAGE
    if language:
        for candidate in (language, language.split("-")[0]):
            if candidate in available:
                chosen = candidate
                break
    strings = _load_strings_file(DEVICE_TRANSLATIONS_DIR / f"{DEFAULT_LANGUAGE}.json")
    if chosen != DEFAULT_LANGUAGE:
        strings.update(_load_strings_file(DEVICE_TRANSLATIONS_DIR / f"{chosen}.json"))
    return chosen, strings


def esphome_node_name(hass: HomeAssistant, device: dr.DeviceEntry) -> str | None:
    """Return the ESPHome node name of a device, used in its service names."""
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != ESPHOME_DOMAIN:
            continue
        if name := entry.data.get("device_name"):
            return str(name)
    return None


def esphome_service_name(node_name: str, action: str) -> str:
    """Mirror how the ESPHome integration names user-defined API actions."""
    return f"{node_name.replace('-', '_')}_{action}"


class DeviceLink:
    """Keeps one knob device supplied with UI strings."""

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        self.hass = hass
        self.device_id = device_id
        self._unsubs: list[CALLBACK_TYPE] = []
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=2.0,
            immediate=False,
            function=self.async_push_strings,
        )

    def _service(self, action: str) -> str | None:
        device = dr.async_get(self.hass).async_get(self.device_id)
        if device is None:
            return None
        node_name = esphome_node_name(self.hass, device)
        if node_name is None and device.name:
            node_name = slugify(device.name)
        if node_name is None:
            return None
        service = esphome_service_name(node_name, action)
        if not self.hass.services.has_service(ESPHOME_DOMAIN, service):
            return None
        return service

    async def async_push_strings(self) -> None:
        """Send the on-screen strings in the Home Assistant language."""
        service = self._service(ESPHOME_ACTION_SET_UI_STRINGS)
        if service is None:
            _LOGGER.debug(
                "Knob %s has no %s action (yet)",
                self.device_id,
                ESPHOME_ACTION_SET_UI_STRINGS,
            )
            return
        language, strings = await self.hass.async_add_executor_job(
            load_device_strings, self.hass.config.language
        )
        data: dict[str, Any] = {
            "language": language,
            "keys": list(strings),
            "values": list(strings.values()),
        }
        await self.hass.services.async_call(
            ESPHOME_DOMAIN, service, data, blocking=True
        )
        _LOGGER.debug("Sent %d UI strings (%s) to %s", len(strings), language, service)

    @callback
    def async_start(self) -> None:
        """Push now, and again on reconnect or language change."""
        entity_ids = [
            entry.entity_id
            for entry in er.async_entries_for_device(
                er.async_get(self.hass), self.device_id
            )
        ]
        if entity_ids:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, entity_ids, self._async_state_changed
                )
            )
        self._unsubs.append(
            self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, self._async_core_config_updated
            )
        )
        self.hass.async_create_task(self._debouncer.async_call())

    @callback
    def async_stop(self) -> None:
        """Stop listening."""
        while self._unsubs:
            self._unsubs.pop()()
        self._debouncer.async_cancel()

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if new_state is None or new_state.state == STATE_UNAVAILABLE:
            return
        if old_state is None or old_state.state == STATE_UNAVAILABLE:
            self.hass.async_create_task(self._debouncer.async_call())

    @callback
    def _async_core_config_updated(self, event: Event) -> None:
        self.hass.async_create_task(self._debouncer.async_call())
