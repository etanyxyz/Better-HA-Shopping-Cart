"""The Better Shopping Cart integration.

A mobile-friendly supermarket shopping list for Home Assistant.

M0: sets up the store, registers the (stub) WebSocket module and forwards the
todo platform. M1-M9 fill in the store CRUD, WebSocket commands, todo entities
and the custom panel.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN
from .store import BetterShoppingCartStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Better Shopping Cart integration (no YAML configuration)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Better Shopping Cart from a config entry."""
    if DOMAIN in hass.data:
        return True

    cart = BetterShoppingCartStore(hass)
    await cart.async_load()
    hass.data[DOMAIN] = cart

    await websocket_api.async_register(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Better Shopping Cart set up (entry: %s)", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry.entry_id, PLATFORMS):
        return False
    hass.data.pop(DOMAIN, None)
    return True
