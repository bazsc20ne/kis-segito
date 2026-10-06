# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the config flow and setup."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN, PANEL_URL_PATH


def _esphome_device(hass: HomeAssistant) -> dr.DeviceEntry:
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={"host": "192.0.2.1", "device_name": "test-knob"},
    )
    esphome_entry.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:01")},
        name="Test knob",
    )


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    device = _esphome_device(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: device.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test knob"
    assert result["data"] == {CONF_DEVICE_ID: device.id}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: device.id}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_setup_registers_panel_and_pushes_strings(hass: HomeAssistant) -> None:
    hass.config.language = "hu"
    device = _esphome_device(hass)

    calls: list[ServiceCall] = []

    async def _set_ui_strings(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("esphome", "test_knob_set_ui_strings", _set_ui_strings)

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert PANEL_URL_PATH in hass.data["frontend_panels"]

    # The automatic push is debounced; trigger it directly.
    entry.runtime_data._debouncer.async_cancel()
    await entry.runtime_data.async_push_strings()
    await hass.async_block_till_done()
    assert calls
    assert calls[-1].data["language"] == "hu"
    assert len(calls[-1].data["keys"]) == len(calls[-1].data["values"])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH not in hass.data["frontend_panels"]
