"""WebSocket commands for settings and subscribe (PLAN.md §5, M3).

Every mutating command saves the store and fires the ``{DOMAIN}_updated``
dispatcher signal (via ``commit``). Store-level ``ValueError`` (unknown
ids) is mapped to a ``home_assistant_error`` WebSocket error response.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATED
from .ws_common import _ID, _TYPE, Msg, as_error, commit, get_store

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@websocket_api.websocket_command(
    {vol.Required("type"): f"{_TYPE}settings/get"}
)
@websocket_api.async_response
async def websocket_settings_get(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/settings/get``."""
    store = get_store(hass)
    connection.send_result(msg["id"], {"settings": store.settings()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}settings/update",
        vol.Optional("default_layout_id"): _ID,
        vol.Optional("active_list_id"): _ID,
        vol.Optional("hide_checked"): cv.boolean,
        vol.Optional("notify_on_add"): cv.boolean,
        vol.Optional("notify_service"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_settings_update(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/settings/update``.

    Only the known settings keys are accepted (unknown keys are rejected
    as invalid format); ``default_layout_id`` / ``active_list_id`` must
    reference an existing layout/list (``null`` clears them).
    """
    store = get_store(hass)
    try:
        layout_id = msg.get("default_layout_id")
        if layout_id is not None and store.layout(layout_id) is None:
            raise ValueError(f"unknown layout: {layout_id}")
        active_list_id = msg.get("active_list_id")
        if (
            active_list_id is not None
            and store.shopping_list(active_list_id) is None
        ):
            raise ValueError(f"unknown list: {active_list_id}")
        settings = store.update_settings(
            {key: value for key, value in msg.items() if key != "type"}
        )
    except ValueError as err:
        raise as_error(err) from err
    await commit(hass, store)
    connection.send_result(msg["id"], {"settings": settings})


# ---------------------------------------------------------------------------
# Subscribe
# ---------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{_TYPE}subscribe",
        vol.Required("list_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: Msg,
) -> None:
    """Handle ``better_shopping_cart/subscribe``.

    Streams the ``better_shopping_cart/updated`` event message whenever the
    store changes (any mutating command). The subscription is torn down
    automatically when the connection closes.
    """
    store = get_store(hass)
    if store.shopping_list(msg["list_id"]) is None:
        raise as_error(ValueError(f"unknown list: {msg['list_id']}"))

    @callback
    def on_update() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], f"{DOMAIN}/updated")
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_UPDATED, on_update
    )
    connection.send_result(msg["id"])


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = (
    websocket_settings_get,
    websocket_settings_update,
    websocket_subscribe,
)
