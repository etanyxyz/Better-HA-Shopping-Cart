"""Data model for Smartcart (frozen contract, PLAN.md §4).

All IDs are ``uuid4().hex`` strings. Timestamps are ISO-8601 UTC strings.
Every dataclass implements ``to_dict`` and ``from_dict``; round-trip
serialization is unit-tested (M1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def new_id() -> str:
    """Generate a unique identifier (uuid4 hex)."""
    return uuid4().hex


def utc_now_iso() -> str:
    """Current time as an ISO-8601 UTC string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Section:
    """A supermarket section (aisle)."""

    id: str
    name: str
    icon: str = "mdi:cart"
    order: int = 0  # default ordering when no layout override

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the persisted store shape."""
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Section:
        """Build a Section from a persisted store entry."""
        return cls(
            id=data["id"],
            name=data["name"],
            icon=data.get("icon", "mdi:cart"),
            order=data.get("order", 0),
        )


@dataclass
class Layout:
    """A named store layout (walking order of sections)."""

    id: str
    name: str
    section_order: list[str] = field(default_factory=list)
    hidden_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the persisted store shape."""
        return {
            "id": self.id,
            "name": self.name,
            "section_order": list(self.section_order),
            "hidden_sections": list(self.hidden_sections),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Layout:
        """Build a Layout from a persisted store entry."""
        return cls(
            id=data["id"],
            name=data["name"],
            section_order=list(data.get("section_order", [])),
            hidden_sections=list(data.get("hidden_sections", [])),
        )


@dataclass
class Item:
    """A single item on a shopping list."""

    id: str
    name: str
    section_id: str
    quantity: float | None = None
    unit: str | None = None  # "kg", "x", "L", ...
    note: str | None = None
    checked: bool = False
    checked_at: str | None = None
    added_by: str | None = None  # HA user name
    created_at: str = ""  # set on create
    order: int = 0  # position within its section

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the persisted store shape."""
        return {
            "id": self.id,
            "name": self.name,
            "section_id": self.section_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "note": self.note,
            "checked": self.checked,
            "checked_at": self.checked_at,
            "added_by": self.added_by,
            "created_at": self.created_at,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Item:
        """Build an Item from a persisted store entry."""
        return cls(
            id=data["id"],
            name=data["name"],
            section_id=data["section_id"],
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            note=data.get("note"),
            checked=data.get("checked", False),
            checked_at=data.get("checked_at"),
            added_by=data.get("added_by"),
            created_at=data.get("created_at", ""),
            order=data.get("order", 0),
        )


@dataclass
class ShoppingList:
    """A named shopping list (also a native todo entity from M4 on)."""

    id: str
    name: str
    layout_id: str | None = None
    items: list[Item] = field(default_factory=list)
    created_at: str = ""
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the persisted store shape."""
        return {
            "id": self.id,
            "name": self.name,
            "layout_id": self.layout_id,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShoppingList:
        """Build a ShoppingList from a persisted store entry."""
        return cls(
            id=data["id"],
            name=data["name"],
            layout_id=data.get("layout_id"),
            items=[Item.from_dict(item) for item in data.get("items", [])],
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at"),
        )


@dataclass
class TemplateItem:
    """An item definition inside a list template."""

    name: str
    section_id: str
    quantity: float | None = None
    unit: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the persisted store shape."""
        return {
            "name": self.name,
            "section_id": self.section_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemplateItem:
        """Build a TemplateItem from a persisted store entry."""
        return cls(
            name=data["name"],
            section_id=data["section_id"],
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            note=data.get("note"),
        )


@dataclass
class Template:
    """A reusable set of items ("list template")."""

    id: str
    name: str
    items: list[TemplateItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the persisted store shape."""
        return {
            "id": self.id,
            "name": self.name,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Template:
        """Build a Template from a persisted store entry."""
        return cls(
            id=data["id"],
            name=data["name"],
            items=[TemplateItem.from_dict(item) for item in data.get("items", [])],
        )
