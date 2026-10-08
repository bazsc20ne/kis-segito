# SPDX-License-Identifier: AGPL-3.0-only
"""Icon ids that share another icon's artwork.

Some icons are the same picture under two ids (for example a task and a
routine). The artwork is stored once, under one id; the other id is an alias
(frontend/icons/aliases.json). Routines, tasks and checkpoints may use either
id; the knob and the panel get the stored one.
"""

from __future__ import annotations

import json
from pathlib import Path

ALIASES_FILE = Path(__file__).parent / "frontend" / "icons" / "aliases.json"

try:
    ICON_ALIASES: dict[str, str] = json.loads(ALIASES_FILE.read_text("utf-8"))
except (OSError, ValueError):
    ICON_ALIASES = {}


def stored_icon(icon: str) -> str:
    """The id under which an icon's artwork is stored."""
    return ICON_ALIASES.get(icon, icon)
