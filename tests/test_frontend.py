"""Panel registration and static asset tests (PLAN.md M5)."""
from __future__ import annotations

from homeassistant.components.frontend import DATA_PANELS

from custom_components.better_shopping_cart.const import (
    PANEL_MODULE_URL,
    PANEL_URL_PATH,
)


async def test_panel_registered(hass, bsc_entry):
    """The config entry registers the /shopping-cart sidebar panel."""
    panel = hass.data[DATA_PANELS][PANEL_URL_PATH]
    assert panel.component_name == "custom"
    assert panel.frontend_url_path == "shopping-cart"
    assert panel.sidebar_title == "Shopping Cart"
    assert panel.sidebar_icon == "mdi:cart"
    assert panel.require_admin is False
    custom = panel.config["_panel_custom"]
    assert custom["name"] == "better-shopping-cart-panel"
    assert custom["module_url"] == PANEL_MODULE_URL
    assert custom["embed_iframe"] is False
    assert custom["trust_external"] is False


async def test_get_panels_lists_panel(bsc_ws):
    """The frontend ``get_panels`` WS command exposes our panel."""
    await bsc_ws.send_json_auto_id({"type": "get_panels"})
    result = await bsc_ws.receive_json()
    panel = result["result"]["shopping-cart"]
    assert panel["component_name"] == "custom"
    assert panel["title"] == "Shopping Cart"
    assert panel["icon"] == "mdi:cart"
    assert panel["url_path"] == "shopping-cart"
    assert panel["config"]["_panel_custom"]["module_url"] == PANEL_MODULE_URL


async def test_static_assets_served(hass_client, bsc_entry):
    """The frontend/ directory is served under /bsc/ with the real files."""
    client = await hass_client()
    js = await client.get("/bsc/better-shopping-cart-panel.js")
    assert js.status == 200
    assert "better-shopping-cart-panel" in await js.text()
    css = await client.get("/bsc/panel.css")
    assert css.status == 200
    assert "--primary-background-color" in await css.text()
    missing = await client.get("/bsc/missing.js")
    assert missing.status == 404


async def test_panel_url_serves_index(hass_client, bsc_entry):
    """GET /shopping-cart serves the frontend index page (direct navigation)."""
    client = await hass_client()
    resp = await client.get("/shopping-cart")
    assert resp.status == 200
    assert "Home Assistant" in await resp.text()


async def test_panel_removed_on_unload(hass, bsc_entry):
    """Unloading the entry removes the panel registration."""
    assert await hass.config_entries.async_unload(bsc_entry.entry_id)
    assert PANEL_URL_PATH not in hass.data[DATA_PANELS]
