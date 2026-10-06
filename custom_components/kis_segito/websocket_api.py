# SPDX-License-Identifier: AGPL-3.0-only
"""WebSocket commands used by the Kis Segito panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DEVICE_ID, DOMAIN


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the panel's WebSocket commands."""
    websocket_api.async_register_command(hass, ws_info)


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
