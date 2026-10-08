# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the knob device link helpers."""

from __future__ import annotations

import json

from custom_components.kis_segito.device_link import (
    DEVICE_TRANSLATIONS_DIR,
    esphome_service_name,
    load_device_strings,
)


def test_all_languages_have_the_english_keys() -> None:
    english = json.loads((DEVICE_TRANSLATIONS_DIR / "en.json").read_text("utf-8"))
    for path in DEVICE_TRANSLATIONS_DIR.glob("*.json"):
        strings = json.loads(path.read_text("utf-8"))
        assert set(strings) <= set(english), path.name


def test_language_fallbacks() -> None:
    assert load_device_strings("hu")[0] == "hu"
    assert load_device_strings("hu-HU")[0] == "hu"
    assert load_device_strings("xx")[0] == "en"
    assert load_device_strings(None)[0] == "en"
    _language, strings = load_device_strings("hu")
    assert (
        strings["test_screen.hint"] != load_device_strings("en")[1]["test_screen.hint"]
    )


def test_service_name() -> None:
    assert esphome_service_name("kis-segito", "set_ui_strings") == (
        "kis_segito_set_ui_strings"
    )


def test_parse_action() -> None:
    from custom_components.kis_segito.device_link import parse_action

    ok = {"a": "task", "id": "0a1b2c", "c": "kid", "r": "routine", "t": "task1"}
    assert parse_action(json.dumps(ok)) == ok
    assert parse_action(json.dumps({"a": "seen", "id": "1", "c": "kid"}))
    assert parse_action(json.dumps({"a": "piggy", "id": "1", "c": "kid", "n": -3}))
    for bad in (
        "not json",
        "[1, 2]",
        json.dumps(ok | {"extra": 1}),
        json.dumps({"a": "explode", "id": "1", "c": "kid"}),
        json.dumps({"a": "piggy", "id": "1", "c": "kid", "n": True}),
        json.dumps({"a": "piggy", "id": "1", "c": "kid", "n": 0}),
        json.dumps({"a": "piggy", "id": "1", "c": "kid", "n": 10**9}),
        json.dumps({"a": "seen", "id": "1\n", "c": "kid"}),
        json.dumps({"a": "seen", "id": "1", "c": "x" * 65}),
        json.dumps({"a": "seen", "id": "1", "c": "kid", "pad": "y" * 300}),
    ):
        assert parse_action(bad) is None, bad


async def test_actions_are_rate_limited(hass) -> None:
    from custom_components.kis_segito.device_link import (
        ACTION_RATE_COUNT,
        DeviceLink,
    )

    calls: list[dict] = []

    class FakeManager:
        async def async_device_action(self, action: dict) -> dict:
            calls.append(action)
            return {"ok": True}

    link = DeviceLink(hass, "dev", manager=FakeManager())  # type: ignore[arg-type]
    for i in range(ACTION_RATE_COUNT + 5):
        await link._async_run_action(json.dumps({"a": "seen", "id": f"i{i}", "c": "k"}))
    link.async_stop()
    assert len(calls) == ACTION_RATE_COUNT
