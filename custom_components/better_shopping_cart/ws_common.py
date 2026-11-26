"""Shared helpers for the Better Shopping Cart WebSocket commands (M3).

The §5 commands are split across several modules (``websocket_api.py`` for
sections/layouts, ``ws_lists.py`` for lists, ``ws_items.py`` for items,
``ws_templates.py`` for templates/history and ``ws_settings.py`` for
settings/subscribe) to keep each file close to the ~300-line target. The
shared schema pieces, the store lookup and the error mapping live here.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_UPDATED
from .store import BetterShoppingCartStore

_TYPE = f"{DOMAIN}/"
Msg = dict[str, Any]

# A name: a non-empty string.
_NAME = vol.All(cv.string, vol.Length(min=1))
# An updatable name: a non-empty string, or null (null = leave unchanged).
_OPT_NAME = vol.Any(_NAME, None)
# An optional identifier: a string, or explicit null (clears / no change).
_ID = vol.Any(cv.string, None)
# An optional free-form string: a string, or null (null = leave unchanged).
_OPT_STRING = vol.Any(cv.string, None)
# A quantity: any number.
_QTY = vol.Coerce(float)


def get_store(hass: HomeAssistant) -> BetterShoppingCartStore:
    """Return the loaded store, or a WS-visible error when not set up."""
    store = hass.data.get(DOMAIN)
    if store is None:
        raise HomeAssistantError("Better Shopping Cart is not set up")
    return store


def as_error(err: ValueError) -> HomeAssistantError:
    """Map a store-level ValueError (unknown id) to a WS error response."""
    return HomeAssistantError(str(err))


async def commit(hass: HomeAssistant, store: BetterShoppingCartStore) -> None:
    """Persist a mutation and notify listeners (PLAN.md §5)."""
    await store.async_save()
    async_dispatcher_send(hass, SIGNAL_UPDATED)
