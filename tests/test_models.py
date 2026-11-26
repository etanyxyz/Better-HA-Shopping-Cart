"""Unit tests for the data model (PLAN.md §4): serialization round-trips."""
from __future__ import annotations

from datetime import datetime

from custom_components.better_shopping_cart.models import (
    Item,
    Layout,
    Section,
    ShoppingList,
    Template,
    TemplateItem,
    new_id,
    utc_now_iso,
)


def test_section_roundtrip_defaults():
    section = Section(id="s1", name="Produce")
    assert Section.from_dict(section.to_dict()) == section
    assert section.icon == "mdi:cart"
    assert section.order == 0


def test_section_roundtrip_full():
    section = Section(id="s1", name="Dairy", icon="mdi:milk", order=3)
    assert Section.from_dict(section.to_dict()) == section


def test_layout_roundtrip():
    layout = Layout(
        id="l1",
        name="Tesco",
        section_order=["s1", "s2"],
        hidden_sections=["s3"],
    )
    assert Layout.from_dict(layout.to_dict()) == layout


def test_item_roundtrip_defaults():
    item = Item(id="i1", name="Milk", section_id="s1")
    assert Item.from_dict(item.to_dict()) == item
    assert item.checked is False
    assert item.checked_at is None
    assert item.created_at == ""
    assert item.order == 0


def test_item_roundtrip_full():
    item = Item(
        id="i1",
        name="Potatoes",
        section_id="s2",
        quantity=2.0,
        unit="kg",
        note="the big ones",
        checked=True,
        checked_at="2026-11-26T10:00:00+00:00",
        added_by="etany",
        created_at="2026-11-26T09:00:00+00:00",
        order=4,
    )
    assert Item.from_dict(item.to_dict()) == item


def test_shopping_list_roundtrip_nested():
    lst = ShoppingList(
        id="lst1",
        name="Weekly",
        layout_id="l1",
        items=[
            Item(id="i1", name="Milk", section_id="s1"),
            Item(id="i2", name="Bread", section_id="s2", quantity=1.0, unit="x"),
        ],
        created_at="2026-11-26T09:00:00+00:00",
    )
    restored = ShoppingList.from_dict(lst.to_dict())
    assert restored == lst
    assert restored.items[0].id == "i1"
    assert restored.items[1].quantity == 1.0


def test_template_roundtrip_nested():
    tpl = Template(
        id="t1",
        name="Weekly basics",
        items=[
            TemplateItem(name="Milk", section_id="s1", quantity=2.0, unit="L"),
            TemplateItem(name="Bread", section_id="s2"),
        ],
    )
    restored = Template.from_dict(tpl.to_dict())
    assert restored == tpl
    assert restored.items[0].quantity == 2.0


def test_from_dict_missing_optional_keys():
    assert Section.from_dict({"id": "a", "name": "X"}) == Section(id="a", name="X")
    assert Layout.from_dict({"id": "a", "name": "X"}) == Layout(id="a", name="X")
    assert Item.from_dict(
        {"id": "a", "name": "X", "section_id": "s"}
    ) == Item(id="a", name="X", section_id="s")
    assert ShoppingList.from_dict({"id": "a", "name": "X"}) == ShoppingList(
        id="a", name="X"
    )
    assert Template.from_dict({"id": "a", "name": "X"}) == Template(id="a", name="X")
    assert TemplateItem.from_dict(
        {"name": "X", "section_id": "s"}
    ) == TemplateItem(name="X", section_id="s")


def test_from_dict_copies_lists():
    """from_dict must not alias the input's lists (mutations stay isolated)."""
    raw = {"id": "l1", "name": "Tesco", "section_order": ["s1"], "hidden_sections": []}
    layout = Layout.from_dict(raw)
    layout.section_order.append("s2")
    assert raw["section_order"] == ["s1"]


def test_new_id_is_unique_hex32():
    ids = {new_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(i) == 32 for i in ids)


def test_utc_now_iso_is_parseable_utc():
    ts = utc_now_iso()
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
    assert ts.endswith("+00:00")
