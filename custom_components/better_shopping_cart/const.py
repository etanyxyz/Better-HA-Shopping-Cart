"""Constants for the Smartcart integration."""
from __future__ import annotations

from typing import Any

DOMAIN = "better_shopping_cart"
VERSION = "1.0.3"

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


# Default sections (NOTES: Sections tab): the immutable set, seeded on first
# run and restored by the load-time migration. Each default section keeps a
# unique canonical icon; icons must render in the HA frontend's bundled MDI
# set (e.g. mdi:milk does not).
DEFAULT_SECTIONS: list[tuple[str, str]] = [
    ("Produce", "mdi:carrot"),
    ("Dairy", "mdi:cheese"),
    ("Meat", "mdi:cow"),
    ("Bakery", "mdi:baguette"),
    ("Frozen", "mdi:snowflake"),
    ("Drinks", "mdi:glass-mug"),
    ("Household", "mdi:spray"),
    ("Pantry", "mdi:package-variant"),
    ("Other", "mdi:dots-triangle"),
    ("Uncategorised", "mdi:help-circle"),
]

# Normalised name -> canonical icon of the immutable default sections.
# A section whose normalised name is a key here is a default section: it
# cannot be created, deleted, renamed, reordered or re-iconed.
DEFAULT_SECTION_ICONS: dict[str, str] = {
    normalise_name(name): icon for name, icon in DEFAULT_SECTIONS
}
DEFAULT_SECTION_NAMES: frozenset[str] = frozenset(DEFAULT_SECTION_ICONS)

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
