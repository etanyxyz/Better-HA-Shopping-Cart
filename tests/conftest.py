"""Shared fixtures for Better Shopping Cart tests."""
from __future__ import annotations

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.better_shopping_cart.const import DOMAIN
from custom_components.better_shopping_cart.store import BetterShoppingCartStore


@pytest.fixture
def store(hass) -> BetterShoppingCartStore:
    """A fresh in-memory Better Shopping Cart store (seeded on first load)."""
    return BetterShoppingCartStore(hass)


@pytest.fixture
async def bsc_entry(hass, enable_custom_integrations) -> MockConfigEntry:
    """A fully set up Better Shopping Cart config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test", title="Test Cart")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def bsc_ws(hass, hass_ws_client, bsc_entry):
    """An authenticated websocket client with the integration set up.

    Wraps the plugin ``hass_ws_client`` (real aiohttp connection to
    ``hass.http.app`` with the auth exchange already completed).
    """
    return await hass_ws_client(hass)
