# SPDX-License-Identifier: AGPL-3.0-only
"""WebSocket commands used by the Kis Segito panel."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.service import async_get_all_descriptions

from .const import CONF_DEVICE_ID, DOMAIN, LANGUAGE_AUTO
from .device_link import api_encrypted, available_languages
from .icons import ICON_ALIASES
from .ledger import PIGGY, WALLET
from .manager import (
    BACKGROUND_PRESETS,
    BACKGROUND_VALUE,
    COLLECTIONS,
    KisSegitoError,
    KisSegitoManager,
)
from .notify import EVENT_TYPES
from .panel import FRONTEND_DIR, panel_language_names
from .store import DEFAULT_SETTINGS

# Knob screen power settings: seconds (0 = never), the dim level in percent.
SCREEN_FIELDS = {
    "saver_after": vol.All(int, vol.Range(min=0, max=86400)),
    "dim_after": vol.All(int, vol.Range(min=0, max=86400)),
    "dim_level": vol.All(int, vol.Range(min=1, max=100)),
    "blank_after": vol.All(int, vol.Range(min=0, max=86400)),
    "off_after": vol.All(int, vol.Range(min=0, max=86400)),
    "saver_type": vol.In(["balls", "confetti", "stars"]),
}
SCREEN_SCHEMA = vol.Schema({vol.Optional(k): v for k, v in SCREEN_FIELDS.items()})


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
        ws_day_template,
        ws_notify_targets,
        ws_notify_test,
        ws_day_routine,
        ws_rotate_device_token,
        ws_device_screen,
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
        "screen": DEFAULT_SETTINGS["screen"]
        | (data.store.settings.get("screen") or {}),
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
        vol.Optional("notification_label"): str,
        vol.Optional("background"): vol.Match(BACKGROUND_VALUE),
        vol.Optional("screen"): SCREEN_SCHEMA,
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
            "notification_label",
            "background",
        )
        if key in msg
    }
    if "screen" in msg:
        changes["screen"] = data.manager.settings.get("screen", {}) | msg["screen"]
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


def _small_icons() -> list[str]:
    return sorted(
        path.stem for path in (FRONTEND_DIR / "icons" / "small").glob("*.png")
    )


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
                "encrypted": device is not None and api_encrypted(hass, device),
                "screen": hass.data[DOMAIN]
                .manager.data["devices"]
                .get(device_id, {})
                .get("screen", {}),
            }
        )
    return result


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/device/screen",
        vol.Required("device_id"): str,
        # A number overrides the general value for this knob; None clears it.
        vol.Required("screen"): {
            vol.Optional(key): vol.Any(None, validator)
            for key, validator in SCREEN_FIELDS.items()
        },
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_device_screen(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set or clear a knob's own screen power settings."""
    if msg["device_id"] not in {d["device_id"] for d in _devices(hass)}:
        connection.send_error(msg["id"], "unknown_device", "Unknown knob")
        return
    await _manager(hass).async_set_device_screen(
        msg["device_id"], msg["screen"], who=_who(connection)
    )
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/device/rotate_token",
        vol.Required("device_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_rotate_device_token(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Give a knob a new picture key; the old one stops working at once."""
    if msg["device_id"] not in {d["device_id"] for d in _devices(hass)}:
        connection.send_error(msg["id"], "unknown_device", "Unknown knob")
        return
    await _manager(hass).async_rotate_device_token(msg["device_id"])
    connection.send_result(msg["id"])


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
            "templates": manager.data["templates"],
            "routine_templates": manager.data["routine_templates"],
            "weekday_templates": manager.data["weekday_templates"],
            "date_templates": manager.data["date_templates"],
            "devices": _devices(hass),
            "icons": await hass.async_add_executor_job(_icons),
            "small_icons": await hass.async_add_executor_job(_small_icons),
            "icon_aliases": ICON_ALIASES,
            "backgrounds": list(BACKGROUND_PRESETS),
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
        template = manager.template_for_day(day)
        days.append(
            {
                "date": day.isoformat(),
                "today": day == today,
                "template": template["id"] if template else None,
                "template_name": template.get("name", "") if template else None,
                "routines": [
                    {
                        "routine": r,
                        "one_day": bool(r.get("one_day")),
                        "edited": bool(
                            (manager.override(day, r["id"]) or {}).get("routine")
                        ),
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
                    # Script targets: which fields get the message and title,
                    # and fixed values for other fields.
                    vol.Optional("message_field", default=""): str,
                    vol.Optional("title_field", default=""): str,
                    vol.Optional("extra", default=dict): {
                        str: vol.Any(str, int, float, bool, None)
                    },
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/day_template",
        vol.Exclusive("date", "day"): str,
        vol.Exclusive("weekday", "day"): vol.All(int, vol.Range(min=0, max=6)),
        vol.Required("template_id"): vol.Any(None, str),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_day_template(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Choose the day template of a date or the default of a weekday."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_set_day_template(
            day=date.fromisoformat(msg["date"]) if msg.get("date") else None,
            weekday=msg.get("weekday"),
            template_id=msg["template_id"],
            who=_who(connection),
        ),
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/notify_targets"})
@websocket_api.async_response
async def ws_notify_targets(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Notify actions and scripts (with their fields) that can be rule targets.

    Scripts carrying the label set in the settings are marked ``labelled``;
    the panel lists only those unless "show all scripts" is on.
    """
    label_setting = str(_manager(hass).settings.get("notification_label") or "").strip()
    label_ids: set[str] = set()
    if label_setting:
        for label in lr.async_get(hass).async_list_labels():
            if label_setting.casefold() in (
                label.label_id.casefold(),
                label.name.casefold(),
            ):
                label_ids.add(label.label_id)
    descriptions = await async_get_all_descriptions(hass)
    registry = er.async_get(hass)
    scripts = []
    for name, description in sorted(descriptions.get("script", {}).items()):
        if name in ("turn_on", "turn_off", "toggle", "reload"):
            continue
        entry = registry.async_get(f"script.{name}")
        state = hass.states.get(f"script.{name}")
        fields = description.get("fields") or {}
        scripts.append(
            {
                "service": f"script.{name}",
                "name": (state.name if state else None)
                or description.get("name")
                or name,
                "labelled": bool(entry and label_ids & set(entry.labels)),
                "fields": {
                    key: {
                        "name": field.get("name") or key,
                        "description": field.get("description") or "",
                        "selector": field.get("selector") or {},
                    }
                    for key, field in fields.items()
                },
            }
        )
    connection.send_result(
        msg["id"],
        {
            "notify": sorted(
                f"notify.{name}"
                for name in descriptions.get("notify", {})
                if name != "send_message"
            ),
            "scripts": scripts,
            "label": label_setting,
            "label_found": bool(label_ids),
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/notify_test", vol.Required("rule"): dict}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_notify_test(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send a sample message through a rule (not saved)."""
    notifier = _manager(hass).notifier
    try:
        await notifier.async_test(msg["rule"])
    except Exception as err:  # noqa: BLE001 - shown in the panel
        connection.send_error(msg["id"], "notify_failed", str(err))
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/day_routine",
        vol.Required("date"): str,
        vol.Optional("routine_id"): vol.Any(None, str),
        vol.Required("routine"): vol.Any(None, dict),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_day_routine(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Edit a routine for one day, add a one-day routine, or restore."""
    await _run(
        connection,
        msg["id"],
        _manager(hass).async_set_day_routine(
            date.fromisoformat(msg["date"]),
            msg.get("routine_id"),
            msg["routine"],
            who=_who(connection),
        ),
    )
