# SPDX-License-Identifier: AGPL-3.0-only
"""Constants for the Kis Segito integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "kis_segito"

CONF_DEVICE_ID: Final = "device_id"

# Sidebar panel
PANEL_URL_PATH: Final = "kis-segito"
PANEL_TITLE: Final = "Kis Segítő"
PANEL_ICON: Final = "mdi:hand-heart"
PANEL_ELEMENT: Final = "kis-segito-panel"
STATIC_URL: Final = "/kis_segito_static"

# Persistent storage
STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1

ESPHOME_DOMAIN: Final = "esphome"

# ESPHome API action exposed by the knob firmware (see esphome/kis-segito.yaml).
ESPHOME_ACTION_SET_UI_STRINGS: Final = "set_ui_strings"

DEFAULT_LANGUAGE: Final = "en"

# Language setting: "auto" follows the Home Assistant language.
LANGUAGE_AUTO: Final = "auto"
