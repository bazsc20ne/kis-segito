# SPDX-License-Identifier: AGPL-3.0-only
"""End-to-end test of the knob protocol: state push and actions."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN


async def test_state_push_and_action(hass: HomeAssistant) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:03")},
        name="Knob",
    )
    action_entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "esphome",
        "knob-action",
        device_id=device.id,
        config_entry=esphome_entry,
        original_name="Action",
    )
    hass.states.async_set(action_entity.entity_id, "")

    states: list[dict] = []

    async def _set_state(call: ServiceCall) -> None:
        states.append(json.loads(call.data["data"]))

    async def _set_ui_strings(call: ServiceCall) -> None:
        return

    hass.services.async_register("esphome", "test_knob_set_state", _set_state)
    hass.services.async_register("esphome", "test_knob_set_ui_strings", _set_ui_strings)

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    manager = hass.data[DOMAIN].manager
    child = await manager.async_save_item(
        "children", {"name": "Kid", "color": "#FF0000"}
    )
    reward = await manager.async_save_item(
        "rewards", {"name": "Treat", "cost": 3, "icon": "reward_treat"}
    )
    await manager.async_adjust(child["id"], 5)

    link = entry.runtime_data
    link._state_debouncer.async_cancel()
    await link.async_push_state()
    snapshot = states[-1]
    assert snapshot["v"] == 1
    assert snapshot["children"][0]["w"] == 5
    assert snapshot["children"][0]["c"] == "#FF0000"
    assert snapshot["rewards"][0]["i"] == "reward_treat"

    # The knob reports a redemption on its Action sensor.
    action = {"a": "redeem", "id": "abc123", "c": child["id"], "r": reward["id"]}
    hass.states.async_set(action_entity.entity_id, json.dumps(action))
    await hass.async_block_till_done()
    assert manager.balances(child["id"])["wallet"] == 2
    # The same action again (e.g. after a reconnect) is not booked twice.
    hass.states.async_set(action_entity.entity_id, "")
    hass.states.async_set(action_entity.entity_id, json.dumps(action))
    await hass.async_block_till_done()
    assert manager.balances(child["id"])["wallet"] == 2
