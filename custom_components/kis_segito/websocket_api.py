# SPDX-License-Identifier: AGPL-3.0-only
"""WebSocket commands used by the Kis Segito panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DEVICE_ID, DOMAIN, LANGUAGE_AUTO
from .device_link import available_languages
from .panel import panel_language_names


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the panel's WebSocket commands."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_settings)
    websocket_api.async_register_command(hass, ws_settings_update)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info"})
@callback
def ws_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return basic information about the integration."""
    data = hass.data[DOMAIN]
    connection.send_result(
        msg["id"],
        {
            "version": data.version,
            "devices": [
                {"entry_id": entry.entry_id, "device_id": entry.data[CONF_DEVICE_ID]}
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            ],
        },
    )


async def _settings(hass: HomeAssistant) -> dict[str, Any]:
    data = hass.data[DOMAIN]
    codes = await hass.async_add_executor_job(available_languages)
    names = await hass.async_add_executor_job(panel_language_names)
    return {
        "language": data.store.language,
        "languages": [{"code": code, "name": names.get(code, code)} for code in codes],
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/settings"})
@websocket_api.async_response
async def ws_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the settings and the languages that can be chosen."""
    connection.send_result(msg["id"], await _settings(hass))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/settings/update",
        vol.Required("language"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_settings_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Change the settings and push the new texts to every knob."""
    language = msg["language"]
    codes = await hass.async_add_executor_job(available_languages)
    if language != LANGUAGE_AUTO and language not in codes:
        connection.send_error(msg["id"], "invalid_language", "Unknown language")
        return
    data = hass.data[DOMAIN]
    data.store.set_language(language)
    await data.store.async_save()
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        entry.runtime_data.async_schedule_push()
    connection.send_result(msg["id"], await _settings(hass))
