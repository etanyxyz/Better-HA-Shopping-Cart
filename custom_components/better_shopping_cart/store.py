"""Persistence, read access and categorisation (PLAN.md M1).

``BetterShoppingCartStore`` wraps ``homeassistant.helpers.storage.Store`` and
keeps the in-memory payload in the frozen store shape (PLAN.md §4). Mutating
CRUD helpers live in ``crud.py`` (mixed in via ``Crud``). CRUD helpers mutate
the payload only; the caller (WebSocket layer from M2 on) must
``await async_save()`` and fire the dispatcher signal.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from . import models
from .const import (
    DEFAULT_CATEGORY_MAP,
    DEFAULT_LAYOUT_NAME,
    DEFAULT_SECTIONS,
    DEFAULT_SECTION_ICONS,
    DEFAULT_SETTINGS,
    SECTION_UNCATEGORISED,
    STORAGE_KEY,
    STORAGE_VERSION,
    default_data,
    normalise_name,
)
from .crud import Crud
from .models import Item, Layout, Section, ShoppingList, Template

_LOGGER = logging.getLogger(__name__)


class BetterShoppingCartStore(Crud):
    """Load, save and expose the Better Shopping Cart data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store wrapper."""
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None

    @property
    def data(self) -> dict[str, Any]:
        """Return the in-memory store payload."""
        if self._data is None:
            self._data = default_data()
        return self._data

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load data from disk, seeding defaults on first run."""
        try:
            stored = await self._store.async_load()
        except Exception:  # noqa: BLE001 - a corrupt file must not break setup
            _LOGGER.warning("Could not load %s; starting with defaults", STORAGE_KEY)
            stored = None
        if stored is None:
            self._data = self._seed()
        elif stored.get("version") != STORAGE_VERSION:
            _LOGGER.warning(
                "Store version %s does not match %s; starting with defaults",
                stored.get("version"),
                STORAGE_VERSION,
            )
            self._data = self._seed()
        else:
            self._data = stored
            if (
                self._migrate_default_sections()
                or self._migrate_layout_hidden_sections()
            ):
                await self.async_save()

    async def async_save(self) -> None:
        """Persist the in-memory payload to disk."""
        await self._store.async_save(self.data)

    def _seed(self) -> dict[str, Any]:
        """Build the first-run payload: default sections, layout, category map."""
        data = default_data()
        section_id_by_name: dict[str, str] = {}
        for order, (name, icon) in enumerate(DEFAULT_SECTIONS):
            section_id = models.new_id()
            section_id_by_name[name] = section_id
            data["sections"].append(
                {"id": section_id, "name": name, "icon": icon, "order": order}
            )
        data["layouts"].append(
            {
                "id": models.new_id(),
                "name": DEFAULT_LAYOUT_NAME,
                "section_order": [s["id"] for s in data["sections"]],
                "hidden_sections": [],
            }
        )
        fallback = section_id_by_name.get("Other")
        for item_name, section_name in DEFAULT_CATEGORY_MAP.items():
            data["category_map"][normalise_name(item_name)] = (
                section_id_by_name.get(section_name) or fallback
            )
        return data

    def _migrate_default_sections(self) -> bool:
        """Normalise the immutable default sections (NOTES: Sections tab).

        Default sections are identified by name: an existing default keeps
        its id, regains its canonical icon and fixed position (its index in
        DEFAULT_SECTIONS); a missing default is re-added. Custom sections
        keep their ids and relative order and are renumbered contiguously
        after the defaults, so the stored order is always "defaults first,
        then customs". Returns True when the payload changed.
        """
        by_name = {
            normalise_name(entry["name"]): entry for entry in self.data["sections"]
        }
        changed = False
        for order, (name, icon) in enumerate(DEFAULT_SECTIONS):
            entry = by_name.get(normalise_name(name))
            if entry is None:
                self.data["sections"].append(
                    {
                        "id": models.new_id(),
                        "name": name,
                        "icon": icon,
                        "order": order,
                    }
                )
                changed = True
            elif entry["icon"] != icon or entry["order"] != order:
                entry["icon"] = icon
                entry["order"] = order
                changed = True
        customs = sorted(
            (
                entry
                for entry in self.data["sections"]
                if normalise_name(entry["name"]) not in DEFAULT_SECTION_ICONS
            ),
            key=lambda entry: entry["order"],
        )
        for offset, entry in enumerate(customs):
            if entry["order"] != len(DEFAULT_SECTIONS) + offset:
                entry["order"] = len(DEFAULT_SECTIONS) + offset
                changed = True
        if changed:
            _LOGGER.info("Migrated shopping cart sections to the default set")
        return changed

    def _migrate_layout_hidden_sections(self) -> bool:
        """Clear every layout's hidden sections (NOTES: Layouts tab).

        The "Hidden sections" UI is gone: removing a section from a layout is
        the only way to keep it out of the view, so stored hidden lists would
        be invisible leftovers with no way to restore them. Returns True when
        the payload changed.
        """
        changed = False
        for layout in self.data["layouts"]:
            if layout.get("hidden_sections"):
                layout["hidden_sections"] = []
                changed = True
        if changed:
            _LOGGER.info(
                "Migrated shopping cart layouts (cleared hidden sections)"
            )
        return changed

    # ------------------------------------------------------------------
    # Read access
    # ------------------------------------------------------------------

    def sections(self) -> list[Section]:
        """Return all sections in default order."""
        return sorted(
            (Section.from_dict(s) for s in self.data["sections"]), key=lambda s: s.order
        )

    def section(self, section_id: str) -> Section | None:
        """Return one section by id."""
        for entry in self.data["sections"]:
            if entry["id"] == section_id:
                return Section.from_dict(entry)
        return None

    def layouts(self) -> list[Layout]:
        """Return all layouts."""
        return [Layout.from_dict(l) for l in self.data["layouts"]]

    def layout(self, layout_id: str) -> Layout | None:
        """Return one layout by id."""
        for entry in self.data["layouts"]:
            if entry["id"] == layout_id:
                return Layout.from_dict(entry)
        return None

    def lists(self) -> list[ShoppingList]:
        """Return all shopping lists."""
        return [ShoppingList.from_dict(l) for l in self.data["lists"]]

    def shopping_list(self, list_id: str) -> ShoppingList | None:
        """Return one shopping list by id."""
        for entry in self.data["lists"]:
            if entry["id"] == list_id:
                return ShoppingList.from_dict(entry)
        return None

    def items(self, list_id: str) -> list[Item]:
        """Return the items of a list (in stored order)."""
        entry = self._find("lists", list_id)
        return [Item.from_dict(i) for i in entry["items"]]

    def item(self, list_id: str, item_id: str) -> Item | None:
        """Return one item of a list."""
        entry = self._find("lists", list_id)
        for item in entry["items"]:
            if item["id"] == item_id:
                return Item.from_dict(item)
        return None

    def templates(self) -> list[Template]:
        """Return all templates."""
        return [Template.from_dict(t) for t in self.data["templates"]]

    def template(self, template_id: str) -> Template | None:
        """Return one template by id."""
        for entry in self.data["templates"]:
            if entry["id"] == template_id:
                return Template.from_dict(entry)
        return None

    def settings(self) -> dict[str, Any]:
        """Return the current settings."""
        return self.data["settings"]

    def category_map(self) -> dict[str, str]:
        """Return the learned category map (normalised name -> section id)."""
        return self.data["category_map"]

    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        """Update settings (the WebSocket layer validates the keys)."""
        self.data["settings"].update(values)
        return self.data["settings"]

    # ------------------------------------------------------------------
    # Auto-categorisation (PLAN.md §5)
    # ------------------------------------------------------------------

    def categorise(self, name: str, section_id: str | None = None) -> str:
        """Resolve the section id for an item name (PLAN.md §5 rule).

        An explicit valid section id wins, then the learned category map, then
        the built-in dictionary, else the "Uncategorised" section.
        """
        if section_id and self.section(section_id) is not None:
            return section_id
        normalised = normalise_name(name)
        learned = self.data["category_map"].get(normalised)
        if learned and self.section(learned) is not None:
            return learned
        section_name = DEFAULT_CATEGORY_MAP.get(normalised)
        if section_name:
            for entry in self.data["sections"]:
                if entry["name"] == section_name:
                    return entry["id"]
        return self._ensure_uncategorised()

    def learn_category(self, name: str, section_id: str) -> None:
        """Record the user's section choice for an item name."""
        if self.section(section_id) is not None:
            self.data["category_map"][normalise_name(name)] = section_id

    def _ensure_uncategorised(self) -> str:
        """Return (creating if needed) the fallback section for items."""
        for entry in self.data["sections"]:
            if entry["name"] == SECTION_UNCATEGORISED:
                return entry["id"]
        entry: dict[str, Any] = {
            "id": models.new_id(),
            "name": SECTION_UNCATEGORISED,
            "icon": DEFAULT_SECTION_ICONS[normalise_name(SECTION_UNCATEGORISED)],
            "order": len(self.data["sections"]),
        }
        self.data["sections"].append(entry)
        return entry["id"]
