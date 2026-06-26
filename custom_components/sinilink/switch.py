"""Switch platform for Sinilink Amplifier."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .sinilink import SinilinkInstance

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Sinilink switch from a config entry."""
    data = entry.data
    name = data.get(CONF_NAME, "Sinilink Amplifier")
    mac = data[CONF_MAC]
    
    instance = hass.data[DOMAIN][mac]
    async_add_entities([SinilinkPromptToneSwitch(name, instance)])


class SinilinkPromptToneSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Sinilink Amplifier Prompt Tone Switch."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bell-ring"
    _attr_should_poll = True

    def __init__(self, name: str, amp_instance: SinilinkInstance) -> None:
        """Initialize the switch."""
        self._amp = amp_instance
        self._name = f"{name} Prompt Tone"
        self._hass = amp_instance.hass
        self._amp.register_callback(self.async_schedule_update_ha_state)

    @property
    def name(self) -> str:
        """Return the display name."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if the prompt tone is on."""
        return self._amp.prompt_tone

    @property
    def device_info(self):
        """Return device information for device registry."""
        return {
            "identifiers": {(DOMAIN, self._amp.mac)},
            "name": self._name.replace(" Prompt Tone", ""),
            "manufacturer": "Sinilink",
            "model": "Amplifier",
            "connections": {("mac", self._amp.mac)},
        }

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"{self._amp.mac}_prompt_tone"

    async def async_added_to_hass(self) -> None:
        """Restore last known state on HA startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in ("on", "off"):
            self._amp._prompt_tone = (last_state.state == "on")
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the prompt tone on."""
        if not self._amp.prompt_tone:
            await self._amp.toggle_prompt_tone()
            # Optimistic update
            self._amp._prompt_tone = True
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the prompt tone off."""
        if self._amp.prompt_tone:
            await self._amp.toggle_prompt_tone()
            # Optimistic update
            self._amp._prompt_tone = False
            self.async_schedule_update_ha_state()

    async def async_update(self) -> None:
        """Watchdog to maintain connection and update state."""
        if getattr(self._amp, "_device", None) and self._amp._device.is_connected:
            return

        _LOGGER.debug("Attempting to connect to %s for switch", self._amp.mac)
        await self._amp.connect()
        self.async_schedule_update_ha_state()
