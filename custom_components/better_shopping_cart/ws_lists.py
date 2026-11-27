"""WebSocket commands for lists (PLAN.md §5, M3).

Every mutating command saves the store and fires the ``{DOMAIN}_updated``
dispatcher signal (via ``commit``). Store-level ``ValueError`` (unknown
ids) is mapped to a ``home_assistant_error`` WebSocket error response.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .ws_common import _ID, _NAME, _OPT_NAME, _TYPE, Msg, as_error, commit, get_store


@websocket_api.websocket_command(
    {vol.Required("type"): f"{_TYPE}lists/list"}
)
@websocket_api.async_response
async def websocket_lists_list(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/list``."""
    store = get_store(hass)
    connection.send_result(
        msg["id"], {"lists": [lst.to_dict() for lst in store.lists()]}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}lists/create",
        vol.Required("name"): _NAME,
        vol.Optional("layout_id"): _ID,
    }
)
@websocket_api.async_response
async def websocket_lists_create(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/create``."""
    store = get_store(hass)
    try:
        shopping_list = store.create_list(msg["name"], msg.get("layout_id"))
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"list": shopping_list.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}lists/update",
        vol.Required("list_id"): cv.string,
        vol.Optional("name"): _OPT_NAME,
        vol.Optional("layout_id"): _ID,
    }
)
@websocket_api.async_response
async def websocket_lists_update(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/update``.

    Omitting ``layout_id`` leaves the layout untouched; an explicit
    ``null`` clears it (matching the §5 contract).
    """
    store = get_store(hass)
    kwargs: dict[str, Any] = {}
    if "layout_id" in msg:
        kwargs["layout_id"] = msg["layout_id"]
    try:
        shopping_list = store.update_list(
            msg["list_id"], name=msg.get("name"), **kwargs
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"list": shopping_list.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}lists/delete",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_lists_delete(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/delete``."""
    store = get_store(hass)
    try:
        store.delete_list(msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}lists/complete",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_lists_complete(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/complete``."""
    store = get_store(hass)
    try:
        shopping_list = store.complete_list(msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"list": shopping_list.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}lists/clear",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_lists_clear(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/clear`` (NOTES: Shopping Cart View).

    Removes every item from the list in one commit instead of one
    ``items/delete`` round trip per item.
    """
    store = get_store(hass)
    try:
        store.clear_list(msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}lists/clear_completed",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_lists_clear_completed(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/lists/clear_completed``."""
    store = get_store(hass)
    try:
        store.clear_completed(msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = (
    websocket_lists_list,
    websocket_lists_create,
    websocket_lists_update,
    websocket_lists_delete,
    websocket_lists_complete,
    websocket_lists_clear,
    websocket_lists_clear_completed,
)
