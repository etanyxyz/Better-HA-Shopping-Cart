"""HA service tests for add_item / complete_list (PLAN.md M9).

The services mirror the store CRUD for automations, scripts and Assist:
lists and sections are referenced by name (case-insensitive).
"""
from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.better_shopping_cart.const import (
    DOMAIN,
    SIGNAL_UPDATED,
)
from custom_components.better_shopping_cart.store import BetterShoppingCartStore


@pytest.fixture
def cart(hass, bsc_entry) -> BetterShoppingCartStore:
    """The store attached to the running config entry."""
    return hass.data[DOMAIN]


async def test_add_item_service(cart, hass):
    """add_item adds to the list by name (case-insensitive)."""
    cart.create_list("Weekly Shop")
    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {
            "name": "Whole Milk",
            "list": "weekly shop",
            "section": "dairy",
            "quantity": 2,
            "unit": "L",
        },
        blocking=True,
    )
    shopping_list = cart.lists()[0]
    assert len(shopping_list.items) == 1
    item = shopping_list.items[0]
    assert item.name == "Whole Milk"
    dairy = next(section for section in cart.sections() if section.name == "Dairy")
    assert item.section_id == dairy.id
    assert item.quantity == 2
    assert item.unit == "L"


async def test_add_item_service_auto_categorises(cart, hass):
    """Without a section the item is auto-categorised like the WS path."""
    cart.create_list("Weekly Shop")
    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"name": "Milk", "list": "Weekly Shop"},
        blocking=True,
    )
    item = cart.lists()[0].items[0]
    dairy = next(section for section in cart.sections() if section.name == "Dairy")
    assert item.section_id == dairy.id


async def test_add_item_service_fires_update_signal(cart, hass):
    """The service commits, so the {DOMAIN}_updated signal fires."""
    fired = []
    async_dispatcher_connect(hass, SIGNAL_UPDATED, lambda: fired.append(1))
    cart.create_list("Weekly Shop")
    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"name": "Milk", "list": "Weekly Shop"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(fired) == 1


async def test_add_item_service_unknown_list(cart, hass):
    cart.create_list("Weekly Shop")
    with pytest.raises(HomeAssistantError, match="unknown list"):
        await hass.services.async_call(
            DOMAIN,
            "add_item",
            {"name": "Milk", "list": "Nope"},
            blocking=True,
        )


async def test_add_item_service_unknown_section(cart, hass):
    cart.create_list("Weekly Shop")
    with pytest.raises(HomeAssistantError, match="unknown section"):
        await hass.services.async_call(
            DOMAIN,
            "add_item",
            {"name": "Milk", "list": "Weekly Shop", "section": "Nope"},
            blocking=True,
        )


async def test_add_item_service_requires_name(cart, hass):
    cart.create_list("Weekly Shop")
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_item",
            {"list": "Weekly Shop"},
            blocking=True,
        )


async def test_complete_list_service(cart, hass):
    shopping_list = cart.create_list("Weekly Shop")
    await hass.services.async_call(
        DOMAIN, "complete_list", {"list": "weekly shop"}, blocking=True
    )
    assert cart.shopping_list(shopping_list.id).completed_at is not None


async def test_complete_list_service_unknown_list(cart, hass):
    with pytest.raises(HomeAssistantError, match="unknown list"):
        await hass.services.async_call(
            DOMAIN, "complete_list", {"list": "Nope"}, blocking=True
        )


async def test_services_removed_on_unload(cart, hass, bsc_entry):
    """Unloading the entry unregisters both services."""
    assert hass.services.has_service(DOMAIN, "add_item")
    assert hass.services.has_service(DOMAIN, "complete_list")
    assert await hass.config_entries.async_unload(bsc_entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "add_item")
    assert not hass.services.has_service(DOMAIN, "complete_list")
