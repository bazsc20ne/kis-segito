# SPDX-License-Identifier: AGPL-3.0-only
"""Home Assistant actions for automations (see services.yaml)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .ledger import PIGGY, WALLET
from .manager import KisSegitoError, KisSegitoManager

CHILD = vol.Required("child_id")

SCHEMAS = {
    "complete_task": vol.Schema(
        {
            CHILD: cv.string,
            vol.Required("routine_id"): cv.string,
            vol.Required("task_id"): cv.string,
        }
    ),
    "complete_checkpoint": vol.Schema(
        {
            CHILD: cv.string,
            vol.Required("routine_id"): cv.string,
            vol.Required("checkpoint_id"): cv.string,
        }
    ),
    "adjust_tokens": vol.Schema(
        {
            CHILD: cv.string,
            vol.Required("amount"): vol.Coerce(int),
            vol.Optional("account", default=WALLET): vol.In([WALLET, PIGGY]),
            vol.Optional("note", default=""): cv.string,
        }
    ),
    "redeem_reward": vol.Schema(
        {CHILD: cv.string, vol.Required("reward_id"): cv.string}
    ),
    "piggy_deposit": vol.Schema(
        {
            CHILD: cv.string,
            vol.Required("amount"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }
    ),
    "piggy_withdraw": vol.Schema(
        {
            CHILD: cv.string,
            vol.Required("amount"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }
    ),
    "reverse_transaction": vol.Schema({vol.Required("transaction_id"): cv.string}),
}


@callback
def async_register_services(hass: HomeAssistant, manager: KisSegitoManager) -> None:
    """Register the integration's actions."""

    async def handle(call: ServiceCall) -> None:
        data = call.data
        try:
            match call.service:
                case "complete_task":
                    await manager.async_complete_task(
                        data["child_id"], data["routine_id"], data["task_id"]
                    )
                case "complete_checkpoint":
                    await manager.async_complete_checkpoint(
                        data["child_id"], data["routine_id"], data["checkpoint_id"]
                    )
                case "adjust_tokens":
                    await manager.async_adjust(
                        data["child_id"],
                        data["amount"],
                        account=data["account"],
                        note=data["note"],
                        creator="automation",
                        source="service",
                    )
                case "redeem_reward":
                    await manager.async_redeem(
                        data["child_id"],
                        data["reward_id"],
                        source="service",
                        creator="automation",
                    )
                case "piggy_deposit":
                    await manager.async_piggy_transfer(
                        data["child_id"],
                        data["amount"],
                        source="service",
                        creator="automation",
                    )
                case "piggy_withdraw":
                    await manager.async_piggy_transfer(
                        data["child_id"],
                        -data["amount"],
                        source="service",
                        creator="automation",
                    )
                case "reverse_transaction":
                    await manager.async_reverse(
                        data["transaction_id"], creator="automation"
                    )
        except KisSegitoError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key=err.code
            ) from err

    for name, schema in SCHEMAS.items():
        hass.services.async_register(DOMAIN, name, handle, schema=schema)
