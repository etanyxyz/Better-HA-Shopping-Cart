"""Auto-categorisation tests (PLAN.md §5 rule, M3).

``items/add`` without ``section_id`` resolves a section: an explicit
section id wins, then the learned category map, then the built-in
dictionary, else "Uncategorised". Moving an item to a new section via
``items/update`` teaches the learned map, and the choice persists.
"""
from __future__ import annotations

from custom_components.better_shopping_cart.const import SECTION_UNCATEGORISED
from custom_components.better_shopping_cart.store import BetterShoppingCartStore

from test_websocket_api import (
    add_item,
    create_list,
    section_ids_by_name,
    sections_by_id,
    ws_call,
)


class TestAutoCategorise:
    async def test_add_without_section_uses_builtin_map(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        item = await add_item(bsc_ws, shopping_list["id"], "milk")
        by_id = await sections_by_id(bsc_ws)
        assert by_id[item["section_id"]]["name"] == "Dairy"

    async def test_add_unknown_name_goes_to_uncategorised(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        item = await add_item(bsc_ws, shopping_list["id"], "zucchini")
        by_id = await sections_by_id(bsc_ws)
        assert by_id[item["section_id"]]["name"] == SECTION_UNCATEGORISED

    async def test_explicit_section_wins_over_map(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        sections = await section_ids_by_name(bsc_ws)
        # "milk" is in the built-in map (Dairy); the explicit choice wins
        item = await add_item(
            bsc_ws, shopping_list["id"], "milk", section_id=sections["Meat"]
        )
        assert item["section_id"] == sections["Meat"]

    async def test_learning_from_section_move(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        sections = await section_ids_by_name(bsc_ws)
        first = await add_item(bsc_ws, shopping_list["id"], "zucchini")
        by_id = await sections_by_id(bsc_ws)
        assert by_id[first["section_id"]]["name"] == SECTION_UNCATEGORISED
        # moving the item to Produce records the choice in the learned map
        result = await ws_call(
            bsc_ws,
            "items/update",
            list_id=shopping_list["id"],
            item_id=first["id"],
            section_id=sections["Produce"],
        )
        assert result["success"] is True
        # the next "zucchini" (any casing/whitespace) lands in Produce
        again = await add_item(bsc_ws, shopping_list["id"], "  ZUCCHINI ")
        assert again["section_id"] == sections["Produce"]

    async def test_learned_category_persists(self, bsc_ws, hass):
        shopping_list = await create_list(bsc_ws)
        sections = await section_ids_by_name(bsc_ws)
        first = await add_item(bsc_ws, shopping_list["id"], "zucchini")
        await ws_call(
            bsc_ws,
            "items/update",
            list_id=shopping_list["id"],
            item_id=first["id"],
            section_id=sections["Produce"],
        )
        # a fresh store instance (e.g. after a restart) sees the learned map
        fresh = BetterShoppingCartStore(hass)
        await fresh.async_load()
        assert fresh.category_map()["zucchini"] == sections["Produce"]
