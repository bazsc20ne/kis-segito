# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the dashboard cards' WebSocket commands."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN


async def test_cards(
    hass: HomeAssistant, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:08")},
        name="Knob",
        sw_version="0.9.4",
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager
    client = await hass_ws_client(hass)

    async def call(**msg):
        await client.send_json_auto_id(msg)
        return await client.receive_json()

    freezer.move_to(dt_util.now().replace(hour=7, minute=20, second=0, microsecond=0))
    kid = (await manager.async_save_item("children", {"name": "Kid"}))["id"]
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Morning",
            "start": "07:00",
            "end": "08:00",
            "tasks": [{"icon": "task_breakfast", "label": "Eat"}],
        },
    )
    reward = await manager.async_save_item("rewards", {"name": "Treat", "cost": 2})
    await manager.async_adjust(kid, 5)

    data = (await call(type=f"{DOMAIN}/cards"))["result"]
    child = data["children"][0]
    assert child["status"]["wallet"] == 5
    assert child["today"][0]["tasks"][0] == {
        "id": routine["tasks"][0]["id"],
        "label": "Eat",
        "icon": "task_breakfast",
        "done": False,
    }
    assert child["week"]["days"][-1] == {
        "date": dt_util.now().date().isoformat(),
        "done": 0,
        "total": 1,
        "percent": 0,
    }
    assert data["rewards"][0]["id"] == reward["id"]
    assert data["knobs"][0]["sw_version"] == "0.9.4"

    # A parent's tick is logged with the parent's name.
    result = await call(
        type=f"{DOMAIN}/cards/task",
        child_id=kid,
        routine_id=routine["id"],
        task_id=routine["tasks"][0]["id"],
    )
    assert result["success"]
    event = manager.event_list(kid, 1)[0]
    assert event["type"] == "task_done" and event["by"]
    data = (await call(type=f"{DOMAIN}/cards"))["result"]
    week = data["children"][0]["week"]
    assert week["days"][-1]["percent"] == 100
    assert week["percent"] == 14  # 1 of the 7 daily tasks this week
    assert week["routines"][0]["percent"] == 14

    # Redeeming for a child.
    assert (
        await call(type=f"{DOMAIN}/cards/redeem", child_id=kid, reward_id=reward["id"])
    )["success"]
    assert manager.balances(kid)["wallet"] == 3
    result = await call(
        type=f"{DOMAIN}/cards/redeem", child_id=kid, reward_id="missing"
    )
    assert result["error"]["code"] == "unknown_reward"

    # Knob buttons call the knob's API actions.
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("esphome", "test_knob_night_light", record)
    result = await call(
        type=f"{DOMAIN}/cards/knob",
        device_id=device.id,
        action="night_light",
        enable=True,
    )
    assert result["success"]
    assert calls[0].data == {"enable": True, "brightness": 0, "kelvin": 0}
    result = await call(type=f"{DOMAIN}/cards/knob", device_id=device.id, action="wake")
    assert result["error"]["code"] == "unavailable"


async def test_cards_look(hass: HomeAssistant, hass_ws_client) -> None:
    """The cards take the theme's look only when it is switched on."""
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:0b")},
        name="Knob",
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    async def call(**msg):
        await client.send_json_auto_id(msg)
        return await client.receive_json()

    assert (await call(type=f"{DOMAIN}/cards"))["result"]["look"] is None
    assert (await call(type=f"{DOMAIN}/settings/update", cards_themed=True))["success"]
    look = (await call(type=f"{DOMAIN}/cards"))["result"]["look"]
    # The default theme's colours, for light and dark dashboards.
    assert look["panel"]["light"]["--surface"] == "#FFFFFF"
    assert look["panel"]["dark"]["--accent"] == "#7DB2FF"
