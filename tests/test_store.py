"""Unit tests for the store layer (PLAN.md M1).

Uses the HA test harness ``hass`` fixture (pytest-homeassistant-custom-component)
so the real ``Store`` persistence helper runs against a temporary config dir.
"""
from __future__ import annotations

import json

import pytest

from custom_components.better_shopping_cart.const import (
    DEFAULT_CATEGORY_MAP,
    DEFAULT_LAYOUT_NAME,
    DEFAULT_SECTIONS,
    DEFAULT_SETTINGS,
    SECTION_UNCATEGORISED,
    STORAGE_VERSION,
    normalise_name,
)
from custom_components.better_shopping_cart.models import TemplateItem
from custom_components.better_shopping_cart.store import BetterShoppingCartStore


async def test_first_run_seeds_defaults(store):
    await store.async_load()
    sections = store.sections()
    assert [s.name for s in sections] == [name for name, _ in DEFAULT_SECTIONS]
    assert [s.order for s in sections] == list(range(len(DEFAULT_SECTIONS)))
    assert {s.icon for s in sections} == {icon for _, icon in DEFAULT_SECTIONS}

    layouts = store.layouts()
    assert len(layouts) == 1
    layout = layouts[0]
    assert layout.name == DEFAULT_LAYOUT_NAME
    assert layout.section_order == [s.id for s in sections]
    assert layout.hidden_sections == []

    assert store.settings() == DEFAULT_SETTINGS

    category_map = store.category_map()
    assert len(category_map) == len(DEFAULT_CATEGORY_MAP)
    dairy_id = next(s.id for s in sections if s.name == "Dairy")
    assert category_map["milk"] == dairy_id
    other_id = next(s.id for s in sections if s.name == "Other")
    assert category_map["cereal"] == other_id


async def test_save_and_reload_persists(store, hass):
    await store.async_load()
    store.create_section("Deli")
    await store.async_save()

    fresh = BetterShoppingCartStore(hass)
    await fresh.async_load()
    assert {s.name for s in fresh.sections()} == {s.name for s in store.sections()}
    assert "Deli" in {s.name for s in fresh.sections()}


async def test_corrupt_file_falls_back_to_defaults(store, monkeypatch):
    """A load that fails (e.g. a corrupt JSON file) must not break setup."""

    async def _raise_json_err():
        raise json.JSONDecodeError("Expecting value", "", 0)

    monkeypatch.setattr(store._store, "async_load", _raise_json_err)
    await store.async_load()
    assert [s.name for s in store.sections()] == [name for name, _ in DEFAULT_SECTIONS]
    assert len(store.layouts()) == 1
    assert store.layouts()[0].name == DEFAULT_LAYOUT_NAME


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------


async def test_section_crud(store):
    await store.async_load()
    # custom sections always use the cart icon; the requested icon is ignored
    section = store.create_section("Deli", icon="mdi:cheese")
    assert section.name == "Deli"
    assert section.icon == "mdi:cart"
    assert section.order == len(DEFAULT_SECTIONS)

    updated = store.update_section(section.id, name="Deli Counter")
    assert updated.name == "Deli Counter"
    assert updated.icon == "mdi:cart"

    icon_only = store.update_section(section.id, icon="mdi:knife")
    assert icon_only.name == "Deli Counter"
    assert icon_only.icon == "mdi:cart"

    # reordering moves custom sections; defaults keep their fixed positions
    second = store.create_section("Second")
    store.reorder_sections([second.id, section.id])
    orders = {s.name: s.order for s in store.sections()}
    assert orders["Second"] == len(DEFAULT_SECTIONS)
    assert orders["Deli Counter"] == len(DEFAULT_SECTIONS) + 1

    store.delete_section(section.id)
    assert store.section(section.id) is None
    with pytest.raises(ValueError):
        store.update_section(section.id, name="x")


async def test_default_sections_are_immutable(store):
    await store.async_load()
    ids = {s.name: s.id for s in store.sections()}

    with pytest.raises(ValueError, match="cannot be created"):
        store.create_section("dairy")
    with pytest.raises(ValueError, match="cannot be renamed"):
        store.update_section(ids["Dairy"], name="Cheese")
    custom_id = store.create_section("Custom").id
    with pytest.raises(ValueError, match="default section name"):
        store.update_section(custom_id, name="Pantry")
    with pytest.raises(ValueError, match="cannot be deleted"):
        store.delete_section(ids["Produce"])
    with pytest.raises(ValueError, match="cannot be reordered"):
        store.reorder_sections([ids["Dairy"], ids["Produce"]] + list(ids))

    # the rejected calls mutated nothing (beyond the "Custom" section itself)
    store.delete_section(custom_id)
    assert [s.name for s in store.sections()] == [
        name for name, _ in DEFAULT_SECTIONS
    ]
    assert [s.order for s in store.sections()] == list(range(len(DEFAULT_SECTIONS)))


async def test_delete_section_moves_items_and_cleans_layouts(store):
    await store.async_load()
    custom = store.create_section("Deli")
    other_id = next(s.id for s in store.sections() if s.name == "Other")
    layout = store.layouts()[0]
    store.update_layout(layout.id, hidden_sections=[custom.id])

    lst = store.create_list("Weekly")
    item = store.add_item(lst.id, "Salami", section_id=custom.id)

    store.delete_section(custom.id)

    moved = store.item(lst.id, item.id)
    assert moved.section_id == other_id
    assert custom.id not in store.layouts()[0].section_order
    assert custom.id not in store.layouts()[0].hidden_sections


async def test_load_migrates_default_sections(store, hass):
    """An older payload (NOTES: Sections tab) is normalised on load.

    Missing defaults come back, defaults regain their canonical icons and
    fixed positions, and a section whose name now collides with a default
    (here "Pantry") becomes a default. Customs keep their ids and relative
    order and are renumbered after the defaults; the result is persisted.
    """
    old_payload = {
        "version": STORAGE_VERSION,
        "sections": [
            {"id": "dairy", "name": "Dairy", "icon": "mdi:milk", "order": 0},
            {"id": "meat", "name": "Meat", "icon": "mdi:beef", "order": 1},
            {"id": "bakery", "name": "Bakery", "icon": "mdi:bread", "order": 2},
            {"id": "frozen", "name": "Frozen", "icon": "mdi:snowflake", "order": 3},
            {"id": "drinks", "name": "Drinks", "icon": "mdi:soda", "order": 4},
            {"id": "household", "name": "Household", "icon": "mdi:spray", "order": 5},
            {"id": "other", "name": "Other", "icon": "mdi:dots-triangle", "order": 6},
            {"id": "uncat", "name": "Uncategorised", "icon": "mdi:help-circle", "order": 7},
            {"id": "pantry", "name": "Pantry", "icon": "mdi:cart", "order": 8},
            {"id": "deli", "name": "Deli", "icon": "mdi:cart", "order": 9},
            {"id": "extra", "name": "Extra", "icon": "mdi:cart", "order": 10},
        ],
        "layouts": [],
        "lists": [],
        "templates": [],
        "category_map": {},
        "settings": dict(DEFAULT_SETTINGS),
    }
    await store._store.async_save(old_payload)

    fresh = BetterShoppingCartStore(hass)
    await fresh.async_load()
    by_name = {s.name: s for s in fresh.sections()}

    # "Produce" is restored; "Pantry" became a default with its canonical
    # icon and fixed position (index 7 in DEFAULT_SECTIONS)
    assert by_name["Produce"].icon == "mdi:carrot"
    assert by_name["Produce"].order == 0
    assert by_name["Pantry"].id == "pantry"
    assert by_name["Pantry"].icon == "mdi:package-variant"
    assert by_name["Pantry"].order == 7
    # broken icons are replaced by the canonical ones
    assert by_name["Dairy"].icon == "mdi:cheese"
    assert by_name["Meat"].icon == "mdi:cow"
    assert by_name["Bakery"].icon == "mdi:baguette"
    assert by_name["Drinks"].icon == "mdi:glass-mug"
    # customs keep their ids and relative order, renumbered after defaults
    assert by_name["Deli"].order == len(DEFAULT_SECTIONS)
    assert by_name["Extra"].order == len(DEFAULT_SECTIONS) + 1
    assert [s.name for s in fresh.sections()] == [
        n for n, _ in DEFAULT_SECTIONS
    ] + ["Deli", "Extra"]

    # the migration persisted: a second load is a no-op
    again = BetterShoppingCartStore(hass)
    await again.async_load()
    assert [s.id for s in again.sections()] == [s.id for s in fresh.sections()]


async def test_load_migrates_layout_hidden_sections(store, hass):
    """The "Hidden sections" UI is gone (NOTES: Layouts tab), so stored
    hidden lists are cleared on load: every section in a layout's order is
    shown again. The user's explicit section_order is left untouched and
    the result is persisted.
    """
    old_payload = {
        "version": STORAGE_VERSION,
        "sections": [
            {"id": name.lower(), "name": name, "icon": icon, "order": order}
            for order, (name, icon) in enumerate(DEFAULT_SECTIONS)
        ],
        "layouts": [
            {
                "id": "tesco",
                "name": "Tesco",
                "section_order": ["dairy", "meat", "bakery"],
                "hidden_sections": ["meat", "bakery"],
            }
        ],
        "lists": [],
        "templates": [],
        "category_map": {},
        "settings": dict(DEFAULT_SETTINGS),
    }
    await store._store.async_save(old_payload)

    fresh = BetterShoppingCartStore(hass)
    await fresh.async_load()
    layout = fresh.layouts()[0]
    assert layout.hidden_sections == []
    # the user's explicit order is kept as-is
    assert layout.section_order == ["dairy", "meat", "bakery"]

    # the migration persisted: a second load is a no-op
    again = BetterShoppingCartStore(hass)
    await again.async_load()
    assert again.layouts()[0].hidden_sections == []


# ----------------------------------------------------------------------
# Layouts
# ----------------------------------------------------------------------


async def test_layout_crud(store):
    await store.async_load()
    layout = store.create_layout("Costco")
    assert layout.section_order == [s.id for s in store.sections()]

    second = store.create_layout("Lidl")
    section_ids = [s.id for s in store.sections()]
    reordered = list(reversed(section_ids))
    updated = store.update_layout(second.id, section_order=reordered)
    assert updated.section_order == reordered

    rename_only = store.update_layout(second.id, name="Lidl XXL")
    assert rename_only.name == "Lidl XXL"
    assert rename_only.section_order == reordered

    store.delete_layout(layout.id)
    assert store.layout(layout.id) is None


async def test_delete_layout_clears_references(store):
    await store.async_load()
    layout_a = store.create_layout("A")
    layout_b = store.create_layout("B")
    lst = store.create_list("Weekly", layout_id=layout_a.id)
    store.update_settings({"default_layout_id": layout_a.id})

    store.delete_layout(layout_a.id)

    assert store.shopping_list(lst.id).layout_id is None
    assert store.settings()["default_layout_id"] is None
    assert store.layout(layout_b.id) is not None


# ----------------------------------------------------------------------
# Lists
# ----------------------------------------------------------------------


async def test_list_crud(store):
    await store.async_load()
    layout = store.layouts()[0]
    lst = store.create_list("Weekly", layout_id=layout.id)
    assert lst.name == "Weekly"
    assert lst.layout_id == layout.id
    assert lst.items == []
    assert lst.created_at
    assert lst.completed_at is None

    renamed = store.update_list(lst.id, name="Party")
    assert renamed.name == "Party"
    assert renamed.layout_id == layout.id

    store.update_list(lst.id, layout_id=None)
    assert store.shopping_list(lst.id).layout_id is None

    completed = store.complete_list(lst.id)
    assert completed.completed_at is not None

    store.delete_list(lst.id)
    assert store.shopping_list(lst.id) is None
    with pytest.raises(ValueError):
        store.complete_list(lst.id)


async def test_create_list_requires_valid_layout(store):
    await store.async_load()
    with pytest.raises(ValueError):
        store.create_list("Weekly", layout_id="nope")


async def test_clear_list_and_completed(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    store.add_item(lst.id, "Chips")
    done = store.add_item(lst.id, "Peas")
    store.check_item(lst.id, done.id, True)

    store.clear_completed(lst.id)
    assert [i.name for i in store.shopping_list(lst.id).items] == ["Chips"]

    store.clear_list(lst.id)
    assert store.shopping_list(lst.id).items == []
    with pytest.raises(ValueError):
        store.clear_list("nope")


# ----------------------------------------------------------------------
# Items
# ----------------------------------------------------------------------


def _ids(store, *names):
    return [next(s.id for s in store.sections() if s.name == n) for n in names]


async def test_add_item_explicit_section_and_fields(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    produce_id = _ids(store, "Produce")[0]
    item = store.add_item(
        lst.id, "Potatoes", section_id=produce_id,
        quantity=2.0, unit="kg", note="the big ones", added_by="etany",
    )
    assert item.section_id == produce_id
    assert item.quantity == 2.0
    assert item.unit == "kg"
    assert item.note == "the big ones"
    assert item.added_by == "etany"
    assert item.checked is False
    assert item.created_at
    assert store.item(lst.id, item.id) == item


async def test_add_item_auto_categorises(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    item = store.add_item(lst.id, "Milk")
    assert item.section_id == _ids(store, "Dairy")[0]

    second = store.add_item(lst.id, "  CHICKEN  ")
    assert second.section_id == _ids(store, "Meat")[0]


async def test_add_item_unknown_name_goes_to_uncategorised(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    item = store.add_item(lst.id, "Quantum Flux Capacitor")
    uncategorised = next(
        s for s in store.sections() if s.name == SECTION_UNCATEGORISED
    )
    assert item.section_id == uncategorised.id
    # second unknown item reuses the section
    again = store.add_item(lst.id, "Flux Capacitor Widget")
    assert again.section_id == uncategorised.id


async def test_check_and_delete_item(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    item = store.add_item(lst.id, "Milk")

    checked = store.check_item(lst.id, item.id, True)
    assert checked.checked is True
    assert checked.checked_at is not None

    unchecked = store.check_item(lst.id, item.id, False)
    assert unchecked.checked is False
    assert unchecked.checked_at is None

    store.delete_item(lst.id, item.id)
    assert store.item(lst.id, item.id) is None
    with pytest.raises(ValueError):
        store.check_item(lst.id, item.id, True)


async def test_item_order_and_reorder(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    a = store.add_item(lst.id, "Milk")
    b = store.add_item(lst.id, "Eggs")
    c = store.add_item(lst.id, "Butter")
    assert [store.item(lst.id, i.id).order for i in (a, b, c)] == [0, 1, 2]

    store.reorder_items(lst.id, [b.id, a.id, c.id])
    assert store.item(lst.id, b.id).order == 0
    assert store.item(lst.id, a.id).order == 1
    assert store.item(lst.id, c.id).order == 2

    # ids not in the list are ignored
    store.reorder_items(lst.id, ["nope", a.id])
    assert store.item(lst.id, a.id).order == 0


async def test_update_item_with_learning(store):
    await store.async_load()
    lst = store.create_list("Weekly")
    frozen_id = _ids(store, "Frozen")[0]
    item = store.add_item(lst.id, "Pizza")  # seeded -> Frozen
    assert item.section_id == frozen_id

    # move to Bakery: teaches the map
    bakery_id = _ids(store, "Bakery")[0]
    store.update_item(lst.id, item.id, section_id=bakery_id)
    assert store.category_map()[normalise_name("Pizza")] == bakery_id

    # a new "pizza" now lands in Bakery (learned beats built-in)
    again = store.add_item(lst.id, "Pizza")
    assert again.section_id == bakery_id

    # other fields update without touching the section
    updated = store.update_item(
        lst.id, item.id, quantity=2.0, unit="x", note="tonight"
    )
    assert updated.quantity == 2.0
    assert updated.unit == "x"
    assert updated.note == "tonight"
    assert updated.section_id == bakery_id


# ----------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------


async def test_template_crud_and_apply(store):
    await store.async_load()
    dairy_id, bakery_id = _ids(store, "Dairy", "Bakery")
    tpl = store.create_template(
        "Weekly basics",
        [
            {"name": "Milk", "section_id": dairy_id, "quantity": 2.0, "unit": "L"},
            TemplateItem(name="Bread", section_id=bakery_id),
        ],
    )
    assert len(tpl.items) == 2

    renamed = store.update_template(tpl.id, name="Weekly v2")
    assert renamed.name == "Weekly v2"
    assert len(renamed.items) == 2

    lst = store.create_list("Weekly")
    created = store.apply_template(tpl.id, lst.id)
    assert [i.name for i in created] == ["Milk", "Bread"]
    assert created[0].section_id == dairy_id
    assert created[0].quantity == 2.0
    assert created[1].section_id == bakery_id
    assert len(store.items(lst.id)) == 2

    store.delete_template(tpl.id)
    assert store.template(tpl.id) is None
    with pytest.raises(ValueError):
        store.apply_template(tpl.id, lst.id)
