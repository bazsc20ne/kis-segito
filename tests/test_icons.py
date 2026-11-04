# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for own (uploaded) icons and switching icons off."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant
from PIL import Image
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN


async def test_own_icons(hass: HomeAssistant, hass_ws_client, hass_client_no_auth) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="dev", data={CONF_DEVICE_ID: "dev"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager
    ws = await hass_ws_client(hass)

    async def call(**msg):
        await ws.send_json_auto_id(msg)
        return await ws.receive_json()

    for image in ("pic1", "pic2"):
        folder = Path(hass.config.path("image", image))
        await hass.async_add_executor_job(lambda f=folder: f.mkdir(parents=True, exist_ok=True))
        await hass.async_add_executor_job(
            lambda f=folder: Image.new("RGBA", (100, 100), (0, 0, 255, 255)).save(f / "original", "PNG")
        )

    key = (await call(type=f"{DOMAIN}/icons/add", image_id="pic1"))["result"]
    assert key.startswith("own_")
    routine = await manager.async_save_item(
        "routines",
        {
            "name": "Morning",
            "icon": key,
            "start": "07:00",
            "end": "08:00",
            "checkpoints": [{"name": "Ready", "time": "07:50", "icon": key}],
            "tasks": [{"icon": key, "label": "Shoes"}],
        },
    )
    reward = await manager.async_save_item("rewards", {"name": "Film", "cost": 1, "icon": key})

    # The knob gets it like any other icon, at the sizes it shows icons.
    client = await hass_client_no_auth()
    token = manager.device_token("dev")
    url = f"/api/kis_segito/knob_image/{key}"
    ok = await client.get(f"{url}/40", headers={"X-Kis-Segito-Token": token})
    assert ok.status == 200 and (await ok.read())[:4] == b"KSI1"
    assert (
        await client.get("/api/kis_segito/knob_image/own_unknown/40", headers={"X-Kis-Segito-Token": token})
    ).status == 404

    # Replaced: the same key shows the new picture.
    assert (await call(type=f"{DOMAIN}/icons/replace", key=key, image_id="pic2"))["success"]
    assert manager.own_icon(key)["image"] == "pic2"

    # Switched off (own and built-in): not offered, but kept where used.
    await call(type=f"{DOMAIN}/icons/active", key=key, active=False)
    await call(type=f"{DOMAIN}/icons/active", key="task_shoes", active=False)
    data = (await call(type=f"{DOMAIN}/data"))["result"]
    assert data["own_icons"][0]["active"] is False
    assert data["disabled_icons"] == ["task_shoes"]
    await call(type=f"{DOMAIN}/icons/active", key="task_shoes", active=True)
    assert manager.icon_settings["disabled"] == []

    # Where it is used, then deleted: built-in icons take its place.
    usage = (await call(type=f"{DOMAIN}/icons/usage", key=key))["result"]
    assert sorted(u["kind"] for u in usage) == ["checkpoint", "reward", "routine", "task"]
    assert (await call(type=f"{DOMAIN}/icons/delete", key=key))["result"] == 4
    saved = manager.routine(routine["id"])
    assert saved["icon"] == "routine_generic"
    assert saved["tasks"][0]["icon"] == "task_clothes"
    assert saved["checkpoints"][0]["icon"] == "checkpoint_flag"
    assert manager.reward(reward["id"])["icon"] == "fn_rewards"
    assert manager.own_icon(key) is None
