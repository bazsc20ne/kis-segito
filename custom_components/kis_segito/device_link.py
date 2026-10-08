# SPDX-License-Identifier: AGPL-3.0-only
"""Link between a config entry and its ESPHome knob device.

The integration talks to the knob only through the ESPHome native API: the
firmware exposes API actions, which the ESPHome integration registers as
``esphome.<node_name>_<action>`` services. This module resolves those service
names and pushes the on-screen strings in the chosen language (by default the
Home Assistant language) and the data snapshot (``set_state``). The knob reports
the child's actions through its "Action" text sensor (JSON); see
docs/protocol.md.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import slugify

from .const import (
    ACTION_SENSOR_NAME,
    DEFAULT_LANGUAGE,
    DOMAIN,
    ESPHOME_ACTION_SET_STATE,
    ESPHOME_ACTION_SET_UI_STRINGS,
    ESPHOME_DOMAIN,
    SECURITY_DOCS_URL,
)

if TYPE_CHECKING:
    from .manager import KisSegitoManager

_LOGGER = logging.getLogger(__name__)

DEVICE_TRANSLATIONS_DIR = Path(__file__).parent / "device_translations"

# Limits for what a knob reports (see docs/protocol.md, "Actions").
ACTION_MAX_BYTES = 255  # also the longest Home Assistant state
ACTION_RATE_COUNT = 20
ACTION_RATE_WINDOW_S = 60.0
_ID = vol.All(str, vol.Match(r"^[\w.:-]{1,64}\Z"))
ACTION_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Required("a"): "task",
            vol.Required("id"): _ID,
            vol.Required("c"): _ID,
            vol.Required("r"): _ID,
            vol.Required("t"): _ID,
        }
    ),
    vol.Schema(
        {
            vol.Required("a"): "redeem",
            vol.Required("id"): _ID,
            vol.Required("c"): _ID,
            vol.Required("r"): _ID,
        }
    ),
    vol.Schema(
        {
            vol.Required("a"): "piggy",
            vol.Required("id"): _ID,
            vol.Required("c"): _ID,
            vol.Required("n"): vol.All(
                int, vol.NotIn([0]), vol.Range(min=-100_000, max=100_000)
            ),
        }
    ),
    vol.Schema(
        {
            vol.Required("a"): "seen",
            vol.Required("id"): _ID,
            vol.Required("c"): _ID,
        }
    ),
)


def parse_action(raw: str) -> dict[str, Any] | None:
    """A knob action, or None when it is too big, unreadable or not allowed."""
    if len(raw.encode()) > ACTION_MAX_BYTES:
        return None
    try:
        action = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(action, dict) or isinstance(action.get("n"), bool):
        return None
    try:
        return ACTION_SCHEMA(action)
    except vol.Invalid:
        return None


def api_encrypted(hass: HomeAssistant, device: dr.DeviceEntry) -> bool:
    """Whether Home Assistant talks to this ESPHome device with an encryption key."""
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == ESPHOME_DOMAIN:
            return bool(entry.data.get("noise_psk"))
    return False


def unencrypted_issue_id(device_id: str) -> str:
    """Repair issue id for a knob without API encryption."""
    return f"unencrypted_api_{device_id}"


def _load_strings_file(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return {str(key): str(value) for key, value in data.items()}


def available_languages() -> list[str]:
    """Language codes the knob has translations for (from the JSON files)."""
    return sorted(path.stem for path in DEVICE_TRANSLATIONS_DIR.glob("*.json"))


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
    """Keeps one knob supplied with UI strings and data, and runs its actions."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        language: Callable[[], str | None] | None = None,
        manager: KisSegitoManager | None = None,
    ) -> None:
        self.hass = hass
        self.device_id = device_id
        self.manager = manager
        # Returns the language to send; defaults to the Home Assistant language.
        self._language = language or (lambda: self.hass.config.language)
        self._unsubs: list[CALLBACK_TYPE] = []
        self._action_entity: str | None = None
        self._action_times: deque[float] = deque()
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=2.0,
            immediate=False,
            function=self.async_push_strings,
        )
        self._state_debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=0.5,
            immediate=False,
            function=self.async_push_state,
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
        """Send the on-screen strings in the chosen language."""
        service = self._service(ESPHOME_ACTION_SET_UI_STRINGS)
        if service is None:
            _LOGGER.debug(
                "Knob %s has no %s action (yet)",
                self.device_id,
                ESPHOME_ACTION_SET_UI_STRINGS,
            )
            return
        language, strings = await self.hass.async_add_executor_job(
            load_device_strings, self._language()
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

    async def async_push_state(self) -> None:
        """Send the data snapshot (children, rewards, today's routines)."""
        if self.manager is None:
            return
        service = self._service(ESPHOME_ACTION_SET_STATE)
        if service is None:
            _LOGGER.debug(
                "Knob %s has no %s action (yet)",
                self.device_id,
                ESPHOME_ACTION_SET_STATE,
            )
            return
        language, _strings = await self.hass.async_add_executor_job(
            load_device_strings, self._language()
        )
        try:
            base_url: str | None = get_url(
                self.hass,
                allow_internal=True,
                allow_external=True,
                prefer_external=False,
                allow_cloud=False,
            )
        except NoURLAvailableError:
            base_url = None
        # The picture secret travels only over an encrypted API connection.
        if not self._check_encryption():
            base_url = None
        snapshot = self.manager.snapshot(self.device_id, language, base_url)
        payload = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False)
        await self.hass.services.async_call(
            ESPHOME_DOMAIN, service, {"data": payload}, blocking=True
        )
        _LOGGER.debug("Sent state (%d bytes) to %s", len(payload), service)

    def _check_encryption(self) -> bool:
        """Whether the API is encrypted; raises or clears a repair issue."""
        device = dr.async_get(self.hass).async_get(self.device_id)
        encrypted = device is not None and api_encrypted(self.hass, device)
        issue_id = unencrypted_issue_id(self.device_id)
        if encrypted:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        else:
            name = (device.name_by_user or device.name) if device else self.device_id
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="unencrypted_api",
                translation_placeholders={"name": str(name)},
                learn_more_url=SECURITY_DOCS_URL,
            )
        return encrypted

    @callback
    def async_schedule_state(self) -> None:
        """Push the data snapshot soon (after a data change)."""
        self.hass.async_create_task(self._state_debouncer.async_call())

    async def _async_run_action(self, raw: str) -> None:
        if self.manager is None:
            return
        now = time.monotonic()
        while self._action_times and now - self._action_times[0] > ACTION_RATE_WINDOW_S:
            self._action_times.popleft()
        if len(self._action_times) >= ACTION_RATE_COUNT:
            _LOGGER.warning("Knob %s sends too many actions; ignored", self.device_id)
            return
        self._action_times.append(now)
        action = parse_action(raw)
        if action is None:
            _LOGGER.warning("Knob %s sent an invalid action; ignored", self.device_id)
            return
        await self.manager.async_device_action(action)
        # Refused actions change nothing: resend so the knob drops its guess.
        self.async_schedule_state()

    @callback
    def async_start(self) -> None:
        """Push now, and again on reconnect or language change."""
        entries = er.async_entries_for_device(er.async_get(self.hass), self.device_id)
        entity_ids = [entry.entity_id for entry in entries]
        self._action_entity = next(
            (
                entry.entity_id
                for entry in entries
                if entry.domain == "sensor"
                and (
                    entry.original_name == ACTION_SENSOR_NAME
                    or entry.entity_id.endswith("_action")
                )
            ),
            None,
        )
        if self.manager is not None:
            self._unsubs.append(
                self.manager.async_add_listener(self.async_schedule_state)
            )
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
        self.async_schedule_state()

    @callback
    def async_schedule_push(self) -> None:
        """Push the strings again soon (e.g. after a language change)."""
        self.hass.async_create_task(self._debouncer.async_call())

    @callback
    def async_stop(self) -> None:
        """Stop listening."""
        while self._unsubs:
            self._unsubs.pop()()
        self._debouncer.async_cancel()
        self._state_debouncer.async_cancel()

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if old_state is None or old_state.state == STATE_UNAVAILABLE:
            # The knob (re)connected: it needs strings and data again.
            self.hass.async_create_task(self._debouncer.async_call())
            self.async_schedule_state()
            return
        if (
            event.data["entity_id"] == self._action_entity
            and new_state.state != old_state.state
        ):
            self.hass.async_create_task(self._async_run_action(new_state.state))

    @callback
    def _async_core_config_updated(self, event: Event) -> None:
        self.hass.async_create_task(self._debouncer.async_call())
