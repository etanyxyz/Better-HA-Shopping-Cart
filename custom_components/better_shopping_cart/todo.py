"""To-do platform for Better Shopping Cart (PLAN.md §7, M4).

Each shopping list is exposed as a ``todo.*`` entity (unique id = list id).
HA to-do has no grouping, so an item's section is flattened into the item's
description (``"Section"`` or ``"Section: note"``). Editing the description
can move the item's section: a ``"Section: note"`` prefix matching a
section name is re-applied, everything else is kept as the note.

Store mutations go through ``commit`` (save + ``SIGNAL_UPDATED``); sync
listeners keep the entities in line: every entity refreshes its own items
and removes itself if its list is gone, and one per-entry listener adds
entities for newly created lists.
"""
from __future__ import annotations

import logging

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
)
from homeassistant.components.todo.const import TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED
from .models import Item, ShoppingList
from .store import BetterShoppingCartStore
from .ws_common import commit

_LOGGER = logging.getLogger(__name__)


def _to_todo_item(item: Item, section_name: str) -> TodoItem:
    """Map an ``Item`` to a todo ``TodoItem`` (PLAN.md M4 task 3)."""
    description = f"{section_name}: {item.note}" if item.note else section_name
    return TodoItem(
        summary=item.name,
        uid=item.id,
        status=TodoItemStatus.COMPLETED
        if item.checked
        else TodoItemStatus.NEEDS_ACTION,
        description=description,
    )


class BscTodoListEntity(TodoListEntity):
    """A shopping list as a todo list entity."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )
    _attr_should_poll = False

    def __init__(self, shopping_list: ShoppingList) -> None:
        """Create the entity for one shopping list (unique id = list id)."""
        self._list_id = shopping_list.id
        self._store: BetterShoppingCartStore | None = None
        self._attr_name = shopping_list.name
        self._attr_unique_id = shopping_list.id
        self._attr_todo_items = []

    async def async_added_to_hass(self) -> None:
        """Bind the store and start tracking update signals."""
        await super().async_added_to_hass()
        self._store = self.hass.data[DOMAIN]
        if self._refresh(state_update=False) is None:
            # the list was deleted before this entity got added
            self.hass.async_create_task(
                self.async_remove(), f"{DOMAIN} remove todo entity {self._list_id}"
            )
            return
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._on_store_updated)
        )

    @callback
    def _on_store_updated(self) -> None:
        """Refresh the items after any store mutation (PLAN.md M4 task 4)."""
        if self._refresh() is None:
            self.hass.async_create_task(
                self.async_remove(), f"{DOMAIN} remove todo entity {self._list_id}"
            )

    @callback
    def _refresh(self, state_update: bool = True) -> ShoppingList | None:
        """Rebuild ``_attr_todo_items`` from the store; the list, or ``None``."""
        if self._store is None:
            return None
        shopping_list = self._store.shopping_list(self._list_id)
        if shopping_list is None:
            return None
        self._attr_name = shopping_list.name
        sections = {s.id: s.name for s in self._store.sections()}
        self._attr_todo_items = [
            _to_todo_item(item, sections.get(item.section_id, ""))
            for item in sorted(shopping_list.items, key=lambda i: i.order)
        ]
        if state_update:
            self.async_write_ha_state()
        return shopping_list

    def _parse_description(
        self, description: str | None
    ) -> tuple[str | None, str | None]:
        """Return ``(section_id, note)`` encoded in a todo description."""
        if not description:
            return None, None
        for section in self._store.sections():
            if description == section.name:
                return section.id, None
            prefix = f"{section.name}: "
            if description.startswith(prefix):
                note = description.removeprefix(prefix)
                return section.id, note or None
        return None, description

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add a todo item (``todo/add_item``); auto-categorised as usual."""
        section_id, note = self._parse_description(item.description)
        try:
            self._store.add_item(
                self._list_id, item.summary, section_id=section_id, note=note
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await commit(self.hass, self._store)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a todo item (``todo/update_item``)."""
        if not item.uid:
            raise HomeAssistantError("todo item has no uid")
        section_id, note = self._parse_description(item.description)
        try:
            current = self._store.item(self._list_id, item.uid)
            if current is None:
                raise ValueError(f"unknown item: {item.uid}")
            checked = item.status == TodoItemStatus.COMPLETED
            if current.checked != checked:
                self._store.check_item(self._list_id, item.uid, checked)
            self._store.update_item(
                self._list_id,
                item.uid,
                name=item.summary,
                section_id=section_id,
                note=note,
                clear_note=note is None,
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await commit(self.hass, self._store)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items (``todo/remove_item``)."""
        try:
            for uid in uids:
                self._store.delete_item(self._list_id, uid)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await commit(self.hass, self._store)

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move a todo item after ``previous_uid`` (``todo/item/move``)."""
        try:
            ordered = [
                item.id
                for item in sorted(
                    self._store.items(self._list_id), key=lambda i: i.order
                )
            ]
            if uid not in ordered:
                raise ValueError(f"unknown item: {uid}")
            position = 0
            if previous_uid in ordered and previous_uid != uid:
                position = ordered.index(previous_uid) + 1
            ordered.remove(uid)
            ordered.insert(min(position, len(ordered)), uid)
            self._store.reorder_items(self._list_id, ordered)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await commit(self.hass, self._store)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the to-do platform: one entity per shopping list."""
    store: BetterShoppingCartStore = hass.data[DOMAIN]
    # ``added`` maps list id -> entity. It is updated synchronously when a
    # rebuild starts, so two fast mutations can never add the same list twice.
    # Note: the ``async_add_entities`` callback is synchronous on HA 2025.1
    # (it schedules the async add internally).
    added = {lst.id: BscTodoListEntity(lst) for lst in store.lists()}
    async_add_entities(list(added.values()))

    in_flight = False
    dirty = False

    async def _rebuild() -> None:
        nonlocal dirty, in_flight
        try:
            to_add = {
                lst.id: BscTodoListEntity(lst)
                for lst in store.lists()
                if lst.id not in added
            }
            if to_add:
                added.update(to_add)
                async_add_entities(list(to_add.values()))
        finally:
            in_flight = False
            # a mutation happened while this rebuild was running: reconcile
            if dirty:
                dirty = False
                hass.async_create_task(
                    _rebuild(), f"{DOMAIN} rebuild todo entities"
                )

    @callback
    def rebuild_entities() -> None:
        """Add todo entities for lists created since the last rebuild."""
        nonlocal dirty, in_flight
        if in_flight:
            dirty = True
            return
        in_flight = True
        hass.async_create_task(_rebuild(), f"{DOMAIN} rebuild todo entities")

    unsub = async_dispatcher_connect(hass, SIGNAL_UPDATED, rebuild_entities)
    config_entry.async_on_unload(unsub)
    _LOGGER.debug("To-do platform set up (%d list(s))", len(added))
