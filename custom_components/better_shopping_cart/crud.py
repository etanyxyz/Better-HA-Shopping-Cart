"""CRUD helpers for the Better Shopping Cart store (PLAN.md M1).

``Crud`` holds the mutating operations on the frozen store shape (PLAN.md §4).
It is mixed into ``BetterShoppingCartStore`` (see ``store.py``) and operates on
``self.data``; callers must ``await store.async_save()`` after mutations.
Unknown ids raise ``ValueError`` (mapped to WebSocket errors from M2 on).
"""
from __future__ import annotations

from typing import Any

from . import models
from .models import Item, Layout, Section, ShoppingList, Template, TemplateItem

# Sentinel: "field not provided" for update helpers (None has meaning of its own).
_UNCHANGED = object()


class Crud:
    """Mutating store operations (mixed into BetterShoppingCartStore)."""

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def create_section(self, name: str, icon: str | None = None) -> Section:
        """Create a section at the end of the default order."""
        entry: dict[str, Any] = {
            "id": models.new_id(),
            "name": name,
            "icon": icon or "mdi:cart",
            "order": max((s["order"] for s in self.data["sections"]), default=-1) + 1,
        }
        self.data["sections"].append(entry)
        return Section.from_dict(entry)

    def update_section(
        self, section_id: str, *, name: str | None = None, icon: str | None = None
    ) -> Section:
        """Update the name and/or icon of a section."""
        entry = self._find("sections", section_id)
        if name is not None:
            entry["name"] = name
        if icon is not None:
            entry["icon"] = icon
        return Section.from_dict(entry)

    def delete_section(self, section_id: str) -> None:
        """Delete a section.

        Items in it move to "Other" (or the first remaining section when
        "Other" itself is deleted); layout references are cleaned up.
        """
        entry = self._find("sections", section_id)
        remaining = [s for s in self.data["sections"] if s["id"] != section_id]
        target = next(
            (s for s in remaining if s["name"] == "Other"),
            remaining[0] if remaining else None,
        )
        if target is not None:
            for lst in self.data["lists"]:
                for item in lst["items"]:
                    if item["section_id"] == section_id:
                        item["section_id"] = target["id"]
        for layout in self.data["layouts"]:
            layout["section_order"] = [
                i for i in layout["section_order"] if i != section_id
            ]
            layout["hidden_sections"] = [
                i for i in layout["hidden_sections"] if i != section_id
            ]
        self.data["sections"].remove(entry)

    def reorder_sections(self, ordered_ids: list[str]) -> None:
        """Set the default order from a full or partial id list.

        Unknown ids are ignored; the remaining sections keep their relative
        order and are renumbered contiguously.
        """
        by_id = {s["id"]: s for s in self.data["sections"]}
        known = [i for i in ordered_ids if i in by_id]
        for position, section_id in enumerate(known):
            by_id[section_id]["order"] = position

    # ------------------------------------------------------------------
    # Layouts
    # ------------------------------------------------------------------

    def create_layout(self, name: str) -> Layout:
        """Create a layout with the current section order."""
        entry: dict[str, Any] = {
            "id": models.new_id(),
            "name": name,
            "section_order": [s["id"] for s in self.data["sections"]],
            "hidden_sections": [],
        }
        self.data["layouts"].append(entry)
        return Layout.from_dict(entry)

    def update_layout(
        self,
        layout_id: str,
        *,
        name: str | None = None,
        section_order: list[str] | None = None,
        hidden_sections: list[str] | None = None,
    ) -> Layout:
        """Update the name and/or section order of a layout."""
        entry = self._find("layouts", layout_id)
        if name is not None:
            entry["name"] = name
        if section_order is not None:
            entry["section_order"] = list(section_order)
        if hidden_sections is not None:
            entry["hidden_sections"] = list(hidden_sections)
        return Layout.from_dict(entry)

    def delete_layout(self, layout_id: str) -> None:
        """Delete a layout and clear references to it."""
        entry = self._find("layouts", layout_id)
        for lst in self.data["lists"]:
            if lst["layout_id"] == layout_id:
                lst["layout_id"] = None
        if self.data["settings"]["default_layout_id"] == layout_id:
            self.data["settings"]["default_layout_id"] = None
        self.data["layouts"].remove(entry)

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def create_list(self, name: str, layout_id: str | None = None) -> ShoppingList:
        """Create an empty shopping list."""
        if layout_id is not None:
            self._find("layouts", layout_id)
        entry: dict[str, Any] = {
            "id": models.new_id(),
            "name": name,
            "layout_id": layout_id,
            "items": [],
            "created_at": models.utc_now_iso(),
            "completed_at": None,
        }
        self.data["lists"].append(entry)
        return ShoppingList.from_dict(entry)

    def update_list(
        self,
        list_id: str,
        *,
        name: str | None = None,
        layout_id: str | None = _UNCHANGED,
    ) -> ShoppingList:
        """Rename a list and/or change its layout.

        ``layout_id`` omitted leaves the layout untouched; ``layout_id=None``
        clears it (matching the ``lists/update`` WebSocket contract, §5).
        """
        entry = self._find("lists", list_id)
        if name is not None:
            entry["name"] = name
        if layout_id is not _UNCHANGED:
            if layout_id is not None:
                self._find("layouts", layout_id)
            entry["layout_id"] = layout_id
        return ShoppingList.from_dict(entry)

    def delete_list(self, list_id: str) -> None:
        """Delete a shopping list and its items."""
        entry = self._find("lists", list_id)
        self.data["lists"].remove(entry)

    def complete_list(self, list_id: str) -> ShoppingList:
        """Mark a list as completed (used by history/repeat_last)."""
        entry = self._find("lists", list_id)
        entry["completed_at"] = models.utc_now_iso()
        return ShoppingList.from_dict(entry)

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def add_item(
        self,
        list_id: str,
        name: str,
        *,
        section_id: str | None = None,
        quantity: float | None = None,
        unit: str | None = None,
        note: str | None = None,
        added_by: str | None = None,
    ) -> Item:
        """Add an item; without ``section_id`` it is auto-categorised."""
        entry = self._find("lists", list_id)
        sid = self.categorise(name, section_id)
        in_section = max(
            (i["order"] for i in entry["items"] if i["section_id"] == sid), default=-1
        )
        item: dict[str, Any] = {
            "id": models.new_id(),
            "name": name,
            "section_id": sid,
            "quantity": quantity,
            "unit": unit,
            "note": note,
            "checked": False,
            "checked_at": None,
            "added_by": added_by,
            "created_at": models.utc_now_iso(),
            "order": in_section + 1,
        }
        entry["items"].append(item)
        return Item.from_dict(item)

    def update_item(
        self,
        list_id: str,
        item_id: str,
        *,
        name: str | None = None,
        section_id: str | None = None,
        quantity: float | None = None,
        unit: str | None = None,
        note: str | None = None,
        clear_note: bool = False,
    ) -> Item:
        """Update item fields; moving to a new section teaches the map.

        ``note=None`` leaves the note untouched; ``clear_note=True`` clears
        it (used by the todo platform, where clearing the description means
        clearing the note).
        """
        item_entry = self._find_item(list_id, item_id)
        if name is not None:
            item_entry["name"] = name
        if section_id is not None and section_id != item_entry["section_id"]:
            self._find("sections", section_id)
            item_entry["section_id"] = section_id
            self.learn_category(item_entry["name"], section_id)
        if quantity is not None:
            item_entry["quantity"] = quantity
        if unit is not None:
            item_entry["unit"] = unit
        if clear_note:
            item_entry["note"] = None
        elif note is not None:
            item_entry["note"] = note
        return Item.from_dict(item_entry)

    def check_item(self, list_id: str, item_id: str, checked: bool) -> Item:
        """Tick or untick an item."""
        item_entry = self._find_item(list_id, item_id)
        item_entry["checked"] = checked
        item_entry["checked_at"] = models.utc_now_iso() if checked else None
        return Item.from_dict(item_entry)

    def delete_item(self, list_id: str, item_id: str) -> None:
        """Delete an item from a list."""
        entry = self._find("lists", list_id)
        entry["items"].remove(self._find_item(list_id, item_id))

    def reorder_items(self, list_id: str, ordered_ids: list[str]) -> None:
        """Assign item order from a list of item ids (per-list).

        Unknown ids are ignored; the remaining items keep their relative
        order and are renumbered contiguously.
        """
        entry = self._find("lists", list_id)
        by_id = {i["id"]: i for i in entry["items"]}
        known = [i for i in ordered_ids if i in by_id]
        for position, item_id in enumerate(known):
            by_id[item_id]["order"] = position

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def create_template(
        self, name: str, items: list[TemplateItem | dict[str, Any]]
    ) -> Template:
        """Create a template from model items or raw item dicts."""
        entry: dict[str, Any] = {
            "id": models.new_id(),
            "name": name,
            "items": [self._to_template_item(i).to_dict() for i in items],
        }
        self.data["templates"].append(entry)
        return Template.from_dict(entry)

    def update_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        items: list[TemplateItem | dict[str, Any]] | None = None,
    ) -> Template:
        """Rename a template and/or replace its items."""
        entry = self._find("templates", template_id)
        if name is not None:
            entry["name"] = name
        if items is not None:
            entry["items"] = [self._to_template_item(i).to_dict() for i in items]
        return Template.from_dict(entry)

    def delete_template(self, template_id: str) -> None:
        """Delete a template."""
        entry = self._find("templates", template_id)
        self.data["templates"].remove(entry)

    def apply_template(self, template_id: str, list_id: str) -> list[Item]:
        """Add all template items to a list; returns the created items."""
        tpl = self.template(template_id)
        if tpl is None:
            raise ValueError(f"unknown template: {template_id}")
        self._find("lists", list_id)
        return [
            self.add_item(
                list_id,
                item.name,
                section_id=item.section_id,
                quantity=item.quantity,
                unit=item.unit,
                note=item.note,
            )
            for item in tpl.items
        ]

    # ------------------------------------------------------------------
    # History (M3)
    # ------------------------------------------------------------------

    def recent_checked(self, limit: int = 20) -> list[str]:
        """Return the most recently checked item names, most recent first.

        Names are deduplicated so each appears at most once.
        """
        checked: list[tuple[str, str]] = []
        for lst in self.data["lists"]:
            for item in lst["items"]:
                if item.get("checked_at"):
                    checked.append((item["checked_at"], item["name"]))
        checked.sort(key=lambda pair: pair[0], reverse=True)
        names: list[str] = []
        for _, name in checked:
            if name not in names:
                names.append(name)
            if len(names) >= limit:
                break
        return names

    def repeat_last(self, list_id: str) -> list[Item]:
        """Copy the items of the most recently completed list into a list.

        The source list keeps its completion state; copied items start
        unchecked. Returns the created items (empty when no list has been
        completed yet).
        """
        self._find("lists", list_id)
        completed = [
            lst
            for lst in self.data["lists"]
            if lst["id"] != list_id and lst.get("completed_at")
        ]
        if not completed:
            return []
        source = max(completed, key=lambda lst: lst["completed_at"])
        return [
            self.add_item(
                list_id,
                item["name"],
                section_id=item.get("section_id"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                note=item.get("note"),
            )
            for item in source["items"]
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _to_template_item(
        self, item: TemplateItem | dict[str, Any]
    ) -> TemplateItem:
        """Normalise a template item argument to a model."""
        return item if isinstance(item, TemplateItem) else TemplateItem.from_dict(item)

    def _find(self, key: str, entry_id: str) -> dict[str, Any]:
        """Return a raw store entry by id, raising ValueError when missing."""
        entry = next((e for e in self.data[key] if e["id"] == entry_id), None)
        if entry is None:
            raise ValueError(f"unknown {key[:-1]}: {entry_id}")
        return entry

    def _find_item(self, list_id: str, item_id: str) -> dict[str, Any]:
        """Return a raw item entry, raising ValueError when missing."""
        entry = self._find("lists", list_id)
        item_entry = next((i for i in entry["items"] if i["id"] == item_id), None)
        if item_entry is None:
            raise ValueError(f"unknown item: {item_id}")
        return item_entry
