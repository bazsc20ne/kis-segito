# SPDX-License-Identifier: AGPL-3.0-only
"""A read-only tool for LLM-based Assist agents: what Kis Segítő knows about
a child. Offered when at least one Kis Segítő entity is exposed to the
assistant."""

from __future__ import annotations

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    ToolAnnotations,
)

from .assist import INTENT_CHILD_STATUS
from .const import DOMAIN

ANNOTATIONS = ToolAnnotations(
    read_only=True, destructive=False, idempotent=True, open_world=False
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """The child status tool, when a Kis Segítő entity is exposed."""
    if api_id != LLM_API_ASSIST or not llm_context.assistant:
        return None
    registry = er.async_get(hass)
    if not any(
        entry.platform == DOMAIN
        and async_should_expose(hass, llm_context.assistant, entry.entity_id)
        for entry in registry.entities.values()
    ):
        return None
    tools = [
        IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            title="Kis Segítő child status",
            integration=DOMAIN,
            annotations=ANNOTATIONS,
        )
        for handler in intent.async_get(hass)
        if handler.intent_type == INTENT_CHILD_STATUS
    ]
    return LLMTools(tools=tools) if tools else None
