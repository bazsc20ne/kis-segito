# SPDX-License-Identifier: AGPL-3.0-only
"""The pictures a knob stores for a theme, and whether they fit its store."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN
from custom_components.kis_segito.knob_pictures import knob_store, theme_keys


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


def test_theme_keys_big_task_pictures_first() -> None:
    keys = theme_keys("frozen", {"task_breakfast", "routine_morning", "reward_treat"}, "hu")
    names = [k for k, _b in keys]
    assert names[0] == "task_breakfast_150"
    assert "task_breakfast_40" in names
    assert "fn_rewards_160" in names
    # The brand mark only in the knob's language.
    assert any(n.startswith("brand_mark_2") for n in names)
    assert not any(n.startswith("brand_mark_en") for n in names)
    assert not any(n.startswith("avatar_") for n in names)
    english = [k for k, _b in theme_keys("frozen", set(), "en")]
    assert any(n.startswith("brand_mark_en") for n in english)


async def _setup(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="dev", data={CONF_DEVICE_ID: "dev"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN].manager


async def test_store_fits_one_theme_not_four(hass: HomeAssistant) -> None:
    manager = await _setup(hass)
    tasks = [{"icon": f"task_{n}", "label": n} for n in ("breakfast", "clothes", "coat", "cookie", "hair", "pajamas")]
    await manager.async_save_item(
        "routines", {"name": "Morning", "start": "07:00", "end": "08:00", "tasks": tasks}
    )
    manager.settings["theme"] = "frozen"
    for name in ("Kid A", "Kid B", "Kid C", "Kid D"):
        await manager.async_save_item("children", {"name": name})
    one = await hass.async_add_executor_job(knob_store, manager, "dev", "hu")
    assert one["themes"] == ["frozen"] and one["fits"], one
    for child, theme in zip(manager.children(), ("cars", "planes", "toy_story", "pooh")):
        await manager.async_save_item("children", {"id": child["id"], "theme": theme})
    four = await hass.async_add_executor_job(knob_store, manager, "dev", "hu")
    assert len(four["themes"]) == 5 and not four["fits"], four


async def test_theme_set_view(hass: HomeAssistant, hass_client_no_auth) -> None:
    manager = await _setup(hass)
    token = manager.device_token("dev")
    client = await hass_client_no_auth()
    url = "/api/kis_segito/knob_theme_set/frozen?lang=en"
    assert (await client.get(url, headers={"X-Kis-Segito-Token": "wrong"})).status == 403
    response = await client.get(url, headers={"X-Kis-Segito-Token": token})
    assert response.status == 200
    keys = (await response.json())["keys"]
    assert "fn_rewards_160" in keys
