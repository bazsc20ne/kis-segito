# SPDX-License-Identifier: AGPL-3.0-only
"""Rule-based notifications for Kis Segito events.

Each rule picks a Home Assistant notify action (e.g. ``notify.mobile_app_x``),
the event types and optionally the children it is about. Texts come from
notification_translations/<language>.json (English fills missing keys).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_LANGUAGE

_LOGGER = logging.getLogger(__name__)

TEXTS_DIR = Path(__file__).parent / "notification_translations"

# Event types a rule can select (see docs/automations.md).
EVENT_TYPES = (
    "reward_redeemed",
    "checkpoint_completed",
    "task_completed",
    "piggy_deposit",
    "piggy_withdrawal",
    "piggy_interest",
    "streak_completed",
    "manual_adjustment",
    "transaction_reversed",
    "transaction_revised",
)


def load_texts(language: str | None) -> dict[str, str]:
    """Notification texts in ``language`` (or its base language), English otherwise."""

    def read(code: str) -> dict[str, str]:
        path = TEXTS_DIR / f"{code}.json"
        if not path.exists():
            return {}
        with path.open(encoding="utf-8") as file:
            return {str(k): str(v) for k, v in json.load(file).items()}

    texts = read(DEFAULT_LANGUAGE)
    if language:
        for candidate in (language, language.split("-")[0]):
            if candidate != DEFAULT_LANGUAGE and (extra := read(candidate)):
                texts |= extra
                break
    return texts


def format_message(texts: dict[str, str], event: dict[str, Any]) -> str | None:
    """The notification text of an event, or None when there is no text for it."""
    template = texts.get(str(event.get("event_type")))
    if template is None:
        return None
    amount = int(event.get("amount") or 0)
    values = {
        "child": event.get("child_name") or "",
        "reward": event.get("reward_name") or "",
        "amount": abs(amount),
        "amount_abs": abs(amount),
        "amount_signed": f"{amount:+d}",
        "wallet": event.get("wallet_balance", ""),
        "piggy": event.get("piggy_balance", ""),
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def rule_matches(rule: dict[str, Any], event: dict[str, Any]) -> bool:
    """Whether an enabled rule wants this event."""
    if not rule.get("enabled", True) or not rule.get("service"):
        return False
    if event.get("event_type") not in (rule.get("events") or []):
        return False
    children = rule.get("children") or []
    return not children or event.get("child_id") in children


class Notifier:
    """Sends notifications for events according to the rules."""

    def __init__(self, hass: HomeAssistant, rules: Any, language: Any) -> None:
        self.hass = hass
        self._rules = rules  # callable returning the rule list
        self._language = language  # callable returning the language

    @callback
    def __call__(self, event: dict[str, Any]) -> None:
        rules = [r for r in self._rules() if rule_matches(r, event)]
        if rules:
            self.hass.async_create_task(self._async_send(rules, event))

    async def _async_send(
        self, rules: list[dict[str, Any]], event: dict[str, Any]
    ) -> None:
        texts = await self.hass.async_add_executor_job(load_texts, self._language())
        message = format_message(texts, event)
        if message is None:
            return
        for rule in rules:
            domain, _, service = str(rule["service"]).partition(".")
            if not service:
                domain, service = "notify", domain
            try:
                await self.hass.services.async_call(
                    domain,
                    service,
                    {"title": texts.get("title", "Kis Segítő"), "message": message},
                    blocking=True,
                )
            except Exception:
                _LOGGER.warning(
                    "Notification rule %s could not be sent through %s",
                    rule.get("name") or rule.get("id"),
                    rule["service"],
                    exc_info=True,
                )
