# SPDX-License-Identifier: AGPL-3.0-only
"""Config flow for Kis Segito."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import DeviceSelector, DeviceSelectorConfig

from .const import CONF_DEVICE_ID, DOMAIN, ESPHOME_DOMAIN


class KisSegitoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Kis Segito knob (an ESPHome device running the kis-segito firmware)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick the knob from the ESPHome devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = dr.async_get(self.hass).async_get(device_id)
            if device is None:
                errors[CONF_DEVICE_ID] = "device_not_found"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.name_by_user or device.name or "Kis Segítő",
                    data={CONF_DEVICE_ID: device_id},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): DeviceSelector(
                        DeviceSelectorConfig(integration=ESPHOME_DOMAIN)
                    )
                }
            ),
            errors=errors,
        )
