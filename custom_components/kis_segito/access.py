# SPDX-License-Identifier: AGPL-3.0-only
"""Who may change what in Little Helper: Home Assistant admins and the
non-admin users set as administrators may do everything, the users set as
editors may change content, and everyone else can only look."""

from __future__ import annotations

import functools
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized

from .const import DOMAIN

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"
ROLES_SAVED = (ROLE_ADMIN, ROLE_EDITOR)


def user_role(hass: HomeAssistant, user: Any) -> str:
    """The role of a user: admin (a Home Assistant admin, or set as Little
    Helper administrator), editor, or viewer (anyone not set)."""
    if user is None:
        return ROLE_VIEWER
    if user.is_admin:
        return ROLE_ADMIN
    roles = hass.data[DOMAIN].manager.settings.get("user_roles") or {}
    role = roles.get(user.id)
    return role if role in ROLES_SAVED else ROLE_VIEWER


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


def require_ks_admin(func: Any) -> Any:
    """Like require_admin, but also lets the users set as Little Helper
    administrators in."""

    @functools.wraps(func)
    def with_admin_check(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
    ) -> Any:
        if user_role(hass, connection.user) != ROLE_ADMIN:
            raise Unauthorized()
        return func(hass, connection, msg)

    return with_admin_check
