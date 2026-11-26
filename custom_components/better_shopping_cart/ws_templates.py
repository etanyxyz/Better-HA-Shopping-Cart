"""WebSocket commands for templates and history (PLAN.md §5, M3).

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
    _NAME,
    _OPT_NAME,
    _OPT_STRING,
    _QTY,
    _TYPE,
    Msg,
    as_error,
    commit,
    get_store,
)
from .store import BetterShoppingCartStore

# One template item: a name plus the section it belongs to (§4).
_TEMPLATE_ITEM = vol.Schema(
    {
        vol.Required("name"): _NAME,
        vol.Required("section_id"): cv.string,
        vol.Optional("quantity"): _QTY,
        vol.Optional("unit"): _OPT_STRING,
        vol.Optional("note"): _OPT_STRING,
    }
)


def _require_sections(
    store: BetterShoppingCartStore, items: list[dict]
) -> None:
    """Raise ValueError when an item references an unknown section."""
    for item in items:
        if store.section(item["section_id"]) is None:
            raise ValueError(f"unknown section: {item['section_id']}")


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@websocket_api.websocket_command(
    {vol.Required("type"): f"{_TYPE}templates/list"}
)
@websocket_api.async_response
async def websocket_templates_list(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/templates/list``."""
    store = get_store(hass)
    connection.send_result(
        msg["id"], {"templates": [t.to_dict() for t in store.templates()]}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}templates/create",
        vol.Required("name"): _NAME,
        vol.Required("items"): [_TEMPLATE_ITEM],
    }
)
@websocket_api.async_response
async def websocket_templates_create(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/templates/create``.

    Every item's ``section_id`` must reference an existing section.
    """
    store = get_store(hass)
    try:
        _require_sections(store, msg["items"])
        template = store.create_template(msg["name"], msg["items"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"template": template.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}templates/update",
        vol.Required("template_id"): cv.string,
        vol.Optional("name"): _OPT_NAME,
        vol.Optional("items"): [_TEMPLATE_ITEM],
    }
)
@websocket_api.async_response
async def websocket_templates_update(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/templates/update``.

    Omitting ``items`` leaves them untouched; providing them replaces the
    list (each ``section_id`` must reference an existing section).
    """
    store = get_store(hass)
    try:
        if "items" in msg:
            _require_sections(store, msg["items"])
        template = store.update_template(
            msg["template_id"], name=msg.get("name"), items=msg.get("items")
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"template": template.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}templates/delete",
        vol.Required("template_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_templates_delete(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/templates/delete``."""
    store = get_store(hass)
    try:
        store.delete_template(msg["template_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}templates/apply",
        vol.Required("template_id"): cv.string,
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_templates_apply(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/templates/apply``.

    Adds every template item to the list; returned items are unchecked.
    """
    store = get_store(hass)
    try:
        items = store.apply_template(msg["template_id"], msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"items": [i.to_dict() for i in items]})


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}history/recent",
        vol.Optional("limit", default=20): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)
@websocket_api.async_response
async def websocket_history_recent(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/history/recent``.

    Returns the most recently checked item names, most recent first
    (deduplicated).
    """
    store = get_store(hass)
    connection.send_result(
        msg["id"], {"items": store.recent_checked(msg["limit"])}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}history/repeat_last",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_history_repeat_last(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/history/repeat_last``.

    Copies the items of the most recently completed list into the list;
    returns the created (unchecked) items.
    """
    store = get_store(hass)
    try:
        items = store.repeat_last(msg["list_id"])
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"items": [i.to_dict() for i in items]})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = (
    websocket_templates_list,
    websocket_templates_create,
    websocket_templates_update,
    websocket_templates_delete,
    websocket_templates_apply,
    websocket_history_recent,
    websocket_history_repeat_last,
)
