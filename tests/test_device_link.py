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
