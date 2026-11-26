"""WebSocket API for Better Shopping Cart.

M0: stub. M2 adds the ``sections/*`` and ``layouts/*`` commands, M3 adds
``lists/*``, ``items/*``, ``templates/*``, ``history/*``, ``settings/*`` and
``subscribe``. All commands use the ``better_shopping_cart/`` type prefix
(frozen contract, see PLAN.md §5).
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant


async def async_register(hass: HomeAssistant) -> None:
    """Register the integration's WebSocket commands."""
    # Commands are registered here from M2 onwards, e.g.:
    # websocket_api.async_register_command(hass, websocket_handle_sections_create)
