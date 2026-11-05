# SPDX-License-Identifier: AGPL-3.0-only
"""WebSocket commands for the dashboard cards (adult view)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .assist import child_status
from .const import CONF_DEVICE_ID, DOMAIN, STATIC_URL
from .logic import applies_to
from .manager import KisSegitoError, KisSegitoManager
from .themes import theme_assets

# The knob's own entities a card shows: (domain, object id ending).
KNOB_ENTITIES = {
    "brightness": ("sensor", "screen_brightness"),
    "illuminance": ("sensor", "illuminance"),
    "presence": ("binary_sensor", "presence"),
    "night_light": ("binary_sensor", "night_light"),
    "screensaver": ("binary_sensor", "screensaver"),
}
KNOB_ACTIONS = ("wake", "screensaver", "night_light")


def _manager(hass: HomeAssistant) -> KisSegitoManager:
    return hass.data[DOMAIN].manager


def _who(connection: websocket_api.ActiveConnection) -> str:
    return (connection.user.name if connection.user else None) or "parent"


def _today(manager: KisSegitoManager, child_id: str) -> list[dict[str, Any]]:
    """Today's routines of a child with their tasks and checkpoints."""
    day = manager.today()
    result = []
    for routine in manager.routines_on_day(day):
        if not applies_to(routine, child_id):
            continue
        progress = manager.progress(day, routine["id"], child_id)
        tasks = [
            {
                "id": t["id"],
                "label": t.get("label", ""),
                "icon": t.get("icon", "task_clothes"),
                "done": t["id"] in progress["tasks"],
            }
            for t in routine.get("tasks", [])
        ]
        result.append(
            {
                "id": routine["id"],
                "name": routine.get("name", ""),
                "icon": routine.get("icon", "routine_generic"),
                "start": routine.get("start"),
                "end": routine.get("end"),
                "tasks": tasks,
                "done": sum(1 for t in tasks if t["done"]),
                "checkpoints": [
                    {
                        "name": c.get("name", ""),
                        "time": c.get("time"),
                        "reached": c["id"] in progress["checkpoints"],
                    }
                    for c in routine.get("checkpoints", [])
                    if applies_to(c, child_id)
                ],
            }
        )
    return result


def _knob_entity(
    hass: HomeAssistant, device_id: str, domain: str, key: str
) -> str | None:
    for entry in er.async_entries_for_device(er.async_get(hass), device_id):
        if entry.domain == domain and entry.entity_id.endswith(f"_{key}"):
            return entry.entity_id
    return None


def _knobs(hass: HomeAssistant) -> list[dict[str, Any]]:
    """The physical knobs with the entities the knob card shows."""
    registry = dr.async_get(hass)
    result = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        device_id = entry.data[CONF_DEVICE_ID]
        device = registry.async_get(device_id)
        result.append(
            {
                "device_id": device_id,
                "name": (device.name_by_user or device.name) if device else entry.title,
                "sw_version": device.sw_version if device else None,
                "entities": {
                    key: _knob_entity(hass, device_id, domain, suffix)
                    for key, (domain, suffix) in KNOB_ENTITIES.items()
                },
            }
        )
    return result


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/cards"})
@callback
def ws_cards(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Everything the dashboard cards show."""
    manager = _manager(hass)
    today = manager.today()
    children = []
    for child in manager.children(active_only=True):
        child_id = child["id"]
        children.append(
            {
                "id": child_id,
                "name": child.get("name", ""),
                "color": child.get("color"),
                "avatar": child.get("avatar"),
                "avatar_image": child.get("avatar_image"),
                "status": child_status(manager, child_id),
                "today": _today(manager, child_id),
                "week": manager.week_stats(child_id, today),
            }
        )
    rewards = [
        {
            "id": r["id"],
            "name": r.get("name", ""),
            "icon": r.get("icon", "fn_rewards"),
            "cost": int(r.get("cost", 0)),
            "kind": r.get("kind"),
            "needs_confirmation": bool(r.get("needs_confirmation")),
        }
        for r in sorted(manager.data["rewards"], key=lambda r: r.get("sort_order", 0))
        if r.get("active", True)
    ]
    connection.send_result(
        msg["id"],
        {
            "version": hass.data[DOMAIN].version,
            "static_url": STATIC_URL,
            "date": today.isoformat(),
            "children": children,
            "rewards": rewards,
            "approvals": list(reversed(manager.pending_approvals())),
            "knobs": _knobs(hass),
            "own_icons": manager.icon_settings["own"],
            # Pictures of the chosen theme ("": the built-in ones).
            "theme": theme_assets(manager.theme),
        },
    )


async def _run(
    connection: websocket_api.ActiveConnection, msg_id: int, coro: Any
) -> None:
    try:
        result = await coro
    except KisSegitoError as err:
        connection.send_error(msg_id, err.code, str(err))
        return
    connection.send_result(msg_id, result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/cards/task",
        vol.Required("child_id"): str,
        vol.Required("routine_id"): str,
        vol.Required("task_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_card_task(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """A parent ticks a child's task (logged with the parent's name)."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_complete_task(
            msg["child_id"],
            msg["routine_id"],
            msg["task_id"],
            source="parent",
            by=_who(connection),
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/cards/redeem",
        vol.Required("child_id"): str,
        vol.Required("reward_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_card_redeem(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """A parent redeems a reward for a child."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_redeem(
            msg["child_id"], msg["reward_id"], source="parent", creator=_who(connection)
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/cards/knob",
        vol.Required("device_id"): str,
        vol.Required("action"): vol.In(KNOB_ACTIONS),
        vol.Optional("enable", default=True): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_card_knob(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Wake a knob, or switch its screensaver or night light."""
    link = next(
        (
            entry.runtime_data
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if entry.data[CONF_DEVICE_ID] == msg["device_id"]
        ),
        None,
    )
    service = link.esphome_action(msg["action"]) if link else None
    if service is None:
        connection.send_error(msg["id"], "unavailable", "The knob is not available")
        return
    data: dict[str, Any] = {}
    if msg["action"] != "wake":
        data["enable"] = msg["enable"]
    if msg["action"] == "night_light":
        data |= {"brightness": 0, "kelvin": 0}
    await hass.services.async_call("esphome", service, data, blocking=True)
    connection.send_result(msg["id"])


@callback
def async_register_card_commands(hass: HomeAssistant) -> None:
    """Register the cards' WebSocket commands."""
    for command in (ws_cards, ws_card_task, ws_card_redeem, ws_card_knob):
        websocket_api.async_register_command(hass, command)
