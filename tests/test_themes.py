# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for themes: discovery, the setting, the knob state and pictures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from PIL import Image
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kis_segito import knob_images, themes
from custom_components.kis_segito.const import CONF_DEVICE_ID, DOMAIN


def _write_theme(folder: Path, skip: str | None = None) -> None:
    """A complete theme (every picture a plain colour), less ``skip``."""
    folder.mkdir(parents=True)
    (folder / "theme.json").write_text(
        '{"name": {"en": "Test", "hu": "Teszt"},'
        ' "panel": {"light": {"--bg": "#000000", "color": "red"}},'
        ' "knob": {"bg": "#102030", "pill": "nope"}}',
        "utf-8",
    )
    for name in themes.required_files():
        if name == skip:
            continue
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith(".jpg"):
            Image.new("RGB", (64, 64), (10, 20, 30)).save(path)
        elif name.endswith(".webp"):
            Image.new("RGBA", (40, 20), (200, 0, 0, 255)).save(path)
        else:
            size = int(name.rsplit("_", 1)[1][:-4]) if name.startswith("knob/") else 96
            Image.new("RGBA", (size, size), (200, 100, 0, 255)).save(path)


@pytest.fixture
def theme_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "themes"
    root.mkdir()
    shutil.copy(themes.THEMES_DIR / "knob_pictures.json", root)
    shutil.copytree(themes.THEMES_DIR / "kis_segito", root / "kis_segito")
    monkeypatch.setattr(themes, "THEMES_DIR", root)
    monkeypatch.setattr(knob_images, "THEMES_DIR", root)
    themes.load_themes.cache_clear()
    yield root
    themes.load_themes.cache_clear()


def test_discovery(theme_dir: Path) -> None:
    _write_theme(theme_dir / "test")
    _write_theme(theme_dir / "partial", skip="knob/fn_rewards_160.png")
    found = themes.load_themes()
    # The default first; an incomplete theme is not offered.
    assert list(found) == ["kis_segito", "test"]
    assert themes.missing_files("partial") == ["knob/fn_rewards_160.png"]
    test = found["test"]
    assert test["name"] == {"en": "Test", "hu": "Teszt"}
    # Only CSS variables and valid colours are taken.
    assert test["panel"]["light"] == {"--bg": "#000000"}
    assert test["knob"] == {"bg": "#102030"}
    assert themes.theme("unknown")["id"] == "kis_segito"


def test_shipped_default_theme() -> None:
    themes.load_themes.cache_clear()
    default = themes.load_themes()["kis_segito"]
    assert default["name"] == {"en": "Little Helper", "hu": "Kis Segítő"}
    assert set(default["knob"]) == set(themes.KNOB_COLORS)


async def test_theme_setting(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth, theme_dir: Path
) -> None:
    _write_theme(theme_dir / "test")
    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:09")},
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

    data = (await call(type=f"{DOMAIN}/data"))["result"]
    assert [t["id"] for t in data["themes"]] == ["kis_segito", "test"]
    assert data["theme"]["id"] == "kis_segito"
    state = manager.snapshot(device.id, "en")
    assert state["th"] == "" and state["bg"] == "bg_2"

    result = await call(type=f"{DOMAIN}/settings/update", theme="nope")
    assert result["error"]["code"] == "invalid_theme"
    assert (await call(type=f"{DOMAIN}/settings/update", theme="test"))["success"]
    data = (await call(type=f"{DOMAIN}/data"))["result"]
    assert data["theme"]["id"] == "test"
    state = manager.snapshot(device.id, "en")
    assert state["th"] == "test"
    assert state["tc"] == {"bg": "#102030"}
    # Background presets in the theme's style; uploaded pictures stay.
    assert state["bg"] == "t_test__bg_2"
    await manager.async_update_settings({"background": "abc123"})
    assert manager.snapshot(device.id, "en")["bg"] == "abc123"

    # The knob downloads the theme's pictures.
    header = {"X-Kis-Segito-Token": manager.device_token(device.id)}
    http = await hass_client_no_auth()
    icon = await http.get(
        "/api/kis_segito/knob_image/t_test__task_shoes/150", headers=header
    )
    raw = await icon.read()
    assert raw[:4] == b"KSI1" and raw[4:6] == (150).to_bytes(2, "little")
    # At the size of a whole screen, only a background is stored without alpha.
    mark = await http.get(
        "/api/kis_segito/knob_image/t_test__brand_mark/240", headers=header
    )
    assert (await mark.read())[:4] == b"KSI1"
    bg = await http.get("/api/kis_segito/knob_image/t_test__bg_2/360", headers=header)
    raw = await bg.read()
    assert raw[:4] == b"KSI2" and len(raw) == 8 + 360 * 360 * 2
    for url in (
        "/api/kis_segito/knob_image/t_partial__task_shoes/150",
        "/api/kis_segito/knob_image/t_kis_segito__task_shoes/150",
        "/api/kis_segito/knob_image/t_test__nothing/150",
    ):
        assert (await http.get(url, headers=header)).status == 404
