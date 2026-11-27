"""The Smartcart integration.

A mobile-friendly supermarket shopping list for Home Assistant.

M0: sets up the store, registers the (stub) WebSocket module and forwards the
todo platform. M1-M9 fill in the store CRUD, WebSocket commands, todo entities
and the custom panel. M9 also registers the ``add_item`` and
``complete_list`` HA services (documented in ``services.yaml``).
"""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import (
    DOMAIN,
    PANEL_MODULE_URL,
    PANEL_URL_PATH,
    PANEL_WEBCOMPONENT,
)
from .store import BetterShoppingCartStore
from .ws_common import commit

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.TODO]

# Directory of the frontend assets, served under /bsc/.
PANEL_DIR = Path(__file__).parent / "frontend"

# M9: HA services so automations, scripts and Assist can add items to and
# complete lists (documented in services.yaml). Lists and sections are
# referenced by name so voice commands read naturally.
SERVICE_ADD_ITEM = "add_item"
SERVICE_COMPLETE_LIST = "complete_list"

ADD_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("list"): cv.string,
        vol.Optional("section"): cv.string,
        vol.Optional("quantity"): vol.Coerce(float),
        vol.Optional("unit"): cv.string,
        vol.Optional("note"): cv.string,
    }
)

COMPLETE_LIST_SCHEMA = vol.Schema({vol.Required("list"): cv.string})


def _get_store(hass: HomeAssistant) -> BetterShoppingCartStore:
    """Return the loaded store or raise a service-visible error."""
    store = hass.data.get(DOMAIN)
    if store is None:
        raise HomeAssistantError("Smartcart is not set up")
    return store


def _resolve_list_id(store: BetterShoppingCartStore, name: str) -> str:
    """Resolve a list name (case-insensitive) to its id."""
    wanted = " ".join(name.lower().split())
    for entry in store.lists():
        if " ".join(entry.name.lower().split()) == wanted:
            return entry.id
    raise HomeAssistantError(f"unknown list: {name}")


def _resolve_section_id(store: BetterShoppingCartStore, name: str) -> str | None:
    """Resolve a section name (case-insensitive) to its id."""
    if name is None:
        return None
    wanted = " ".join(name.lower().split())
    for entry in store.sections():
        if " ".join(entry.name.lower().split()) == wanted:
            return entry.id
    raise HomeAssistantError(f"unknown section: {name}")


async def _async_add_item(call: ServiceCall) -> None:
    """Handle ``better_shopping_cart/add_item``."""
    hass = call.hass
    store = _get_store(hass)
    data = call.data
    try:
        store.add_item(
            _resolve_list_id(store, data["list"]),
            data["name"],
            section_id=_resolve_section_id(store, data.get("section")),
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            note=data.get("note"),
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err
    await commit(hass, store)


async def _async_complete_list(call: ServiceCall) -> None:
    """Handle ``better_shopping_cart/complete_list``."""
    hass = call.hass
    store = _get_store(hass)
    try:
        store.complete_list(_resolve_list_id(store, call.data["list"]))
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err
    await commit(hass, store)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Smartcart integration (no YAML configuration)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smartcart from a config entry."""
    if DOMAIN in hass.data:
        return True

    cart = BetterShoppingCartStore(hass)
    await cart.async_load()
    hass.data[DOMAIN] = cart

    await websocket_api.async_register(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # M9: register the add_item / complete_list services.
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEM, _async_add_item, schema=ADD_ITEM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COMPLETE_LIST, _async_complete_list, schema=COMPLETE_LIST_SCHEMA
    )

    # M5: serve the panel assets and register the sidebar panel.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url_path="/bsc", path=str(PANEL_DIR))]
    )
    await async_register_panel(
        hass,
        PANEL_URL_PATH,
        PANEL_WEBCOMPONENT,
        sidebar_title="Shopping Cart",
        sidebar_icon="mdi:cart",
        module_url=PANEL_MODULE_URL,
        config={},
    )

    _LOGGER.debug("Smartcart set up (entry: %s)", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    async_remove_panel(hass, PANEL_URL_PATH)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_ITEM)
    hass.services.async_remove(DOMAIN, SERVICE_COMPLETE_LIST)
    hass.data.pop(DOMAIN, None)
    return True
