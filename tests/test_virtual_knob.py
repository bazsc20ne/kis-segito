# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the virtual knob (the knob screen as a dashboard card)."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN


async def test_virtual_knob(hass: HomeAssistant, hass_ws_client) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:07")},
        name="Knob",
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

    kid = await manager.async_save_item("children", {"name": "Kid", "color": "#FF0000"})
    other = await manager.async_save_item("children", {"name": "Other"})
    reward = await manager.async_save_item(
        "rewards", {"name": "Treat", "cost": 2, "icon": "reward_treat"}
    )
    await manager.async_adjust(kid["id"], 5)
    await manager.async_adjust(other["id"], 5)

    # Created, listed, and offered like a physical knob.
    knob_id = (await call(type=f"{DOMAIN}/virtual/save", name="Trip"))["result"]
    assert (await call(type=f"{DOMAIN}/virtual/list"))["result"] == [
        {"id": knob_id, "name": "Trip"}
    ]
    devices = (await call(type=f"{DOMAIN}/data"))["result"]["devices"]
    assert any(d["device_id"] == knob_id and d["virtual"] for d in devices)
    assert (
        await call(type=f"{DOMAIN}/device/rename", device_id=knob_id, name="Holiday")
    )["success"]
    assert manager.virtual_knobs()[0]["name"] == "Holiday"

    # Kid is assigned to it and to the physical knob, Other to the physical
    # knob only; a child without knobs can be used everywhere.
    await call(
        type=f"{DOMAIN}/assign", child_id=kid["id"], device_ids=[knob_id, device.id]
    )
    await call(type=f"{DOMAIN}/assign", child_id=other["id"], device_id=device.id)
    free = await manager.async_save_item("children", {"name": "Free"})
    assert manager.device_children(device.id) == {kid["id"], other["id"], free["id"]}
    assert manager.device_children(knob_id) == {kid["id"], free["id"]}

    # The card gets the snapshot, without the knob's picture key.
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/virtual/subscribe", "device_id": knob_id}
    )
    assert (await client.receive_json())["success"]
    event = (await client.receive_json())["event"]
    state = event["state"]
    assert state["img"] == {"u": "", "t": ""}
    selectable = {c["id"]: c["sel"] for c in state["children"]}
    assert selectable == {kid["id"]: True, other["id"]: False, free["id"]: True}
    assert event["static_url"]

    def action(child_id: str, action_id: str) -> str:
        return json.dumps(
            {"a": "redeem", "id": action_id, "c": child_id, "r": reward["id"]}
        )

    # A purchase for the assigned child is booked once; another child's is refused.
    msg = await call(
        type=f"{DOMAIN}/virtual/action",
        device_id=knob_id,
        action=action(kid["id"], "v1"),
    )
    assert msg["result"] == {"ok": True}
    await call(
        type=f"{DOMAIN}/virtual/action",
        device_id=knob_id,
        action=action(kid["id"], "v1"),
    )
    assert manager.balances(kid["id"])["wallet"] == 3
    refused = await call(
        type=f"{DOMAIN}/virtual/action",
        device_id=knob_id,
        action=action(other["id"], "v2"),
    )
    assert refused["result"] == {"ok": False, "error": "not_selectable"}
    assert manager.balances(other["id"])["wallet"] == 5
    bad = await call(
        type=f"{DOMAIN}/virtual/action", device_id=knob_id, action="{nonsense"
    )
    assert bad["error"]["code"] == "invalid_action"

    # Several virtual knobs; removing one keeps the child's other knobs.
    second = (await call(type=f"{DOMAIN}/virtual/save", name="Tablet"))["result"]
    assert len(manager.virtual_knobs()) == 2
    assert manager.device_children(second) == {free["id"]}
    assert (await call(type=f"{DOMAIN}/virtual/delete", device_id=knob_id))[
        "success"
    ]
    assert [k["id"] for k in manager.virtual_knobs()] == [second]
    child = next(c for c in manager.children() if c["id"] == kid["id"])
    assert manager.child_devices(child) == [device.id]

    # Older data with one device_id still counts; saving keeps it as a list.
    legacy = await manager.async_save_item(
        "children", {"name": "Old", "device_id": device.id}
    )
    assert legacy["device_ids"] == [device.id] and "device_id" not in legacy
    raw = next(c for c in manager.data["children"] if c["id"] == free["id"])
    raw["device_id"] = second
    raw.pop("device_ids", None)
    assert free["id"] in manager.device_children(second)
    assert free["id"] not in manager.device_children(device.id)
