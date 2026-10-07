# SPDX-License-Identifier: AGPL-3.0-only
"""WebSocket commands used by the Kis Segito panel."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_DEVICE_ID, DOMAIN, LANGUAGE_AUTO
from .device_link import available_languages
from .ledger import PIGGY, WALLET
from .manager import COLLECTIONS, KisSegitoError, KisSegitoManager
from .notify import EVENT_TYPES
from .panel import FRONTEND_DIR, panel_language_names


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the panel's WebSocket commands."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_settings)
    websocket_api.async_register_command(hass, ws_settings_update)
    for command in (
        ws_data,
        ws_subscribe,
        ws_save,
        ws_delete,
        ws_reorder,
        ws_assign,
        ws_history,
        ws_adjust,
        ws_reverse,
        ws_correct,
        ws_today,
        ws_override,
        ws_week,
        ws_notifications,
        ws_export,
    ):
        websocket_api.async_register_command(hass, command)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info"})
@callback
def ws_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return basic information about the integration."""
    data = hass.data[DOMAIN]
    connection.send_result(
        msg["id"],
        {
            "version": data.version,
            "devices": [
                {"entry_id": entry.entry_id, "device_id": entry.data[CONF_DEVICE_ID]}
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            ],
        },
    )


async def _settings(hass: HomeAssistant) -> dict[str, Any]:
    data = hass.data[DOMAIN]
    codes = await hass.async_add_executor_job(available_languages)
    names = await hass.async_add_executor_job(panel_language_names)
    return {
        **data.store.settings,
        "language": data.store.language,
        "languages": [{"code": code, "name": names.get(code, code)} for code in codes],
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/settings"})
@websocket_api.async_response
async def ws_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the settings and the languages that can be chosen."""
    connection.send_result(msg["id"], await _settings(hass))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/settings/update",
        vol.Optional("language"): str,
        vol.Optional("animation_mode"): vol.In(["full", "reduced", "off"]),
        vol.Optional("inactivity_s"): vol.All(int, vol.Range(min=10, max=3600)),
        vol.Optional("streak_target"): vol.All(int, vol.Range(min=0, max=365)),
        vol.Optional("streak_reward"): vol.All(int, vol.Range(min=0, max=1000)),
        vol.Optional("piggy_interest_percent"): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Optional("piggy_interest_weekday"): vol.All(int, vol.Range(min=0, max=6)),
        vol.Optional("piggy_interest_time"): vol.Match(r"^\d{1,2}:\d{2}$"),
        vol.Optional("piggy_interest_min"): vol.Any(
            None, vol.All(int, vol.Range(min=0))
        ),
        vol.Optional("piggy_interest_max"): vol.Any(
            None, vol.All(int, vol.Range(min=0))
        ),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_settings_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Change the settings and push the new texts to every knob."""
    language = msg.get("language")
    codes = await hass.async_add_executor_job(available_languages)
    if language is not None and language != LANGUAGE_AUTO and language not in codes:
        connection.send_error(msg["id"], "invalid_language", "Unknown language")
        return
    data = hass.data[DOMAIN]
    changes = {
        key: msg[key]
        for key in (
            "animation_mode",
            "inactivity_s",
            "streak_target",
            "streak_reward",
            "piggy_interest_percent",
            "piggy_interest_weekday",
            "piggy_interest_time",
            "piggy_interest_min",
            "piggy_interest_max",
        )
        if key in msg
    }
    if language is not None:
        changes["language"] = language
    await data.manager.async_update_settings(changes, who=_who(connection))
    if language is not None:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            entry.runtime_data.async_schedule_push()
    connection.send_result(msg["id"], await _settings(hass))


# ---------------------------------------------------------------- data


def _manager(hass: HomeAssistant) -> KisSegitoManager:
    return hass.data[DOMAIN].manager


def _icons() -> list[str]:
    return sorted(path.stem for path in (FRONTEND_DIR / "icons").glob("*.png"))


def _devices(hass: HomeAssistant) -> list[dict[str, Any]]:
    registry = dr.async_get(hass)
    result = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        device_id = entry.data[CONF_DEVICE_ID]
        device = registry.async_get(device_id)
        result.append(
            {
                "device_id": device_id,
                "name": (device.name_by_user or device.name) if device else entry.title,
            }
        )
    return result


def _children(manager: KisSegitoManager) -> list[dict[str, Any]]:
    return [
        child
        | {
            "balances": manager.balances(child["id"]),
            "streak": manager.streak(child["id"]),
        }
        for child in manager.children()
    ]


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/data"})
@websocket_api.async_response
async def ws_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Everything the panel shows: settings, children, routines, rewards."""
    manager = _manager(hass)
    connection.send_result(
        msg["id"],
        {
            "version": hass.data[DOMAIN].version,
            "settings": await _settings(hass),
            "children": _children(manager),
            "routines": sorted(
                manager.data["routines"], key=lambda r: r.get("start", "")
            ),
            "rewards": sorted(
                manager.data["rewards"], key=lambda r: r.get("sort_order", 0)
            ),
            "devices": _devices(hass),
            "icons": await hass.async_add_executor_job(_icons),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send an event to the panel after every data change."""

    @callback
    def changed() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], {"changed": True})
        )

    connection.subscriptions[msg["id"]] = _manager(hass).async_add_listener(changed)
    connection.send_result(msg["id"])


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
        vol.Required("type"): f"{DOMAIN}/save",
        vol.Required("collection"): vol.In(COLLECTIONS),
        vol.Required("item"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create or update a child, routine or reward."""
    item = {k: v for k, v in msg["item"].items() if k not in ("balances", "streak")}
    await _run(
        connection, msg["id"], _manager(hass).async_save_item(msg["collection"], item)
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete",
        vol.Required("collection"): vol.In(COLLECTIONS),
        vol.Required("item_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a child, routine or reward (token history is kept)."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_delete_item(msg["collection"], msg["item_id"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/reorder",
        vol.Required("collection"): vol.In(COLLECTIONS),
        vol.Required("ids"): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_reorder(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set the display order."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_reorder(msg["collection"], msg["ids"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/assign",
        vol.Required("child_id"): str,
        vol.Required("device_id"): vol.Any(None, str),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_assign(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Assign a child to a knob (or to none)."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_assign_device(msg["child_id"], msg["device_id"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/history",
        vol.Optional("child_id"): vol.Any(None, str),
        vol.Optional("limit", default=200): vol.All(int, vol.Range(min=1, max=2000)),
        vol.Optional("reasons"): vol.Any(None, [str]),
        vol.Optional("account"): vol.Any(None, vol.In([WALLET, PIGGY])),
        vol.Optional("date_from"): vol.Any(None, str),
        vol.Optional("date_to"): vol.Any(None, str),
        vol.Optional("search"): vol.Any(None, str),
    }
)
@callback
def ws_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Token history, newest first, with effective amounts."""
    connection.send_result(
        msg["id"],
        _manager(hass).history(
            msg.get("child_id"),
            msg["limit"],
            reasons=msg.get("reasons"),
            account=msg.get("account"),
            date_from=msg.get("date_from") or None,
            date_to=msg.get("date_to") or None,
            search=msg.get("search"),
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/tokens/adjust",
        vol.Required("child_id"): str,
        vol.Required("amount"): int,
        vol.Optional("account", default=WALLET): vol.In([WALLET, PIGGY]),
        vol.Optional("note", default=""): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_adjust(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Manual bonus or debit."""
    user = connection.user.name if connection.user else "parent"
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_adjust(
            msg["child_id"],
            msg["amount"],
            account=msg["account"],
            note=msg["note"],
            creator=user or "parent",
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/tokens/reverse",
        vol.Required("transaction_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_reverse(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Reverse a transaction (a compensating one is added)."""
    user = connection.user.name if connection.user else "parent"
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_reverse(msg["transaction_id"], creator=user or "parent"),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/tokens/correct",
        vol.Required("transaction_id"): str,
        vol.Optional("account", default=WALLET): vol.In([WALLET, PIGGY]),
        vol.Required("amount"): int,
        vol.Optional("note", default=""): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_correct(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Change the effective amount of a transaction (a correction is added)."""
    user = connection.user.name if connection.user else "parent"
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_correct(
            msg["transaction_id"],
            msg["account"],
            msg["amount"],
            creator=user or "parent",
            note=msg["note"],
        ),
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/today"})
@callback
def ws_today(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Today's progress per routine and child."""
    manager = _manager(hass)
    day = manager.today()
    connection.send_result(
        msg["id"],
        {
            "date": day.isoformat(),
            "progress": manager.data["days"].get(day.isoformat(), {}),
        },
    )


def _who(connection: websocket_api.ActiveConnection) -> str:
    return (connection.user.name if connection.user else None) or "parent"


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/override",
        vol.Required("routine_id"): str,
        vol.Optional("date"): str,
        vol.Optional("skip", default=False): bool,
        vol.Optional("shift_min", default=0): vol.All(
            int, vol.Range(min=-720, max=720)
        ),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_override(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Change a routine for one day only ("Modify today")."""
    manager = _manager(hass)
    day = date.fromisoformat(msg["date"]) if msg.get("date") else manager.today()
    await _run(
        connection,
        msg["id"],
        manager.async_set_override(
            day,
            msg["routine_id"],
            skip=msg["skip"],
            shift_min=msg["shift_min"],
            who=_who(connection),
        ),
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/week", vol.Optional("start"): str}
)
@callback
def ws_week(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Seven days of routines as they run (one-day changes applied)."""
    manager = _manager(hass)
    today = manager.today()
    start = (
        date.fromisoformat(msg["start"])
        if msg.get("start")
        else today - timedelta(days=today.weekday())
    )
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        days.append(
            {
                "date": day.isoformat(),
                "today": day == today,
                "routines": [
                    {
                        "id": r["id"],
                        "name": r.get("name", ""),
                        "icon": r.get("icon", "routine_generic"),
                        "start": r.get("start"),
                        "end": r.get("end"),
                        "children": r.get("children", []),
                        "checkpoints": [
                            {
                                "name": c.get("name", ""),
                                "icon": c.get("icon"),
                                "time": c.get("time"),
                            }
                            for c in r.get("checkpoints", [])
                        ],
                        "override": manager.override(day, r["id"]),
                    }
                    for r in manager.routines_on_day(day)
                ],
                "skipped": [
                    rid
                    for rid, o in manager.data["overrides"]
                    .get(day.isoformat(), {})
                    .items()
                    if o.get("skip")
                ],
            }
        )
    connection.send_result(msg["id"], {"start": start.isoformat(), "days": days})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/notifications",
        vol.Optional("rules"): [
            vol.Schema(
                {
                    vol.Optional("id"): str,
                    vol.Optional("name", default=""): str,
                    vol.Required("service"): str,
                    vol.Optional("events", default=list): [vol.In(EVENT_TYPES)],
                    vol.Optional("children", default=list): [str],
                    vol.Optional("enabled", default=True): bool,
                }
            )
        ],
    }
)
@websocket_api.async_response
async def ws_notifications(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Read the notification rules, or replace them (admins only)."""
    manager = _manager(hass)
    if "rules" in msg:
        if not connection.user or not connection.user.is_admin:
            connection.send_error(msg["id"], "unauthorized", "Admins only")
            return
        await manager.async_save_notifications(msg["rules"], who=_who(connection))
    connection.send_result(
        msg["id"],
        {"rules": manager.data["notifications"], "event_types": list(EVENT_TYPES)},
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/export"})
@websocket_api.require_admin
@callback
def ws_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Everything as one JSON document (configuration and token history)."""
    data = hass.data[DOMAIN]
    connection.send_result(
        msg["id"],
        {
            "kis_segito_export": 1,
            "version": data.version,
            "config": data.store.data,
            "ledger": data.store.ledger["transactions"],
        },
    )
