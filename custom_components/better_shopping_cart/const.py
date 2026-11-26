"""Constants for the Better Shopping Cart integration."""
from __future__ import annotations

from typing import Any

DOMAIN = "better_shopping_cart"
VERSION = "0.1.5"

CONF_NAME = "name"

# Frontend panel (M5): the webcomponent name, its URL path and the
# cache-busted module URL (busted with the integration version so upgrades
# reload the module). Assets are served from frontend/ under /bsc/.
PANEL_URL_PATH = "shopping-cart"
PANEL_WEBCOMPONENT = "better-shopping-cart-panel"
PANEL_MODULE_URL = f"bsc/better-shopping-cart-panel.js?v={VERSION}"

# Dispatcher signal fired after any mutating WebSocket command.
SIGNAL_UPDATED = f"{DOMAIN}_updated"

# Storage
STORAGE_KEY = "better_shopping_cart.json"
STORAGE_VERSION = 1

# Section that receives items with no known category.
SECTION_UNCATEGORISED = "Uncategorised"

# Name of the layout seeded on first run.
DEFAULT_LAYOUT_NAME = "Weekly"

# Default settings (see PLAN.md §4 store shape).
DEFAULT_SETTINGS: dict[str, Any] = {
    "default_layout_id": None,
    "active_list_id": None,
    "hide_checked": False,
    "notify_on_add": False,
    "notify_service": "notify.notify",
}


def default_data() -> dict[str, Any]:
    """Return a fresh default store payload (see PLAN.md §4)."""
    return {
        "version": STORAGE_VERSION,
        "sections": [],
        "layouts": [],
        "lists": [],
        "templates": [],
        "category_map": {},
        "settings": dict(DEFAULT_SETTINGS),
    }


def normalise_name(name: str) -> str:
    """Normalise an item name for category lookups.

    Lower-cases, strips and collapses whitespace so "  Milk " matches "milk".
    """
    return " ".join(name.lower().split())


# Default sections seeded on first run: (name, mdi icon).
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

# Built-in fallback dictionary for auto-categorisation:
# normalised item name -> seeded section name (~80 common groceries).
# Learned user entries live in the persisted store's category_map and take
# precedence over this map (see PLAN.md §5).
DEFAULT_CATEGORY_MAP: dict[str, str] = {
    # Produce
    "apple": "Produce",
    "banana": "Produce",
    "orange": "Produce",
    "pear": "Produce",
    "grape": "Produce",
    "strawberry": "Produce",
    "blueberry": "Produce",
    "tomato": "Produce",
    "cucumber": "Produce",
    "carrot": "Produce",
    "potato": "Produce",
    "onion": "Produce",
    "garlic": "Produce",
    "lettuce": "Produce",
    "broccoli": "Produce",
    "mushroom": "Produce",
    # Dairy
    "milk": "Dairy",
    "eggs": "Dairy",
    "butter": "Dairy",
    "cheese": "Dairy",
    "cheddar": "Dairy",
    "mozzarella": "Dairy",
    "yogurt": "Dairy",
    "yoghurt": "Dairy",
    "cream": "Dairy",
    # Meat
    "chicken": "Meat",
    "chicken breast": "Meat",
    "chicken thigh": "Meat",
    "beef": "Meat",
    "minced beef": "Meat",
    "ground beef": "Meat",
    "pork": "Meat",
    "bacon": "Meat",
    "sausage": "Meat",
    "ham": "Meat",
    "turkey": "Meat",
    # Bakery
    "bread": "Bakery",
    "baguette": "Bakery",
    "rolls": "Bakery",
    "buns": "Bakery",
    "croissant": "Bakery",
    "muffin": "Bakery",
    "bagel": "Bakery",
    "flour": "Bakery",
    "tortilla": "Bakery",
    "pasta": "Bakery",
    # Frozen
    "pizza": "Frozen",
    "ice cream": "Frozen",
    "frozen peas": "Frozen",
    "frozen vegetables": "Frozen",
    "fish sticks": "Frozen",
    "fish fingers": "Frozen",
    "frozen berries": "Frozen",
    # Drinks
    "water": "Drinks",
    "sparkling water": "Drinks",
    "cola": "Drinks",
    "juice": "Drinks",
    "coffee": "Drinks",
    "tea": "Drinks",
    "beer": "Drinks",
    "wine": "Drinks",
    "soft drink": "Drinks",
    # Household
    "toilet paper": "Household",
    "paper towels": "Household",
    "washing powder": "Household",
    "detergent": "Household",
    "dish soap": "Household",
    "bin bags": "Household",
    "foil": "Household",
    "cling film": "Household",
    "hand soap": "Household",
    # Other
    "cereal": "Other",
    "granola": "Other",
    "oats": "Other",
    "honey": "Other",
    "jam": "Other",
    "peanut butter": "Other",
    "chocolate": "Other",
    "chips": "Other",
    "biscuits": "Other",
    "ketchup": "Other",
    "mayonnaise": "Other",
    "olive oil": "Other",
}
