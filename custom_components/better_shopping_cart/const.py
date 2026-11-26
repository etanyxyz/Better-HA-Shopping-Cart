"""Constants for the Better Shopping Cart integration."""
from __future__ import annotations

from typing import Any

DOMAIN = "better_shopping_cart"
VERSION = "0.1.0"

CONF_NAME = "name"

# Dispatcher signal fired after any mutating WebSocket command.
SIGNAL_UPDATED = f"{DOMAIN}_updated"

# Storage
STORAGE_KEY = "better_shopping_cart.json"
STORAGE_VERSION = 1


def default_data() -> dict[str, Any]:
    """Return a fresh default store payload (see PLAN.md §4)."""
    return {
        "version": STORAGE_VERSION,
        "sections": [],
        "layouts": [],
        "lists": [],
        "templates": [],
        "category_map": {},
        "settings": {
            "default_layout_id": None,
            "active_list_id": None,
            "hide_checked": False,
            "notify_on_add": False,
            "notify_service": "notify.notify",
        },
    }


# Default sections seeded on first run (M1): (name, mdi icon).
DEFAULT_SECTIONS: list[tuple[str, str]] = [
    ("Produce", "mdi:carrot"),
    ("Dairy", "mdi:milk"),
    ("Meat", "mdi:beef"),
    ("Bakery", "mdi:bread"),
    ("Frozen", "mdi:snowflake"),
    ("Drinks", "mdi:soda"),
    ("Household", "mdi:spray"),
    ("Other", "mdi:dots-triangle"),
]

# Built-in fallback dictionary: normalised item name -> section name
# (M1 fills this with ~80 common groceries).
DEFAULT_CATEGORY_MAP: dict[str, str] = {}
