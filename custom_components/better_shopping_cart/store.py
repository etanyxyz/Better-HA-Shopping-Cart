"""Persistence for Better Shopping Cart.

M0: thin wrapper around Home Assistant's ``Store`` that loads and saves the
raw store payload. M1 adds first-run seeding and the CRUD helpers.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION, default_data

_LOGGER = logging.getLogger(__name__)


class BetterShoppingCartStore:
    """Load, save and expose the Better Shopping Cart data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store wrapper."""
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = default_data()

    @property
    def data(self) -> dict[str, Any]:
        """Return the in-memory store payload."""
        return self._data

    async def async_load(self) -> None:
        """Load data from disk, keeping defaults when missing or corrupt."""
        try:
            stored = await self._store.async_load()
        except Exception:  # noqa: BLE001 - a corrupt file must not break setup
            _LOGGER.warning("Could not load %s; starting with defaults", STORAGE_KEY)
            return
        if stored is not None:
            self._data = stored

    async def async_save(self) -> None:
        """Persist the in-memory payload to disk."""
        await self._store.async_save(self._data)
