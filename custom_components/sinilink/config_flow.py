"""Config flow for Sinilink Amplifier integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def perform_auto_scan(hass: HomeAssistant, mac: str) -> list[str]:
    """Perform auto scan of sources using SinilinkInstance."""
    import asyncio
    from .sinilink import SinilinkInstance
    
    instance = hass.data.get(DOMAIN, {}).get(mac)
    created = False
    if not instance:
        instance = SinilinkInstance(mac, hass)
        created = True
        
    if getattr(instance, "_device", None) is None or not instance._device.is_connected:
        success = await instance.connect()
        if not success:
            _LOGGER.warning("Auto scan failed: could not connect to %s", mac)
            return ["Bluetooth", "AUX", "USB", "TF Card", "PC Audio"]
            
    if created:
        # Give background request_system_settings time to finish to ensure we know the true prompt tone state
        await asyncio.sleep(1.0)
            
    supported = set()
    original_source = getattr(instance, "_source", "Bluetooth")
    original_volume = getattr(instance, "_volume", 0)
    original_prompt_tone = getattr(instance, "_prompt_tone", True)
    
    # Mute during scan
    await instance.set_volume(0)
    await asyncio.sleep(0.3)
    
    # Mute prompt tone if it's currently on
    if original_prompt_tone:
        await instance.toggle_prompt_tone()
        await asyncio.sleep(0.3)
    
    test_sources = [
        ("AUX", instance.aux),
        ("Bluetooth", instance.bluetooth),
        ("USB", instance.usb),
        ("TF Card", instance.tf_card),
        ("PC Audio", instance.pc_audio)
    ]
    
    for name, func in test_sources:
        await func()
        await asyncio.sleep(0.5)
        if getattr(instance, "_source", None) == name:
            supported.add(name)
        
    # Restore
    if original_source == "AUX":
        await instance.aux()
    else:
        await instance.bluetooth()
    await asyncio.sleep(0.5)
    
    if original_prompt_tone:
        await instance.toggle_prompt_tone()
        await asyncio.sleep(0.3)
        
    await instance.set_volume(original_volume)
    
    if created:
        await instance.disconnect()
        
    return list(supported)


class SinilinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sinilink Amplifier."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SinilinkOptionsFlowHandler(config_entry)

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
            
            self.name = user_input.get(CONF_NAME, "")
            self.mac = user_input[CONF_MAC]
            return await self.async_step_sources()

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
            self.name = user_input.get(CONF_NAME, "")
            self.mac = user_input[CONF_MAC]
            return await self.async_step_sources()
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

    async def async_step_sources(self, user_input: dict[str, Any] | None = None):
        """Configure sources step."""
        if user_input is not None:
            if user_input.get("auto_scan"):
                sources = await perform_auto_scan(self.hass, self.mac)
            else:
                sources = user_input.get("sources", [])

            return self.async_create_entry(
                title=self.name or self.mac,
                data={
                    CONF_NAME: self.name,
                    CONF_MAC: self.mac,
                    "sources": sources,
                },
            )

        schema = vol.Schema(
            {
                vol.Optional("auto_scan", default=False): bool,
                vol.Optional("sources", default=["Bluetooth", "AUX", "USB", "TF Card", "PC Audio"]): cv.multi_select(
                    {"Bluetooth": "Bluetooth", "AUX": "AUX", "USB": "USB", "TF Card": "TF Card", "PC Audio": "PC Audio"}
                ),
            }
        )
        return self.async_show_form(step_id="sources", data_schema=schema)


class SinilinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Sinilink options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            if user_input.get("auto_scan"):
                mac = self._config_entry.data.get(CONF_MAC)
                sources = await perform_auto_scan(self.hass, mac)
            else:
                sources = user_input.get("sources", [])
                
            return self.async_create_entry(title="", data={"sources": sources})

        default_sources = self._config_entry.options.get(
            "sources", self._config_entry.data.get("sources", ["Bluetooth", "AUX", "USB", "TF Card", "PC Audio"])
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("auto_scan", default=False): bool,
                    vol.Optional("sources", default=default_sources): cv.multi_select(
                        {"Bluetooth": "Bluetooth", "AUX": "AUX", "USB": "USB", "TF Card": "TF Card", "PC Audio": "PC Audio"}
                    ),
                }
            ),
        )