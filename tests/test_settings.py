# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the language setting."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
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


async def test_panel_data_flow(hass: HomeAssistant, hass_ws_client) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:02")},
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

    child = (
        await call(
            type=f"{DOMAIN}/save",
            collection="children",
            item={"name": "Kid", "color": "#6CB8FF", "avatar": "test_avatar_1"},
        )
    )["result"]
    assert (
        await call(
            type=f"{DOMAIN}/device/options",
            device_id=device.id,
            children=[child["id"]],
            hide_locked=True,
        )
    )["success"]
    assert (await call(type=f"{DOMAIN}/tokens/adjust", child_id=child["id"], amount=5))[
        "success"
    ]
    refused = await call(
        type=f"{DOMAIN}/tokens/adjust", child_id=child["id"], amount=-9
    )
    assert refused["error"]["code"] == "insufficient_balance"

    data = (await call(type=f"{DOMAIN}/data"))["result"]
    assert data["children"][0]["balances"]["wallet"] == 5
    assert data["devices"][0]["children"] == [data["children"][0]["id"]]
    assert data["devices"][0]["hide_locked"] is True
    assert data["devices"][0]["device_id"] == device.id
    assert "task_toothbrush" in data["icons"]

    history = (await call(type=f"{DOMAIN}/history"))["result"]
    assert history[0]["effective_lines"][0]["amount"] == 5

    settings = (
        await call(
            type=f"{DOMAIN}/settings/update", streak_target=5, animation_mode="reduced"
        )
    )["result"]
    assert settings["streak_target"] == 5
    assert settings["animation_mode"] == "reduced"


async def test_sensor_settings_and_inputs(hass: HomeAssistant, hass_ws_client) -> None:
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:05")},
        name="Knob",
    )
    own = er.async_get(hass).async_get_or_create(
        "binary_sensor",
        "esphome",
        "knob-presence",
        device_id=device.id,
        config_entry=esphome_entry,
    )
    lux = er.async_get(hass).async_get_or_create(
        "sensor",
        "esphome",
        "knob-illuminance",
        device_id=device.id,
        config_entry=esphome_entry,
        original_name="Illuminance",
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

    # Defaults are returned; switches and numbers are validated and stored.
    settings = (await call(type=f"{DOMAIN}/settings"))["result"]
    assert settings["screen"]["night_light"] is True
    assert settings["screen"]["near_cm"] == 80
    result = await call(
        type=f"{DOMAIN}/settings/update",
        screen={"night_light": False, "night_kelvin": 2200, "night_lux": 3.5},
    )
    assert result["success"]
    assert result["result"]["screen"]["night_light"] is False
    assert result["result"]["screen"]["night_kelvin"] == 2200
    assert result["result"]["screen"]["dim_after"] == 60
    bad = await call(type=f"{DOMAIN}/settings/update", screen={"night_kelvin": 900})
    assert not bad["success"]
    result = await call(type=f"{DOMAIN}/settings/update", screen={"light_factor": 3})
    assert result["result"]["screen"]["light_factor"] == 3.0
    bad = await call(type=f"{DOMAIN}/settings/update", screen={"light_factor": 0})
    assert not bad["success"]

    # Forwarded inputs; the knob's own entity is refused.
    assert (
        await call(
            type=f"{DOMAIN}/device/inputs",
            device_id=device.id,
            inputs={"presence": "binary_sensor.hall_motion"},
        )
    )["success"]
    refused = await call(
        type=f"{DOMAIN}/device/inputs",
        device_id=device.id,
        inputs={"presence": own.entity_id},
    )
    assert refused["error"]["code"] == "own_entity"
    devices = (await call(type=f"{DOMAIN}/data"))["result"]["devices"]
    assert devices[0]["inputs"] == {"presence": "binary_sensor.hall_motion"}
    assert devices[0]["illuminance_entity"] == lux.entity_id


async def test_firmware_version_and_release_readiness(hass: HomeAssistant) -> None:
    """The knob's own version (not ESPHome's), and whether it can take a
    release update: on, off, a sensor turned off, or no state."""
    from custom_components.kis_segito.websocket_api import _firmware

    esphome_entry = MockConfigEntry(domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"})
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:09")},
        name="Knob",
        sw_version="0.9.17 (ESPHome 2026.10.2)",
    )
    registry = er.async_get(hass)
    builder = registry.async_get_or_create(
        "update", "esphome", "knob-builder", device_id=device.id, config_entry=esphome_entry, original_name="Firmware"
    )
    hass.states.async_set(builder.entity_id, "off", {"installed_version": "2026.10.2"})
    release = registry.async_get_or_create(
        "update", "esphome", "knob-release", device_id=device.id, config_entry=esphome_entry, original_name="Release firmware"
    )
    hass.states.async_set(release.entity_id, "on", {"installed_version": "0.9.17", "latest_version": "0.9.18"})
    assert _firmware(hass, device.id)["ready"] is None  # no sensor: an older firmware
    ready = registry.async_get_or_create(
        "binary_sensor",
        "esphome",
        "knob-ready",
        device_id=device.id,
        config_entry=esphome_entry,
        original_name="Ready for release updates",
    )
    fw = _firmware(hass, device.id)
    assert fw["version"] == "0.9.17" and fw["latest"] == "0.9.18"
    assert fw["entity_id"] == release.entity_id
    assert fw["ready"] == "unknown"
    hass.states.async_set(ready.entity_id, "on")
    assert _firmware(hass, device.id)["ready"] is True
    hass.states.async_set(ready.entity_id, "off")
    assert _firmware(hass, device.id)["ready"] is False
    registry.async_update_entity(ready.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    assert _firmware(hass, device.id)["ready"] == "disabled"
