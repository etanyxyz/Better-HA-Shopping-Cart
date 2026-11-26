"""WebSocket API tests for sections and layouts (PLAN.md M2).

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


class TestSections:
    async def test_list_returns_seeded_sections(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/list")
        assert result["success"] is True
        sections = result["result"]["sections"]
        assert [s["name"] for s in sections] == [name for name, _ in DEFAULT_SECTIONS]
        assert [s["order"] for s in sections] == list(range(len(DEFAULT_SECTIONS)))
        assert all(s["id"] and s["icon"] for s in sections)

    async def test_create_section(self, bsc_ws):
        result = await ws_call(
            bsc_ws, "sections/create", name="Test Section", icon="mdi:test"
        )
        assert result["success"] is True
        section = result["result"]["section"]
        assert section["name"] == "Test Section"
        assert section["icon"] == "mdi:test"
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

    async def test_update_section(self, bsc_ws):
        sections = await sections_by_id(bsc_ws)
        section_id, current = next(iter(sections.items()))
        result = await ws_call(
            bsc_ws, "sections/update", section_id=section_id, name="Renamed", icon="mdi:apple"
        )
        assert result["success"] is True
        section = result["result"]["section"]
        assert section["name"] == "Renamed"
        assert section["icon"] == "mdi:apple"
        assert section["order"] == current["order"]

    async def test_update_section_partial(self, bsc_ws):
        sections = await sections_by_id(bsc_ws)
        section_id, current = next(iter(sections.items()))
        # omitting ``name`` leaves it untouched
        result = await ws_call(bsc_ws, "sections/update", section_id=section_id, icon="mdi:egg")
        section = result["result"]["section"]
        assert section["name"] == current["name"]
        assert section["icon"] == "mdi:egg"

    async def test_update_section_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/update", section_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"
        assert "unknown section" in result["error"]["message"]

    async def test_delete_section(self, bsc_ws):
        sections = await sections_by_id(bsc_ws)
        section_id = next(iter(sections))
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

    async def test_delete_section_unknown_id(self, bsc_ws):
        result = await ws_call(bsc_ws, "sections/delete", section_id="does-not-exist")
        assert result["success"] is False
        assert result["error"]["code"] == "home_assistant_error"

    async def test_reorder_sections_persists(self, bsc_ws, hass):
        sections = await sections_by_id(bsc_ws)
        ordered_ids = list(sections)
        reversed_ids = list(reversed(ordered_ids))

        result = await ws_call(bsc_ws, "sections/reorder", ordered_ids=reversed_ids)
        assert result["success"] is True
        assert result["result"] == {}

        after = await ws_call(bsc_ws, "sections/list")
        listed = after["result"]["sections"]
        assert [s["id"] for s in listed] == reversed_ids
        assert [s["order"] for s in listed] == list(range(len(listed)))

        # a fresh store instance (e.g. after a restart) sees the persisted order
        fresh = BetterShoppingCartStore(hass)
        await fresh.async_load()
        assert [s.id for s in fresh.sections()] == reversed_ids

    async def test_reorder_ignores_unknown_ids(self, bsc_ws):
        sections = await sections_by_id(bsc_ws)
        ordered_ids = list(sections)
        result = await ws_call(
            bsc_ws,
            "sections/reorder",
            ordered_ids=[ordered_ids[-1], "bogus-id", ordered_ids[0]],
        )
        assert result["success"] is True
        after = await sections_by_id(bsc_ws)
        assert after[ordered_ids[-1]]["order"] == 0
        assert after[ordered_ids[0]]["order"] == 1

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


async def test_unknown_command(bsc_ws):
    result = await ws_call(bsc_ws, "sections/boom")
    assert result["success"] is False
    assert result["error"]["code"] == "unknown_command"
