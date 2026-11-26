"""Shared fixtures for Better Shopping Cart tests."""
from __future__ import annotations

import pytest

from custom_components.better_shopping_cart.store import BetterShoppingCartStore


@pytest.fixture
def store(hass) -> BetterShoppingCartStore:
    """A fresh in-memory Better Shopping Cart store (seeded on first load)."""
    return BetterShoppingCartStore(hass)
