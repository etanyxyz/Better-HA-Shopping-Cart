"""To-do platform tests (PLAN.md M4).

Each shopping list becomes a ``todo.*`` entity; the HA to-do services mutate
the store and store mutations update the entities. Sections are flattened
into the item description (``"Section: note"``) because HA to-do has no
grouping.
"""
from __future__ import annotations

import pytest

from homeassistant.components.todo import TodoItemStatus
from homeassistant.components.todo.const import DATA_COMPONENT
from homeassistant.helpers import entity_registry as er

from custom_components.better_shopping_cart.const import DOMAIN
from custom_components.better_shopping_cart.store import BetterShoppingCartStore
from custom_components.better_shopping_cart.ws_common import commit


def todo_entity(hass, list_id: str):
    """Return the todo entity for a list, by its unique id (list id)."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("todo", DOMAIN, list_id)
    if entity_id is None:
        return None
    return hass.data[DATA_COMPONENT].get_entity(entity_id)


async def make_list(hass, name="Shop"):
    """Create a list in the loaded store and let the todo platform catch up."""
    store: BetterShoppingCartStore = hass.data[DOMAIN]
    shopping_list = store.create_list(name)
    await commit(hass, store)
    await hass.async_block_till_done()
    return shopping_list


@pytest.mark.usefixtures("bsc_entry")
class TestTodoEntities:
    async def test_entity_created_for_new_list(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        assert entity is not None
        assert entity.entity_id.startswith("todo.")
        state = hass.states.get(entity.entity_id)
        assert state is not None
        # no items yet: the state is the count of incomplete items
        assert state.state == "0"

    async def test_add_item_via_service(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        await hass.services.async_call(
            "todo", "add_item", {"entity_id": entity.entity_id, "item": "milk"},
            blocking=True,
        )
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        items = store.items(shopping_list.id)
        assert [item.name for item in items] == ["milk"]
        # auto-categorised to Dairy by the built-in map
        sections = {s.id: s.name for s in store.sections()}
        assert sections[items[0].section_id] == "Dairy"
        # the entity reflects the item; the section is in the description
        todo_items = entity.todo_items
        assert todo_items[0].summary == "milk"
        assert todo_items[0].description == "Dairy"
        assert todo_items[0].status == TodoItemStatus.NEEDS_ACTION
        assert hass.states.get(entity.entity_id).state == "1"

    async def test_update_status_via_service(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        await hass.services.async_call(
            "todo",
            "add_item",
            {"entity_id": entity.entity_id, "item": "milk"},
            blocking=True,
        )
        uid = entity.todo_items[0].uid
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": entity.entity_id, "item": uid, "status": "completed"},
            blocking=True,
        )
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        assert store.item(shopping_list.id, uid).checked is True
        assert entity.todo_items[0].status == TodoItemStatus.COMPLETED
        assert hass.states.get(entity.entity_id).state == "0"

    async def test_rename_via_service(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        await hass.services.async_call(
            "todo",
            "add_item",
            {"entity_id": entity.entity_id, "item": "milk"},
            blocking=True,
        )
        uid = entity.todo_items[0].uid
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": entity.entity_id, "item": uid, "rename": "Whole Milk"},
            blocking=True,
        )
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        assert store.item(shopping_list.id, uid).name == "Whole Milk"
        assert entity.todo_items[0].summary == "Whole Milk"

    async def test_update_description_moves_section(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        await hass.services.async_call(
            "todo",
            "add_item",
            {"entity_id": entity.entity_id, "item": "zucchini"},
            blocking=True,
        )
        uid = entity.todo_items[0].uid
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        id_to_name = {s.id: s.name for s in store.sections()}
        name_to_id = {s.name: s.id for s in store.sections()}
        assert id_to_name[store.item(shopping_list.id, uid).section_id] == "Uncategorised"
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": entity.entity_id, "item": uid, "description": "Produce: zoodles"},
            blocking=True,
        )
        item = store.item(shopping_list.id, uid)
        assert item.section_id == name_to_id["Produce"]
        assert item.note == "zoodles"
        assert entity.todo_items[0].description == "Produce: zoodles"

    async def test_clear_description_clears_note(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        await hass.services.async_call(
            "todo",
            "add_item",
            {
                "entity_id": entity.entity_id,
                "item": "milk",
                "description": "Dairy: low fat",
            },
            blocking=True,
        )
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        uid = entity.todo_items[0].uid
        item = store.item(shopping_list.id, uid)
        assert item.note == "low fat"
        assert item.section_id == {s.name: s.id for s in store.sections()}["Dairy"]
        # a section-only description clears the note (section is kept)
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": entity.entity_id, "item": uid, "description": "Dairy"},
            blocking=True,
        )
        item = store.item(shopping_list.id, uid)
        assert item.note is None
        assert item.section_id == {s.name: s.id for s in store.sections()}["Dairy"]
        assert entity.todo_items[0].description == "Dairy"

    async def test_remove_item_via_service(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        await hass.services.async_call(
            "todo",
            "add_item",
            {"entity_id": entity.entity_id, "item": "milk"},
            blocking=True,
        )
        uid = entity.todo_items[0].uid
        await hass.services.async_call(
            "todo",
            "remove_item",
            {"entity_id": entity.entity_id, "item": [uid]},
            blocking=True,
        )
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        assert store.items(shopping_list.id) == []
        assert entity.todo_items == []

    async def test_remove_completed_items_via_service(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        for name in ("milk", "bread"):
            await hass.services.async_call(
                "todo",
                "add_item",
                {"entity_id": entity.entity_id, "item": name},
                blocking=True,
            )
        uid = entity.todo_items[0].uid
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": entity.entity_id, "item": uid, "status": "completed"},
            blocking=True,
        )
        await hass.services.async_call(
            "todo",
            "remove_completed_items",
            {"entity_id": entity.entity_id},
            blocking=True,
        )
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        assert [item.name for item in store.items(shopping_list.id)] == ["bread"]

    async def test_move_item(self, hass):
        shopping_list = await make_list(hass)
        entity = todo_entity(hass, shopping_list.id)
        uids = []
        for name in ("milk", "bread", "eggs"):
            await hass.services.async_call(
                "todo",
                "add_item",
                {"entity_id": entity.entity_id, "item": name},
                blocking=True,
            )
            uids.append(entity.todo_items[-1].uid)
        # move "eggs" after "milk": milk, eggs, bread
        await entity.async_move_todo_item(uids[2], uids[0])
        await hass.async_block_till_done()
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        ordered = [
            item.id
            for item in sorted(store.items(shopping_list.id), key=lambda i: i.order)
        ]
        assert ordered == [uids[0], uids[2], uids[1]]
        assert [item.uid for item in entity.todo_items] == [uids[0], uids[2], uids[1]]

    async def test_entity_removed_when_list_deleted(self, hass):
        shopping_list = await make_list(hass)
        assert todo_entity(hass, shopping_list.id) is not None
        store: BetterShoppingCartStore = hass.data[DOMAIN]
        store.delete_list(shopping_list.id)
        await commit(hass, store)
        await hass.async_block_till_done()
        assert todo_entity(hass, shopping_list.id) is None
