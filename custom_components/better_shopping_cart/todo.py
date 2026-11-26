"""To-do platform for Better Shopping Cart.

M0: stub so the todo platform forward resolves cleanly at load time.
M4: one ``TodoListEntity`` per shopping list (unique id = list id).
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the to-do platform (entities are added in M4)."""
