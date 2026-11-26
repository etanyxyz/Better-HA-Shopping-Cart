"""Config flow for Better Shopping Cart."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_NAME, DOMAIN

CONFIG_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Single-step confirm flow for Better Shopping Cart.

    The integration needs no credentials; the only option is an optional
    display name for the entry.
    """

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the (only) step of the user-initiated flow."""
        if user_input is not None:
            title = user_input.get(CONF_NAME) or "Better Shopping Cart"
            return self.async_create_entry(title=title)
        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)
