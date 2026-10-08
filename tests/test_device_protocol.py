# SPDX-License-Identifier: AGPL-3.0-only
"""End-to-end test of the knob protocol: state push and actions."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN


async def test_state_push_and_action(hass: HomeAssistant) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome",
        data={
            "host": "192.0.2.1",
            "device_name": "test-knob",
            "noise_psk": "a2lzLXNlZ2l0by1leGFtcGxlLWtleS1ub3QtcmVhbCE=",
        },
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

    # Encrypted API: the knob gets its picture key, and there is no repair issue.
    assert snapshot["img"]["t"] == manager.device_token(device.id)
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"unencrypted_api_{device.id}")
        is None
    )

    # Unencrypted API: no picture key, and a repair issue explains why.
    hass.config_entries.async_update_entry(
        esphome_entry, data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    await link.async_push_state()
    assert states[-1]["img"] == {"u": "", "t": ""}
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"unencrypted_api_{device.id}")

    # Invalid actions are ignored: unknown fields, wrong types, too big.
    for bad in (
        {"a": "redeem", "id": "x1", "c": child["id"], "r": reward["id"], "z": 1},
        {"a": "piggy", "id": "x2", "c": child["id"], "n": "5"},
        {"a": "redeem", "id": "x3", "c": child["id"], "r": "r" * 65},
    ):
        hass.states.async_set(action_entity.entity_id, json.dumps(bad))
        await hass.async_block_till_done()
    assert manager.balances(child["id"])["wallet"] == 5

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


async def test_summary_entities(hass: HomeAssistant) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "knob-two"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:04")},
        name="Knob two",
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager

    assert hass.states.get("sensor.kis_segito").state == "idle"
    child = await manager.async_save_item("children", {"name": "Kid"})
    await manager.async_adjust(child["id"], 7)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.kis_segito_kid")
    assert state.state == "7"
    assert state.attributes["child_id"] == child["id"]
    assert hass.states.get("calendar.kis_segito") is not None


async def test_knob_image(hass: HomeAssistant, hass_client_no_auth) -> None:
    from pathlib import Path

    from PIL import Image

    from custom_components.kis_segito.knob_images import convert

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="dev", data={CONF_DEVICE_ID: "dev"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager
    token = manager.device_token("dev")

    folder = Path(hass.config.path("image", "abc123"))
    await hass.async_add_executor_job(lambda: folder.mkdir(parents=True, exist_ok=True))
    await hass.async_add_executor_job(
        lambda: Image.new("RGBA", (300, 200), (255, 0, 0, 255)).save(
            folder / "original", "PNG"
        )
    )
    raw = await hass.async_add_executor_job(convert, folder / "original", 64)
    assert raw[:4] == b"KSI1" and len(raw) == 8 + 64 * 64 * 3
    assert raw[8:10] == b"\x00\xf8"  # pure red in RGB565, little endian

    client = await hass_client_no_auth()
    url = "/api/kis_segito/knob_image/abc123"
    header = "X-Kis-Segito-Token"
    assert (await client.get(f"{url}/64", headers={header: "wrong"})).status == 403
    # The token is accepted only in the header, never in the URL.
    assert (await client.get(f"{url}/64?t={token}")).status == 403
    ok = await client.get(f"{url}/64", headers={header: token})
    assert ok.status == 200
    assert await ok.read() == raw
    assert (await client.get(f"{url}/99", headers={header: token})).status == 404

    # A rotated key replaces the old one at once.
    await manager.async_rotate_device_token("dev")
    assert (await client.get(f"{url}/64", headers={header: token})).status == 403
    new_token = manager.device_token("dev")
    assert new_token != token
    assert (await client.get(f"{url}/64", headers={header: new_token})).status == 200


async def test_knob_image_local_only(hass: HomeAssistant) -> None:
    from types import SimpleNamespace

    from custom_components.kis_segito.knob_images import _from_local_network

    def request(remote: str | None) -> SimpleNamespace:
        return SimpleNamespace(remote=remote)

    assert _from_local_network(hass, request("192.168.1.20"))
    assert _from_local_network(hass, request("127.0.0.1"))
    assert _from_local_network(hass, request("fe80::1"))
    assert not _from_local_network(hass, request("203.0.113.5"))
    assert not _from_local_network(hass, request(None))
    assert not _from_local_network(hass, request("not-an-ip"))


async def test_knob_image_limits(hass: HomeAssistant, tmp_path) -> None:
    import pytest
    from PIL import Image

    from custom_components.kis_segito import knob_images

    # Not an image, whatever the name says.
    fake = tmp_path / "fake"
    fake.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    with pytest.raises(knob_images.ImageRejected):
        knob_images.convert(fake, 64)

    # Too many pixels: refused from the header, before decoding.
    big = tmp_path / "big"
    Image.new("L", (12000, 9000)).save(big, "PNG")
    with pytest.raises(knob_images.ImageRejected):
        knob_images.convert(big, 64)

    # A large JPEG is decoded at a reduced scale; the result has no metadata.
    photo = tmp_path / "photo"
    Image.new("RGB", (4000, 3000), (0, 0, 255)).save(photo, "JPEG")
    raw = knob_images.convert(photo, 64)
    assert raw[:4] == b"KSI1" and len(raw) == 8 + 64 * 64 * 3


async def test_knob_background(hass: HomeAssistant, hass_client_no_auth) -> None:
    from custom_components.kis_segito.manager import KisSegitoError

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="dev", data={CONF_DEVICE_ID: "dev"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager
    token = manager.device_token("dev")

    # A built-in background, at the knob's screen size, without alpha.
    client = await hass_client_no_auth()
    header = {"X-Kis-Segito-Token": token}
    ok = await client.get("/api/kis_segito/knob_image/bg_3/480", headers=header)
    assert ok.status == 200
    raw = await ok.read()
    assert raw[:4] == b"KSI2" and len(raw) == 8 + 480 * 480 * 2
    assert (
        await client.get("/api/kis_segito/knob_image/bg_9/480", headers=header)
    ).status == 404

    # The general background and a child's own one reach the snapshot.
    await manager.async_update_settings({"background": "bg_2"})
    child = await manager.async_save_item(
        "children", {"name": "Kid", "background": "bg_5"}
    )
    snapshot = manager.snapshot("dev", "en")
    assert snapshot["bg"] == "bg_2"
    assert snapshot["children"][0]["bg"] == "bg_5"
    import pytest

    with pytest.raises(KisSegitoError):
        await manager.async_save_item(
            "children", {"id": child["id"], "background": "../etc"}
        )


def test_summary_refresh_runs_in_event_loop() -> None:
    from homeassistant.core import is_callback

    from custom_components.kis_segito.sensor import _Base

    # The minute timer must write the state from the event loop: a timer target
    # that is not a callback (or coroutine) runs in a worker thread.
    assert is_callback(_Base._async_tick)
