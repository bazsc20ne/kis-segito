# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for avatars: an avatar keeps the look of the theme it was chosen
from, whatever theme is chosen later."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.kis_segito.knob_images import _theme_path
from custom_components.kis_segito.manager import KisSegitoManager
from custom_components.kis_segito.store import KisSegitoStore


@pytest.fixture
async def manager(hass: HomeAssistant) -> KisSegitoManager:
    store = KisSegitoStore(hass)
    await store.async_load()
    return KisSegitoManager(hass, store)


def _snapshot_avatar(manager: KisSegitoManager, child_id: str) -> str:
    snap = manager.snapshot("knob", "en")
    return next(c["ai"] for c in snap["children"] if c["id"] == child_id)


async def test_avatar_keeps_its_theme(manager: KisSegitoManager) -> None:
    manager.settings["theme"] = "frozen"
    kid = await manager.async_save_item("children", {"name": "Kid A", "avatar": "avatar_03"})
    # A new child's avatar takes the look shown when it is created.
    assert kid["avatar_theme"] == "frozen"
    assert _snapshot_avatar(manager, kid["id"]) == "t_frozen__avatar_03"
    # Another common theme does not change it.
    manager.settings["theme"] = "simpsons"
    assert _snapshot_avatar(manager, kid["id"]) == "t_frozen__avatar_03"
    assert manager.avatar_url(kid).startswith("/kis_segito_static/themes/frozen/icons/avatar_03.png")
    # Chosen from the built-in look.
    kid = await manager.async_save_item(
        "children", {"id": kid["id"], "avatar": "avatar_05", "avatar_theme": ""}
    )
    assert _snapshot_avatar(manager, kid["id"]) == "t_kis_segito__avatar_05"
    assert manager.avatar_url(kid) == "/kis_segito_static/icons/avatar_05.png"
    # An uploaded photo wins.
    kid = await manager.async_save_item(
        "children", {"id": kid["id"], "avatar_image": "abc123"}
    )
    assert _snapshot_avatar(manager, kid["id"]) == "abc123"


async def test_second_avatar_set(manager: KisSegitoManager) -> None:
    kid = await manager.async_save_item(
        "children", {"name": "Kid A", "avatar": "avatar_17", "avatar_theme": "pooh"}
    )
    assert _snapshot_avatar(manager, kid["id"]) == "t_pooh__avatar_17"
    assert _theme_path("t_pooh__avatar_17", 180) is not None
    # A theme without that avatar (or a theme that is gone): the placeholder.
    kid = await manager.async_save_item(
        "children", {"id": kid["id"], "avatar_theme": "cars"}
    )
    assert _snapshot_avatar(manager, kid["id"]) == "t_kis_segito__avatar_00"
    kid = await manager.async_save_item(
        "children", {"id": kid["id"], "avatar": "avatar_02", "avatar_theme": "gone"}
    )
    assert _snapshot_avatar(manager, kid["id"]) == "t_kis_segito__avatar_02"


async def test_older_children_keep_their_look(manager: KisSegitoManager) -> None:
    manager.settings["theme"] = "cars"
    manager.data["children"] = [
        {"id": "a", "name": "Kid A", "avatar": "avatar_01", "active": True},
        {"id": "b", "name": "Kid B", "avatar": "avatar_02", "theme": "pooh", "active": True},
    ]
    await manager.async_fix_avatar_themes()
    assert [c["avatar_theme"] for c in manager.data["children"]] == ["cars", "pooh"]


def test_built_in_avatar_for_the_knob() -> None:
    assert _theme_path("t_kis_segito__avatar_04", 180).name == "avatar_04.png"
    assert _theme_path("t_kis_segito__avatar_99", 180) is None


async def test_backgrounds_of_any_theme(manager: KisSegitoManager) -> None:
    """A theme's own background follows the theme; another theme's stays
    (#58)."""
    manager.settings["theme"] = "frozen"
    await manager.async_set_background("bg_4")
    assert manager.snapshot("knob", "en")["bg"] == "t_frozen__bg_4"
    manager.settings["theme"] = "cars"
    assert manager.snapshot("knob", "en")["bg"] == "t_cars__bg_4"
    # Another theme's background stays when the theme changes.
    await manager.async_set_background("t_pooh__bg_2")
    manager.settings["theme"] = "simpsons"
    assert manager.snapshot("knob", "en")["bg"] == "t_pooh__bg_2"
    assert manager.background_url("t_pooh__bg_2").startswith(
        "/kis_segito_static/themes/pooh/backgrounds/bg_2.jpg"
    )
    # The built-in look's background, and a theme that is gone.
    await manager.async_set_background("t_kis_segito__bg_6", device_id="knob")
    assert manager.snapshot("knob", "en")["bg"] == "bg_6"
    assert manager.background_url("t_kis_segito__bg_6") == "/kis_segito_static/backgrounds/bg_6.jpg"
    await manager.async_set_background("t_gone__bg_1", device_id="knob")
    assert manager.snapshot("knob", "en")["bg"] == "t_simpsons__bg_1"


async def test_built_in_background_order(manager: KisSegitoManager) -> None:
    """The built-in backgrounds were reordered: a knob with the built-in look
    keeps its picture; a theme's own order is unchanged."""
    manager.settings.pop("background_order", None)
    manager.settings["background"] = "bg_1"
    manager.data["devices"]["knob"] = {"background": "bg_5"}
    await manager.async_fix_background_order()
    assert manager.settings["background"] == "bg_4"
    assert manager.data["devices"]["knob"]["background"] == "bg_3"
    await manager.async_fix_background_order()  # only once
    assert manager.settings["background"] == "bg_4"

    manager.settings.pop("background_order", None)
    manager.settings["theme"] = "frozen"
    manager.settings["background"] = "bg_1"
    await manager.async_fix_background_order()
    assert manager.settings["background"] == "bg_1"
