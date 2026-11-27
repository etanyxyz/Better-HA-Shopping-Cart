"""WebSocket API for Better Shopping Cart (PLAN.md §5 frozen contract).

M2: ``sections/*`` and ``layouts/*`` commands (this module). M3 adds
``lists/*`` (``ws_lists.py``), ``items/*`` (``ws_items.py``),
``templates/*`` and ``history/*`` (``ws_templates.py``) and ``settings/*``
and ``subscribe`` (``ws_settings.py``). All commands use the
``better_shopping_cart/`` type prefix and are registered together by
``async_register``.

Parameter names avoid the bare ``id`` key: the top-level ``id`` is
reserved by the WebSocket message envelope for request correlation (the
client overwrites any payload ``id`` before sending). The contract's
own ``items/*`` commands already follow the ``<entity>_id`` convention
(``list_id``, ``item_id``), so sections, layouts, lists and templates
use ``section_id`` / ``layout_id`` / ``list_id`` / ``template_id``.

Every mutating command saves the store and fires the ``{DOMAIN}_updated``
dispatcher signal so the panel and todo entities refresh live (PLAN.md §5).
Store-level ``ValueError`` (unknown ids) is mapped to a
``home_assistant_error`` WebSocket error response.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from . import ws_items, ws_lists, ws_settings, ws_templates
from .ws_common import _NAME, _TYPE, Msg, as_error, commit, get_store


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


@websocket_api.websocket_command(
    {vol.Required("type"): f"{_TYPE}sections/list"}
)
@websocket_api.async_response
async def websocket_sections_list(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/sections/list``."""
    store = get_store(hass)
    connection.send_result(
        msg["id"], {"sections": [s.to_dict() for s in store.sections()]}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}sections/create",
        vol.Required("name"): _NAME,
        vol.Optional("icon"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_sections_create(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/sections/create``."""
    store = get_store(hass)
    try:
        section = store.create_section(msg["name"], msg.get("icon"))
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"section": section.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}sections/update",
        vol.Required("section_id"): cv.string,
        vol.Optional("name"): _NAME,
        vol.Optional("icon"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_sections_update(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/sections/update``."""
    store = get_store(hass)
    try:
        section = store.update_section(
            msg["section_id"], name=msg.get("name"), icon=msg.get("icon")
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"section": section.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}sections/delete",
        vol.Required("section_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_sections_delete(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/sections/delete``."""
    store = get_store(hass)
    try:
        store.delete_section(msg["section_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}sections/reorder",
        vol.Required("ordered_ids"): [cv.string],
    }
)
@websocket_api.async_response
async def websocket_sections_reorder(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/sections/reorder``."""
    store = get_store(hass)
    try:
        store.reorder_sections(msg["ordered_ids"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------


@websocket_api.websocket_command(
    {vol.Required("type"): f"{_TYPE}layouts/list"}
)
@websocket_api.async_response
async def websocket_layouts_list(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/layouts/list``."""
    store = get_store(hass)
    connection.send_result(
        msg["id"], {"layouts": [l.to_dict() for l in store.layouts()]}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}layouts/create",
        vol.Required("name"): _NAME,
    }
)
@websocket_api.async_response
async def websocket_layouts_create(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/layouts/create``."""
    store = get_store(hass)
    layout = store.create_layout(msg["name"])
    await commit(hass, store)
    connection.send_result(msg["id"], {"layout": layout.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}layouts/update",
        vol.Required("layout_id"): cv.string,
        vol.Optional("name"): _NAME,
        vol.Optional("section_order"): [cv.string],
        vol.Optional("hidden_sections"): [cv.string],
    }
)
@websocket_api.async_response
async def websocket_layouts_update(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/layouts/update``."""
    store = get_store(hass)
    try:
        layout = store.update_layout(
            msg["layout_id"],
            name=msg.get("name"),
            section_order=msg.get("section_order"),
            hidden_sections=msg.get("hidden_sections"),
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"layout": layout.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}layouts/delete",
        vol.Required("layout_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_layouts_delete(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/layouts/delete``."""
    store = get_store(hass)
    try:
        store.delete_layout(msg["layout_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = (
    websocket_sections_list,
    websocket_sections_create,
    websocket_sections_update,
    websocket_sections_delete,
    websocket_sections_reorder,
    websocket_layouts_list,
    websocket_layouts_create,
    websocket_layouts_update,
    websocket_layouts_delete,
    *ws_lists.COMMANDS,
    *ws_items.COMMANDS,
    *ws_templates.COMMANDS,
    *ws_settings.COMMANDS,
)


async def async_register(hass: HomeAssistant) -> None:
    """Register the integration's WebSocket commands."""
    for command in COMMANDS:
        websocket_api.async_register_command(hass, command)
