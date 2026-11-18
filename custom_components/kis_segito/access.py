# SPDX-License-Identifier: AGPL-3.0-only
"""Who may change what: Home Assistant admins, and the non-admin users set as
editors in the settings (the others can only look)."""

from __future__ import annotations

import functools
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized

from .const import DOMAIN

ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"


def user_role(hass: HomeAssistant, user: Any) -> str:
    """The role of a user: admin, editor or viewer (a non-admin user who is
    not set as an editor)."""
    if user is None:
        return ROLE_VIEWER
    if user.is_admin:
        return "admin"
    roles = hass.data[DOMAIN].manager.settings.get("user_roles") or {}
    return ROLE_EDITOR if roles.get(user.id) == ROLE_EDITOR else ROLE_VIEWER


def require_editor(func: Any) -> Any:
    """Like require_admin, but also lets the users set as editors in."""

    @functools.wraps(func)
    def with_editor_check(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
    ) -> Any:
        if user_role(hass, connection.user) == ROLE_VIEWER:
            raise Unauthorized()
        return func(hass, connection, msg)

    return with_editor_check
