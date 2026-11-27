"""WebSocket commands for items (PLAN.md §5, M3).

Every mutating command saves the store and fires the ``{DOMAIN}_updated``
dispatcher signal (via ``commit``). Store-level ``ValueError`` (unknown
ids) is mapped to a ``home_assistant_error`` WebSocket error response.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .ws_common import (
    _ID,
    _NAME,
    _OPT_NAME,
    _OPT_STRING,
    _QTY,
    _TYPE,
    Msg,
    as_error,
    commit,
    get_store,
    notify_item_added,
)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}items/list",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_items_list(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/items/list``."""
    store = get_store(hass)
    try:
        items = store.items(msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    connection.send_result(msg["id"], {"items": [i.to_dict() for i in items]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}items/add",
        vol.Required("list_id"): cv.string,
        vol.Required("name"): _NAME,
        vol.Optional("section_id"): _ID,
        vol.Optional("quantity"): _QTY,
        vol.Optional("unit"): _OPT_STRING,
        vol.Optional("note"): _OPT_STRING,
    }
)
@websocket_api.async_response
async def websocket_items_add(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/items/add``.

    Without ``section_id`` the item is auto-categorised (PLAN.md §5).
    With ``notify_on_add`` enabled, the configured notify service is
    called with ``"<user> added <item> to <list>"`` (PLAN.md M9).
    """
    store = get_store(hass)
    try:
        section_id = msg.get("section_id")
        if section_id is not None and store.section(section_id) is None:
            raise ValueError(f"unknown section: {section_id}")
        item = store.add_item(
            msg["list_id"],
            msg["name"],
            section_id=section_id,
            quantity=msg.get("quantity"),
            unit=msg.get("unit"),
            note=msg.get("note"),
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"item": item.to_dict()})
    await notify_item_added(
        hass,
        connection,
        store.settings(),
        item,
        store.shopping_list(msg["list_id"]).name,
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}items/update",
        vol.Required("list_id"): cv.string,
        vol.Required("item_id"): cv.string,
        vol.Optional("name"): _OPT_NAME,
        vol.Optional("section_id"): _ID,
        vol.Optional("quantity"): _QTY,
        vol.Optional("unit"): _OPT_STRING,
        vol.Optional("note"): _OPT_STRING,
    }
)
@websocket_api.async_response
async def websocket_items_update(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/items/update``.

    Moving the item to a new section records the choice in the learned
    category map (PLAN.md §5).
    """
    store = get_store(hass)
    try:
        item = store.update_item(
            msg["list_id"],
            msg["item_id"],
            name=msg.get("name"),
            section_id=msg.get("section_id"),
            quantity=msg.get("quantity"),
            unit=msg.get("unit"),
            note=msg.get("note"),
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"item": item.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}items/check",
        vol.Required("list_id"): cv.string,
        vol.Required("item_id"): cv.string,
        vol.Required("checked"): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_items_check(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/items/check``."""
    store = get_store(hass)
    try:
        item = store.check_item(msg["list_id"], msg["item_id"], msg["checked"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"item": item.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}items/delete",
        vol.Required("list_id"): cv.string,
        vol.Required("item_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_items_delete(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/items/delete``."""
    store = get_store(hass)
    try:
        store.delete_item(msg["list_id"], msg["item_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}items/reorder",
        vol.Required("list_id"): cv.string,
        vol.Required("ordered_ids"): [cv.string],
    }
)
@websocket_api.async_response
async def websocket_items_reorder(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/items/reorder``."""
    store = get_store(hass)
    try:
        store.reorder_items(msg["list_id"], msg["ordered_ids"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = (
    websocket_items_list,
    websocket_items_add,
    websocket_items_update,
    websocket_items_check,
    websocket_items_delete,
    websocket_items_reorder,
)
