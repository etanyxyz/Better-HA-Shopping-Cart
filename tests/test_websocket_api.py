"""WebSocket API tests for the §5 commands (PLAN.md M2 + M3).

Commands are exercised end-to-end over a real authenticated websocket
connection to the running hass instance (plugin ``hass_ws_client``):
auth exchange, JSON framing, voluptuous schema validation and error
mapping all run through the core websocket_api component.
"""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.better_shopping_cart.const import (
    DEFAULT_LAYOUT_NAME,
    DEFAULT_SECTIONS,
    DEFAULT_SETTINGS,
    SIGNAL_UPDATED,
)
from custom_components.better_shopping_cart.store import BetterShoppingCartStore


async def ws_call(ws, command: str, **payload) -> dict[str, Any]:
    """Send ``better_shopping_cart/<command>`` and return the WS result."""
    await ws.send_json_auto_id({"type": f"better_shopping_cart/{command}", **payload})
    return await ws.receive_json()


async def sections_by_id(bsc_ws) -> dict[str, dict[str, Any]]:
    """Return the current sections as a name-independent id -> section map."""
    result = await ws_call(bsc_ws, "sections/list")
    return {s["id"]: s for s in result["result"]["sections"]}


async def section_ids_by_name(bsc_ws) -> dict[str, str]:
    """Return the current sections as a name -> section id map."""
    result = await ws_call(bsc_ws, "sections/list")
    return {s["name"]: s["id"] for s in result["result"]["sections"]}


async def create_list(bsc_ws, name="Test List", **extra) -> dict[str, Any]:
    """Create a list via the WS API and return its ``list`` payload."""
    result = await ws_call(bsc_ws, "lists/create", name=name, **extra)
    assert result["success"] is True
    return result["result"]["list"]


async def add_item(bsc_ws, list_id: str, name: str, **extra) -> dict[str, Any]:
    """Add an item via the WS API and return its ``item`` payload."""
    result = await ws_call(bsc_ws, "items/add", list_id=list_id, name=name, **extra)
    assert result["success"] is True
    return result["result"]["item"]


class TestSections:
    async def test_list_returns_seeded_sections(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/list")
        assert result["success"] is True
        sections = result["result"]["sections"]
        assert [s["name"] for s in sections] == [name for name, _ in DEFAULT_SECTIONS]
        assert [s["order"] for s in sections] == list(range(len(DEFAULT_SECTIONS)))
        assert all(s["id"] and s["icon"] for s in sections)

    async def test_create_section(self, bsc_ws):
        # the icon is accepted for contract compatibility but ignored:
        # custom sections always use the cart icon (NOTES: Sections tab)
        result = await ws_call(
            bsc_ws, "sections/create", name="Test Section", icon="mdi:test"
        )
        assert result["success"] is True
        section = result["result"]["section"]
        assert section["name"] == "Test Section"
        assert section["icon"] == "mdi:cart"
        assert section["order"] == len(DEFAULT_SECTIONS)
        sections = await sections_by_id(bsc_ws)
        assert sections[section["id"]]["name"] == "Test Section"

    async def test_create_section_default_icon(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/create", name="Plain")
        assert result["result"]["section"]["icon"] == "mdi:cart"

    async def test_create_section_requires_name(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/create")
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"
        assert "name" in result["error"]["message"]

    async def test_create_default_name_rejected(self, bsc_ws):
        # default names are immutable, even with different casing
        result = await ws_call(bsc_ws, "sections/create", name="dairy")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "default section" in result["error"]["message"]

    async def test_update_section(self, bsc_ws):
        created = await ws_call(bsc_ws, "sections/create", name="Before")
        section_id = created["result"]["section"]["id"]
        result = await ws_call(
            bsc_ws, "sections/update", section_id=section_id, name="Renamed", icon="mdi:apple"
        )
        assert result["success"] is True
        section = result["result"]["section"]
        assert section["name"] == "Renamed"
        assert section["icon"] == "mdi:cart"

    async def test_update_section_partial(self, bsc_ws):
        created = await ws_call(bsc_ws, "sections/create", name="Plain")
        section_id = created["result"]["section"]["id"]
        # omitting ``name`` leaves it untouched; the icon stays the cart icon
        result = await ws_call(bsc_ws, "sections/update", section_id=section_id, icon="mdi:egg")
        section = result["result"]["section"]
        assert section["name"] == "Plain"
        assert section["icon"] == "mdi:cart"

    async def test_update_default_section_rejected(self, bsc_ws):
        ids = await section_ids_by_name(bsc_ws)
        result = await ws_call(
            bsc_ws, "sections/update", section_id=ids["Dairy"], name="Cheese"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "cannot be renamed" in result["error"]["message"]

    async def test_rename_custom_to_default_name_rejected(self, bsc_ws):
        created = await ws_call(bsc_ws, "sections/create", name="Custom")
        section_id = created["result"]["section"]["id"]
        result = await ws_call(
            bsc_ws, "sections/update", section_id=section_id, name="Pantry"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "default section name" in result["error"]["message"]

    async def test_update_section_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/update", section_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown section" in result["error"]["message"]

    async def test_delete_section(self, bsc_ws):
        created = await ws_call(bsc_ws, "sections/create", name="Doomed")
        section_id = created["result"]["section"]["id"]
        result = await ws_call(bsc_ws, "sections/delete", section_id=section_id)
        assert result["success"] is True
        assert result["result"] == {}
        remaining = await sections_by_id(bsc_ws)
        assert section_id not in remaining
        # layout references to the deleted section are cleaned up
        layouts = await ws_call(bsc_ws, "layouts/list")
        for layout in layouts["result"]["layouts"]:
            assert section_id not in layout["section_order"]
            assert section_id not in layout["hidden_sections"]

    async def test_delete_default_section_rejected(self, bsc_ws):
        ids = await section_ids_by_name(bsc_ws)
        result = await ws_call(
            bsc_ws, "sections/delete", section_id=ids["Produce"]
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "cannot be deleted" in result["error"]["message"]

    async def test_delete_section_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/delete", section_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"

    async def test_reorder_custom_sections_persists(self, bsc_ws, hass):
        a = await ws_call(bsc_ws, "sections/create", name="A")
        b = await ws_call(bsc_ws, "sections/create", name="B")
        c = await ws_call(bsc_ws, "sections/create", name="C")
        a_id = a["result"]["section"]["id"]
        b_id = b["result"]["section"]["id"]
        c_id = c["result"]["section"]["id"]

        # reorder the customs in reverse; defaults keep their positions
        result = await ws_call(
            bsc_ws, "sections/reorder", ordered_ids=[c_id, b_id, a_id]
        )
        assert result["success"] is True
        assert result["result"] == {}

        after = await ws_call(bsc_ws, "sections/list")
        listed = after["result"]["sections"]
        customs = [s for s in listed if s["name"] in ("A", "B", "C")]
        assert [s["id"] for s in customs] == [c_id, b_id, a_id]
        assert [s["order"] for s in customs] == list(
            range(len(DEFAULT_SECTIONS), len(DEFAULT_SECTIONS) + 3)
        )
        defaults = [
            s for s in listed if s["name"] not in ("A", "B", "C")
        ]
        assert [s["name"] for s in defaults] == [n for n, _ in DEFAULT_SECTIONS]

        # a fresh store instance (e.g. after a restart) sees the persisted order
        fresh = BetterShoppingCartStore(hass)
        await fresh.async_load()
        listed_fresh = {s.name: s.id for s in fresh.sections()}
        orders = {s.id: s.order for s in fresh.sections()}
        assert orders[listed_fresh["C"]] < orders[listed_fresh["B"]] < orders[
            listed_fresh["A"]
        ]

    async def test_reorder_default_rejected(self, bsc_ws):
        ids = await section_ids_by_name(bsc_ws)
        all_ids = list((await sections_by_id(bsc_ws)))
        swapped = [all_ids[1], all_ids[0]] + all_ids[2:]
        result = await ws_call(
            bsc_ws, "sections/reorder", ordered_ids=swapped
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "cannot be reordered" in result["error"]["message"]
        # the rejected reorder left the store untouched
        after = await section_ids_by_name(bsc_ws)
        assert after == ids

    async def test_reorder_ignores_unknown_ids(self, bsc_ws):
        a = await ws_call(bsc_ws, "sections/create", name="A")
        b = await ws_call(bsc_ws, "sections/create", name="B")
        a_id = a["result"]["section"]["id"]
        b_id = b["result"]["section"]["id"]
        result = await ws_call(
            bsc_ws,
            "sections/reorder",
            ordered_ids=[b_id, "bogus-id", a_id],
        )
        assert result["success"] is True
        after = await sections_by_id(bsc_ws)
        assert after[b_id]["order"] == len(DEFAULT_SECTIONS)
        assert after[a_id]["order"] == len(DEFAULT_SECTIONS) + 1

    async def test_mutating_command_fires_signal(self, bsc_ws, hass):
        signals = []

        def on_update() -> None:
            signals.append(SIGNAL_UPDATED)

        async_dispatcher_connect(hass, SIGNAL_UPDATED, on_update)
        result = await ws_call(bsc_ws, "sections/create", name="Signal Test")
        assert result["success"] is True
        await hass.async_block_till_done()
        assert signals == [SIGNAL_UPDATED]


class TestLayouts:
    async def test_list_returns_seeded_layout(self, bsc_ws):
        result = await ws_call(bsc_ws, "layouts/list")
        assert result["success"] is True
        layouts = result["result"]["layouts"]
        assert len(layouts) == 1
        assert layouts[0]["name"] == DEFAULT_LAYOUT_NAME
        assert layouts[0]["hidden_sections"] == []
        sections = await ws_call(bsc_ws, "sections/list")
        assert layouts[0]["section_order"] == [
            s["id"] for s in sections["result"]["sections"]
        ]

    async def test_create_layout(self, bsc_ws):
        result = await ws_call(bsc_ws, "layouts/create", name="Tesco")
        assert result["success"] is True
        layout = result["result"]["layout"]
        assert layout["name"] == "Tesco"
        assert layout["hidden_sections"] == []
        sections = await ws_call(bsc_ws, "sections/list")
        # new layouts start from the current default section order
        assert layout["section_order"] == [
            s["id"] for s in sections["result"]["sections"]
        ]

    async def test_create_layout_requires_name(self, bsc_ws):
        result = await ws_call(bsc_ws, "layouts/create")
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_update_layout(self, bsc_ws):
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        sections = await ws_call(bsc_ws, "sections/list")
        ordered_ids = [s["id"] for s in sections["result"]["sections"]]

        result = await ws_call(
            bsc_ws,
            "layouts/update",
            layout_id=layout_id,
            name="Costco",
            section_order=list(reversed(ordered_ids)),
            hidden_sections=[ordered_ids[0]],
        )
        assert result["success"] is True
        layout = result["result"]["layout"]
        assert layout["name"] == "Costco"
        assert layout["section_order"] == list(reversed(ordered_ids))
        assert layout["hidden_sections"] == [ordered_ids[0]]

    async def test_update_layout_partial(self, bsc_ws):
        layouts = await ws_call(bsc_ws, "layouts/list")
        current = layouts["result"]["layouts"][0]
        result = await ws_call(
            bsc_ws, "layouts/update", layout_id=current["id"], name="Renamed"
        )
        layout = result["result"]["layout"]
        assert layout["name"] == "Renamed"
        # omitted fields are untouched
        assert layout["section_order"] == current["section_order"]
        assert layout["hidden_sections"] == current["hidden_sections"]

    async def test_update_layout_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "layouts/update", layout_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown layout" in result["error"]["message"]

    async def test_delete_layout(self, bsc_ws):
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        result = await ws_call(bsc_ws, "layouts/delete", layout_id=layout_id)
        assert result["success"] is True
        assert result["result"] == {}
        remaining = await ws_call(bsc_ws, "layouts/list")
        assert remaining["result"]["layouts"] == []

    async def test_delete_layout_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "layouts/delete", layout_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"


class TestLists:
    async def test_list_is_empty_initially(self, bsc_ws):
        result = await ws_call(bsc_ws, "lists/list")
        assert result["success"] is True
        assert result["result"]["lists"] == []

    async def test_create_list(self, bsc_ws):
        shopping_list = await create_list(bsc_ws, name="Groceries")
        assert shopping_list["name"] == "Groceries"
        assert shopping_list["items"] == []
        assert shopping_list["layout_id"] is None
        assert shopping_list["completed_at"] is None
        assert shopping_list["created_at"]
        result = await ws_call(bsc_ws, "lists/list")
        assert [l["id"] for l in result["result"]["lists"]] == [shopping_list["id"]]

    async def test_create_list_with_layout(self, bsc_ws):
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        shopping_list = await create_list(bsc_ws, layout_id=layout_id)
        assert shopping_list["layout_id"] == layout_id

    async def test_create_list_requires_name(self, bsc_ws):
        result = await ws_call(bsc_ws, "lists/create")
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_create_list_unknown_layout(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "lists/create", name="X", layout_id="does-not-exist"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown layout" in result["error"]["message"]

    async def test_update_list(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        result = await ws_call(
            bsc_ws,
            "lists/update",
            list_id=shopping_list["id"],
            name="Renamed",
            layout_id=layout_id,
        )
        assert result["success"] is True
        updated = result["result"]["list"]
        assert updated["name"] == "Renamed"
        assert updated["layout_id"] == layout_id

    async def test_update_list_partial(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        await ws_call(
            bsc_ws, "lists/update", list_id=shopping_list["id"], layout_id=layout_id
        )
        # omitting ``layout_id`` leaves it untouched
        result = await ws_call(
            bsc_ws, "lists/update", list_id=shopping_list["id"], name="Renamed"
        )
        updated = result["result"]["list"]
        assert updated["name"] == "Renamed"
        assert updated["layout_id"] == layout_id

    async def test_update_list_clear_layout(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        await ws_call(
            bsc_ws, "lists/update", list_id=shopping_list["id"], layout_id=layout_id
        )
        # an explicit null clears the layout
        result = await ws_call(
            bsc_ws, "lists/update", list_id=shopping_list["id"], layout_id=None
        )
        assert result["success"] is True
        assert result["result"]["list"]["layout_id"] is None

    async def test_update_list_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "lists/update", list_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]

    async def test_delete_list(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(bsc_ws, "lists/delete", list_id=shopping_list["id"])
        assert result["success"] is True
        assert result["result"] == {}
        remaining = await ws_call(bsc_ws, "lists/list")
        assert remaining["result"]["lists"] == []

    async def test_delete_list_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "lists/delete", list_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"

    async def test_complete_list(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(bsc_ws, "lists/complete", list_id=shopping_list["id"])
        assert result["success"] is True
        assert result["result"]["list"]["completed_at"] is not None
        # completing again keeps it completed
        result = await ws_call(bsc_ws, "lists/complete", list_id=shopping_list["id"])
        assert result["result"]["list"]["completed_at"] is not None

    async def test_clear_list(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        await add_item(bsc_ws, shopping_list["id"], name="Chips")
        await add_item(bsc_ws, shopping_list["id"], name="Peas")
        result = await ws_call(bsc_ws, "lists/clear", list_id=shopping_list["id"])
        assert result["success"] is True
        assert result["result"] == {}
        items = await ws_call(bsc_ws, "items/list", list_id=shopping_list["id"])
        assert items["result"]["items"] == []

    async def test_clear_list_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "lists/clear", list_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"

    async def test_clear_completed(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        await add_item(bsc_ws, shopping_list["id"], name="Chips")
        done = await add_item(bsc_ws, shopping_list["id"], name="Peas")
        await ws_call(
            bsc_ws,
            "items/check",
            list_id=shopping_list["id"],
            item_id=done["id"],
            checked=True,
        )
        result = await ws_call(
            bsc_ws, "lists/clear_completed", list_id=shopping_list["id"]
        )
        assert result["success"] is True
        assert result["result"] == {}
        items = await ws_call(bsc_ws, "items/list", list_id=shopping_list["id"])
        assert [i["name"] for i in items["result"]["items"]] == ["Chips"]


class TestItems:
    async def test_list_items_empty(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(bsc_ws, "items/list", list_id=shopping_list["id"])
        assert result["success"] is True
        assert result["result"]["items"] == []

    async def test_list_items_unknown_list(self, bsc_ws):
        result = await ws_call(bsc_ws, "items/list", list_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]

    async def test_add_item_explicit_section(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        sections = await section_ids_by_name(bsc_ws)
        added = await add_item(
            bsc_ws,
            shopping_list["id"],
            "Milk",
            section_id=sections["Meat"],
            quantity=2,
            unit="L",
            note="semi skimmed",
        )
        assert added["name"] == "Milk"
        assert added["section_id"] == sections["Meat"]
        assert added["quantity"] == 2
        assert added["unit"] == "L"
        assert added["note"] == "semi skimmed"
        assert added["checked"] is False
        assert added["checked_at"] is None
        assert added["order"] == 0

    async def test_add_item_requires_name(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(bsc_ws, "items/add", list_id=shopping_list["id"])
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_add_item_unknown_list(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "items/add", list_id="does-not-exist", name="Milk"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]

    async def test_add_item_unknown_section(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(
            bsc_ws,
            "items/add",
            list_id=shopping_list["id"],
            name="Milk",
            section_id="does-not-exist",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown section" in result["error"]["message"]

    async def test_update_item(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        sections = await section_ids_by_name(bsc_ws)
        added = await add_item(
            bsc_ws, shopping_list["id"], "Milk", section_id=sections["Dairy"]
        )
        result = await ws_call(
            bsc_ws,
            "items/update",
            list_id=shopping_list["id"],
            item_id=added["id"],
            name="Whole Milk",
            section_id=sections["Drinks"],
            quantity=1,
            unit="L",
        )
        assert result["success"] is True
        updated = result["result"]["item"]
        assert updated["name"] == "Whole Milk"
        assert updated["section_id"] == sections["Drinks"]
        assert updated["quantity"] == 1
        assert updated["unit"] == "L"

    async def test_update_item_partial(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        sections = await section_ids_by_name(bsc_ws)
        added = await add_item(
            bsc_ws,
            shopping_list["id"],
            "Milk",
            section_id=sections["Dairy"],
            quantity=2,
        )
        result = await ws_call(
            bsc_ws,
            "items/update",
            list_id=shopping_list["id"],
            item_id=added["id"],
            note="low fat",
        )
        updated = result["result"]["item"]
        assert updated["note"] == "low fat"
        # omitted fields are untouched
        assert updated["name"] == "Milk"
        assert updated["quantity"] == 2
        assert updated["section_id"] == sections["Dairy"]

    async def test_update_item_unknown_item_id(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(
            bsc_ws,
            "items/update",
            list_id=shopping_list["id"],
            item_id="does-not-exist",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown item" in result["error"]["message"]

    async def test_check_and_uncheck(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        added = await add_item(bsc_ws, shopping_list["id"], "Milk")
        result = await ws_call(
            bsc_ws,
            "items/check",
            list_id=shopping_list["id"],
            item_id=added["id"],
            checked=True,
        )
        checked = result["result"]["item"]
        assert checked["checked"] is True
        assert checked["checked_at"] is not None
        result = await ws_call(
            bsc_ws,
            "items/check",
            list_id=shopping_list["id"],
            item_id=added["id"],
            checked=False,
        )
        unchecked = result["result"]["item"]
        assert unchecked["checked"] is False
        assert unchecked["checked_at"] is None

    async def test_check_requires_flag(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        added = await add_item(bsc_ws, shopping_list["id"], "Milk")
        result = await ws_call(
            bsc_ws, "items/check", list_id=shopping_list["id"], item_id=added["id"]
        )
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_delete_item(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        added = await add_item(bsc_ws, shopping_list["id"], "Milk")
        result = await ws_call(
            bsc_ws,
            "items/delete",
            list_id=shopping_list["id"],
            item_id=added["id"],
        )
        assert result["success"] is True
        assert result["result"] == {}
        remaining = await ws_call(bsc_ws, "items/list", list_id=shopping_list["id"])
        assert remaining["result"]["items"] == []
        # deleting it again is an unknown item
        result = await ws_call(
            bsc_ws,
            "items/delete",
            list_id=shopping_list["id"],
            item_id=added["id"],
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"

    async def test_reorder_items(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        first = await add_item(bsc_ws, shopping_list["id"], "Milk")
        second = await add_item(bsc_ws, shopping_list["id"], "Bread")
        third = await add_item(bsc_ws, shopping_list["id"], "Eggs")
        result = await ws_call(
            bsc_ws,
            "items/reorder",
            list_id=shopping_list["id"],
            ordered_ids=[third["id"], first["id"], second["id"], "bogus-id"],
        )
        assert result["success"] is True
        assert result["result"] == {}
        listed = await ws_call(bsc_ws, "items/list", list_id=shopping_list["id"])
        by_id = {i["id"]: i for i in listed["result"]["items"]}
        assert by_id[third["id"]]["order"] == 0
        assert by_id[first["id"]]["order"] == 1
        assert by_id[second["id"]]["order"] == 2


class TestTemplates:
    async def test_list_is_empty_initially(self, bsc_ws):
        result = await ws_call(bsc_ws, "templates/list")
        assert result["success"] is True
        assert result["result"]["templates"] == []

    async def test_create_template(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        result = await ws_call(
            bsc_ws,
            "templates/create",
            name="Weekly Shop",
            items=[
                {"name": "Milk", "section_id": sections["Dairy"], "quantity": 2},
                {"name": "Bread", "section_id": sections["Bakery"]},
            ],
        )
        assert result["success"] is True
        template = result["result"]["template"]
        assert template["name"] == "Weekly Shop"
        assert [i["name"] for i in template["items"]] == ["Milk", "Bread"]
        assert template["items"][0]["quantity"] == 2
        assert template["items"][0]["unit"] is None
        assert template["items"][1]["note"] is None
        listed = await ws_call(bsc_ws, "templates/list")
        assert [t["id"] for t in listed["result"]["templates"]] == [template["id"]]

    async def test_create_template_requires_items(self, bsc_ws):
        result = await ws_call(bsc_ws, "templates/create", name="No Items")
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_create_template_unknown_section(self, bsc_ws):
        result = await ws_call(
            bsc_ws,
            "templates/create",
            name="Bad",
            items=[{"name": "Milk", "section_id": "does-not-exist"}],
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown section" in result["error"]["message"]

    async def test_update_template(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        template = (
            await ws_call(
                bsc_ws,
                "templates/create",
                name="Old",
                items=[{"name": "Milk", "section_id": sections["Dairy"]}],
            )
        )["result"]["template"]
        result = await ws_call(
            bsc_ws,
            "templates/update",
            template_id=template["id"],
            name="New",
            items=[{"name": "Bread", "section_id": sections["Bakery"]}],
        )
        updated = result["result"]["template"]
        assert updated["name"] == "New"
        assert [i["name"] for i in updated["items"]] == ["Bread"]

    async def test_update_template_partial(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        template = (
            await ws_call(
                bsc_ws,
                "templates/create",
                name="Old",
                items=[{"name": "Milk", "section_id": sections["Dairy"]}],
            )
        )["result"]["template"]
        # omitting ``items`` leaves them untouched
        result = await ws_call(
            bsc_ws, "templates/update", template_id=template["id"], name="Renamed"
        )
        updated = result["result"]["template"]
        assert updated["name"] == "Renamed"
        assert [i["name"] for i in updated["items"]] == ["Milk"]

    async def test_update_template_unknown_id(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "templates/update", template_id="does-not-exist", name="X"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown template" in result["error"]["message"]

    async def test_delete_template(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        template = (
            await ws_call(
                bsc_ws,
                "templates/create",
                name="Gone",
                items=[{"name": "Milk", "section_id": sections["Dairy"]}],
            )
        )["result"]["template"]
        result = await ws_call(
            bsc_ws, "templates/delete", template_id=template["id"]
        )
        assert result["success"] is True
        assert result["result"] == {}
        remaining = await ws_call(bsc_ws, "templates/list")
        assert remaining["result"]["templates"] == []

    async def test_delete_template_unknown_id(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "templates/delete", template_id="does-not-exist"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"

    async def test_apply_template(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        template = (
            await ws_call(
                bsc_ws,
                "templates/create",
                name="Weekly Shop",
                items=[
                    {"name": "Milk", "section_id": sections["Dairy"], "quantity": 2},
                    {"name": "Bread", "section_id": sections["Bakery"]},
                ],
            )
        )["result"]["template"]
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(
            bsc_ws,
            "templates/apply",
            template_id=template["id"],
            list_id=shopping_list["id"],
        )
        assert result["success"] is True
        items = result["result"]["items"]
        assert [i["name"] for i in items] == ["Milk", "Bread"]
        assert items[0]["section_id"] == sections["Dairy"]
        assert items[0]["quantity"] == 2
        assert all(i["checked"] is False for i in items)
        listed = await ws_call(bsc_ws, "items/list", list_id=shopping_list["id"])
        assert [i["id"] for i in listed["result"]["items"]] == [
            i["id"] for i in items
        ]

    async def test_apply_template_unknown_template(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(
            bsc_ws,
            "templates/apply",
            template_id="does-not-exist",
            list_id=shopping_list["id"],
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown template" in result["error"]["message"]

    async def test_apply_template_unknown_list(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        template = (
            await ws_call(
                bsc_ws,
                "templates/create",
                name="Weekly Shop",
                items=[{"name": "Milk", "section_id": sections["Dairy"]}],
            )
        )["result"]["template"]
        result = await ws_call(
            bsc_ws,
            "templates/apply",
            template_id=template["id"],
            list_id="does-not-exist",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]


class TestHistory:
    async def test_recent_is_empty_initially(self, bsc_ws):
        result = await ws_call(bsc_ws, "history/recent")
        assert result["success"] is True
        assert result["result"]["items"] == []

    async def test_recent_returns_most_recent_first(self, bsc_ws):
        list_a = await create_list(bsc_ws, name="A")
        list_b = await create_list(bsc_ws, name="B")
        item_a = await add_item(bsc_ws, list_a["id"], "Milk")
        await ws_call(
            bsc_ws,
            "items/check",
            list_id=list_a["id"],
            item_id=item_a["id"],
            checked=True,
        )
        item_b = await add_item(bsc_ws, list_b["id"], "Bread")
        await ws_call(
            bsc_ws,
            "items/check",
            list_id=list_b["id"],
            item_id=item_b["id"],
            checked=True,
        )
        result = await ws_call(bsc_ws, "history/recent")
        assert result["result"]["items"] == ["Bread", "Milk"]

    async def test_recent_dedupes_and_limits(self, bsc_ws):
        list_a = await create_list(bsc_ws, name="A")
        list_b = await create_list(bsc_ws, name="B")
        item_a = await add_item(bsc_ws, list_a["id"], "Milk")
        item_b = await add_item(bsc_ws, list_b["id"], "Milk")
        for list_id, item_id in (
            (list_a["id"], item_a["id"]),
            (list_b["id"], item_b["id"]),
        ):
            await ws_call(
                bsc_ws,
                "items/check",
                list_id=list_id,
                item_id=item_id,
                checked=True,
            )
        # the same name checked in two lists appears once
        result = await ws_call(bsc_ws, "history/recent")
        assert result["result"]["items"] == ["Milk"]
        # limit is respected
        item_c = await add_item(bsc_ws, list_a["id"], "Bread")
        await ws_call(
            bsc_ws,
            "items/check",
            list_id=list_a["id"],
            item_id=item_c["id"],
            checked=True,
        )
        result = await ws_call(bsc_ws, "history/recent", limit=1)
        assert result["result"]["items"] == ["Bread"]

    async def test_repeat_last_with_no_completed_list(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(
            bsc_ws, "history/repeat_last", list_id=shopping_list["id"]
        )
        assert result["success"] is True
        assert result["result"]["items"] == []

    async def test_repeat_last_copies_items(self, bsc_ws):
        sections = await section_ids_by_name(bsc_ws)
        source = await create_list(bsc_ws, name="Last Week")
        await add_item(
            bsc_ws, source["id"], "Milk", section_id=sections["Dairy"], quantity=2
        )
        await add_item(bsc_ws, source["id"], "Bread", section_id=sections["Bakery"])
        await ws_call(bsc_ws, "lists/complete", list_id=source["id"])

        target = await create_list(bsc_ws, name="This Week")
        result = await ws_call(
            bsc_ws, "history/repeat_last", list_id=target["id"]
        )
        assert result["success"] is True
        copied = result["result"]["items"]
        assert [i["name"] for i in copied] == ["Milk", "Bread"]
        assert copied[0]["section_id"] == sections["Dairy"]
        assert copied[0]["quantity"] == 2
        assert all(i["checked"] is False for i in copied)
        # the target list now holds fresh copies (new ids)
        listed = await ws_call(bsc_ws, "items/list", list_id=target["id"])
        listed_ids = [i["id"] for i in listed["result"]["items"]]
        assert listed_ids == [i["id"] for i in copied]
        # the source keeps its completion state and its items
        lists = await ws_call(bsc_ws, "lists/list")
        source_now = next(l for l in lists["result"]["lists"] if l["id"] == source["id"])
        assert source_now["completed_at"] is not None
        assert [i["name"] for i in source_now["items"]] == ["Milk", "Bread"]

    async def test_repeat_last_unknown_list(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "history/repeat_last", list_id="does-not-exist"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]


class TestSettings:
    async def test_get_defaults(self, bsc_ws):
        result = await ws_call(bsc_ws, "settings/get")
        assert result["success"] is True
        assert result["result"]["settings"] == DEFAULT_SETTINGS

    async def test_update_partial(self, bsc_ws, hass):
        result = await ws_call(
            bsc_ws, "settings/update", hide_checked=True, notify_on_add=True
        )
        assert result["success"] is True
        settings = result["result"]["settings"]
        assert settings["hide_checked"] is True
        assert settings["notify_on_add"] is True
        # omitted keys are untouched
        assert settings["notify_service"] == DEFAULT_SETTINGS["notify_service"]
        # the change is persisted (a fresh store instance sees it)
        fresh = BetterShoppingCartStore(hass)
        await fresh.async_load()
        assert fresh.settings()["hide_checked"] is True

    async def test_update_layout_references(self, bsc_ws):
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(
            bsc_ws,
            "settings/update",
            default_layout_id=layout_id,
            active_list_id=shopping_list["id"],
        )
        settings = result["result"]["settings"]
        assert settings["default_layout_id"] == layout_id
        assert settings["active_list_id"] == shopping_list["id"]

    async def test_update_clears_layout(self, bsc_ws):
        layouts = await ws_call(bsc_ws, "layouts/list")
        layout_id = layouts["result"]["layouts"][0]["id"]
        await ws_call(
            bsc_ws, "settings/update", default_layout_id=layout_id
        )
        # an explicit null clears the reference
        result = await ws_call(
            bsc_ws, "settings/update", default_layout_id=None
        )
        assert result["result"]["settings"]["default_layout_id"] is None

    async def test_update_unknown_key_rejected(self, bsc_ws):
        result = await ws_call(bsc_ws, "settings/update", bogus_key=1)
        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_update_unknown_layout(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "settings/update", default_layout_id="does-not-exist"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown layout" in result["error"]["message"]

    async def test_update_unknown_active_list(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "settings/update", active_list_id="does-not-exist"
        )
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]


class TestItemNotifications:
    """M9: the notify service is called on items/add when enabled."""

    async def _register_fake_service(self, hass, service="demo"):
        calls: list = []

        async def fake(call) -> None:
            calls.append(call)

        hass.services.async_register("notify", service, fake)
        return calls

    async def test_add_item_notifies_when_enabled(self, bsc_ws, hass, hass_admin_user):
        calls = await self._register_fake_service(hass)
        await ws_call(
            bsc_ws,
            "settings/update",
            notify_on_add=True,
            notify_service="notify.demo",
        )
        shopping_list = await create_list(bsc_ws, "Test List")
        added = await add_item(bsc_ws, shopping_list["id"], "Salsa")
        await hass.async_block_till_done()
        assert added["name"] == "Salsa"
        assert len(calls) == 1
        call = calls[0]
        assert call.domain == "notify"
        assert call.service == "demo"
        assert (
            call.data["message"]
            == f"{hass_admin_user.name} added Salsa to Test List"
        )

    async def test_add_item_silent_when_disabled(self, bsc_ws, hass):
        calls = await self._register_fake_service(hass)
        # notify_on_add is False by default: no service call
        shopping_list = await create_list(bsc_ws, "Test List")
        await add_item(bsc_ws, shopping_list["id"], "Salsa")
        await hass.async_block_till_done()
        assert calls == []

    async def test_add_item_succeeds_when_service_missing(self, bsc_ws, hass):
        await ws_call(
            bsc_ws,
            "settings/update",
            notify_on_add=True,
            notify_service="notify.does_not_exist",
        )
        shopping_list = await create_list(bsc_ws, "Test List")
        added = await add_item(bsc_ws, shopping_list["id"], "Salsa")
        await hass.async_block_till_done()
        # the add is unaffected by the missing notify service
        assert added["name"] == "Salsa"

    async def test_add_item_succeeds_with_invalid_service(self, bsc_ws, hass):
        # not in the "<domain>.<service>" form
        await ws_call(
            bsc_ws, "settings/update", notify_on_add=True, notify_service="nope"
        )
        shopping_list = await create_list(bsc_ws, "Test List")
        added = await add_item(bsc_ws, shopping_list["id"], "Salsa")
        assert added["name"] == "Salsa"


class TestSubscribe:
    async def test_subscribe_streams_update_events(self, bsc_ws):
        shopping_list = await create_list(bsc_ws)
        result = await ws_call(bsc_ws, "subscribe", list_id=shopping_list["id"])
        assert result["success"] is True
        subscription_id = result["id"]

        # a mutating command streams the update event before its own result
        await bsc_ws.send_json_auto_id(
            {"type": "better_shopping_cart/sections/create", "name": "Trigger"}
        )
        event = await bsc_ws.receive_json()
        assert event["id"] == subscription_id
        assert event["type"] == "event"
        assert event["event"] == "better_shopping_cart/updated"
        result = await bsc_ws.receive_json()
        assert result["success"] is True
        assert result["result"]["section"]["name"] == "Trigger"

    async def test_subscribe_unknown_list(self, bsc_ws):
        result = await ws_call(bsc_ws, "subscribe", list_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown list" in result["error"]["message"]


async def test_unknown_command(bsc_ws):
    result = await ws_call(bsc_ws, "sections/boom")
    assert result["success"] is False
    assert result["error"]["code"] == "unknown_command"
