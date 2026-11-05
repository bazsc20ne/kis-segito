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

from custom_components.kis_segito import themes
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
    themes.reload()
    yield root
    themes.reload()


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
    themes.reload()
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


async def test_own_theme(
    hass: HomeAssistant,
    hass_ws_client,
    hass_client,
    hass_client_no_auth,
    theme_dir: Path,
) -> None:
    import io
    import json
    import zipfile

    esphome_entry = MockConfigEntry(
        domain="esphome", data={"host": "192.0.2.1", "device_name": "test-knob"}
    )
    esphome_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:0a")},
        name="Knob",
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=device.id, data={CONF_DEVICE_ID: device.id}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN].manager
    http = await hass_client()
    ws = await hass_ws_client(hass)

    async def call(**msg):
        await ws.send_json_auto_id(msg)
        return await ws.receive_json()

    # The template: theme.json, the guide and a picture for every source.
    response = await http.get("/api/kis_segito/theme/template")
    assert response.status == 200
    template = zipfile.ZipFile(io.BytesIO(await response.read()))
    names = template.namelist()
    assert "theme.json" in names and "README.txt" in names
    assert "pictures/task_shoes.png" in names and "pictures/bg_1.jpg" in names

    # A theme of a few pictures (the rest stays built-in).
    def package(meta: dict, pictures: dict[str, tuple[int, int]]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("my theme/theme.json", json.dumps(meta))
            for name, size in pictures.items():
                img = io.BytesIO()
                Image.new("RGBA", size, (0, 120, 200, 255)).save(img, "PNG")
                zf.writestr(f"my theme/pictures/{name}", img.getvalue())
            zf.writestr("my theme/notes.txt", "ignored")
        return buf.getvalue()

    async def upload(data: bytes):
        from aiohttp import FormData

        form = FormData()
        form.add_field("file", data, filename="theme.zip")
        return await http.post("/api/kis_segito/theme/upload", data=form)

    data = package(
        {"name": {"en": "Ocean Fun", "hu": "Óceán"}, "knob": {"bg": "#003366"}},
        {
            "task_shoes.png": (512, 512),
            "bg_2.png": (600, 600),
            "brand_logo.png": (300, 100),
        },
    )
    response = await upload(data)
    assert response.status == 200, await response.text()
    result = await response.json()
    assert result["id"] == "my_ocean_fun"
    assert 0 < result["count"] < result["total"]

    listed = (await call(type=f"{DOMAIN}/data"))["result"]["themes"]
    own = next(t for t in listed if t["id"] == "my_ocean_fun")
    assert (
        own["own"]
        and own["active"]
        and own["base"] == "/kis_segito_own_themes/my_ocean_fun"
    )

    assert (await call(type=f"{DOMAIN}/settings/update", theme="my_ocean_fun"))[
        "success"
    ]
    state = manager.snapshot(device.id, "en")
    assert state["th"] == "my_ocean_fun" and state["tc"] == {"bg": "#003366"}
    assert state["bg"] == "t_my_ocean_fun__bg_2"  # the theme has this background
    data_theme = (await call(type=f"{DOMAIN}/data"))["result"]["theme"]
    assert "icons/task_shoes.png" in data_theme["has"]
    assert "icons/task_socks.png" not in data_theme["has"]

    # The knob gets the theme's pictures; a missing one is the built-in one.
    header = {"X-Kis-Segito-Token": manager.device_token(device.id)}
    plain = await hass_client_no_auth()
    ok = await plain.get(
        "/api/kis_segito/knob_image/t_my_ocean_fun__task_shoes/150", headers=header
    )
    assert ok.status == 200
    missing = await plain.get(
        "/api/kis_segito/knob_image/t_my_ocean_fun__task_socks/150", headers=header
    )
    assert missing.status == 404
    # The panel serves the pictures from the configuration folder.
    assert (
        await http.get("/kis_segito_own_themes/my_ocean_fun/icons/task_shoes.png")
    ).status == 200

    # Uploading it again updates it; the knobs restart for the new pictures.
    seq = manager.settings.get("background_seq", 0)
    assert (await upload(data)).status == 200
    assert manager.settings["background_seq"] == seq + 1

    # Switched off: not the chosen theme any more.
    assert (
        await call(
            type=f"{DOMAIN}/themes/active", theme_id="my_ocean_fun", active=False
        )
    )["success"]
    assert manager.settings["theme"] == "kis_segito"
    assert manager.settings["themes_off"] == ["my_ocean_fun"]
    # Only own themes can be deleted.
    result = await call(type=f"{DOMAIN}/themes/delete", theme_id="kis_segito")
    assert result["error"]["code"] == "not_own_theme"
    assert (await call(type=f"{DOMAIN}/themes/delete", theme_id="my_ocean_fun"))[
        "success"
    ]
    assert "my_ocean_fun" not in themes.load_themes()
    assert manager.settings["themes_off"] == []

    # Packages that cannot be installed.
    for bad, code in (
        (b"not a zip", "not_a_zip"),
        (package({"name": {}}, {}), "no_name"),
        (
            package({"name": {"en": "Big"}}, {"task_shoes.png": (5000, 10)}),
            "picture_too_large",
        ),
    ):
        response = await upload(bad)
        assert response.status == 400
        assert (await response.json())["code"] == code


async def test_child_theme(hass: HomeAssistant, theme_dir: Path) -> None:
    """A child's own theme goes to the knob with its colours; the background
    stays the knob's."""
    from custom_components.kis_segito.manager import KisSegitoManager
    from custom_components.kis_segito.store import KisSegitoStore

    _write_theme(theme_dir / "test")
    store = KisSegitoStore(hass)
    await store.async_load()
    manager = KisSegitoManager(hass, store)
    a = await manager.async_save_item("children", {"name": "A", "theme": "test"})
    b = await manager.async_save_item("children", {"name": "B", "theme": "gone"})
    await manager.async_save_item("children", {"name": "C"})
    state = manager.snapshot("dev", "en")
    themes_by_child = {c["id"]: c["th"] for c in state["children"]}
    assert themes_by_child[a["id"]] == "test"
    assert themes_by_child[b["id"]] == ""  # a theme that is not there
    assert state["tcs"] == {"test": {"bg": "#102030"}}
    assert state["th"] == "" and state["bg"] == "bg_2"
    # The child's theme is the common one: nothing extra.
    await manager.async_update_settings({"theme": "test"})
    state = manager.snapshot("dev", "en")
    assert all(c["th"] == "" for c in state["children"]) and state["tcs"] == {}
    # A switched-off theme is not used for a child either.
    await manager.async_update_settings({"theme": "kis_segito", "themes_off": ["test"]})
    assert manager.snapshot("dev", "en")["tcs"] == {}
