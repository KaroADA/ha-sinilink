"""Config flow for Sinilink Amplifier integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SinilinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sinilink Amplifier."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors = {}
        discovered_devices = []

        # Try to discover BLE devices using HA Bluetooth API
        ble_devices = bluetooth.async_discovered_service_info(self.hass)
        for dev in ble_devices:
            if dev.name and dev.name.startswith("Sinilink-APP"):
                discovered_devices.append((dev.address, dev.name))

        if user_input is not None:
            if discovered_devices and user_input.get(CONF_MAC) == "manual":
                return await self.async_step_manual()
            
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or user_input[CONF_MAC],
                data={
                    CONF_NAME: user_input.get(CONF_NAME, ""),
                    CONF_MAC: user_input[CONF_MAC],
                },
            )

        if discovered_devices:
            device_choices = {
                f"{name} ({mac})": mac for mac, name in discovered_devices
            }
            device_choices["Enter MAC manually"] = "manual"
            schema = vol.Schema(
                {
                    vol.Optional(CONF_NAME): str,
                    vol.Required(CONF_MAC): vol.In(list(device_choices.values())),
                }
            )
            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                description_placeholders={"devices": "\n".join(device_choices.keys())},
                errors=errors,
            )

        return await self.async_step_manual()

    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        """Handle manual entry step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or user_input[CONF_MAC],
                data={
                    CONF_NAME: user_input.get(CONF_NAME, ""),
                    CONF_MAC: user_input[CONF_MAC],
                },
            )
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Required(CONF_MAC): str,
            }
        )
        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
        )