# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the language setting."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN
from custom_components.kis_segito.store import KisSegitoStore


async def test_effective_language(hass: HomeAssistant) -> None:
    store = KisSegitoStore(hass)
    assert store.language == "auto"
    assert store.effective_language("dev", "en") == "en"
    store.set_language("hu")
    assert store.effective_language("dev", "en") == "hu"
    store.data["devices"] = {"dev": {"language": "en"}}
    assert store.effective_language("dev", "de") == "en"
    assert store.effective_language("other", "de") == "hu"


async def test_language_setting_is_pushed(hass: HomeAssistant, hass_ws_client) -> None:
    hass.config.language = "en"
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={"host": "192.0.2.1", "device_name": "test-knob"},
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:01")},
        name="Test knob",
    )
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

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/settings"})
    result = (await client.receive_json())["result"]
    assert result["language"] == "auto"
    assert {"code": "hu", "name": "Magyar"} in result["languages"]

    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/settings/update", "language": "xx"}
    )
    assert not (await client.receive_json())["success"]

    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/settings/update", "language": "hu"}
    )
    assert (await client.receive_json())["result"]["language"] == "hu"

    entry.runtime_data._debouncer.async_cancel()
    await entry.runtime_data.async_push_strings()
    await hass.async_block_till_done()
    assert calls[-1].data["language"] == "hu"
