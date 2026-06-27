"""Support for Sinilink number entities."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .sinilink import SinilinkInstance

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Sinilink number platform via configuration.yaml."""
    name = config.get(CONF_NAME, "Sinilink Amplifier")
    mac = config[CONF_MAC]
    
    instance = hass.data[DOMAIN][mac]
    add_entities([SinilinkVolumeStepNumber(name, instance)])


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Sinilink number based on a config entry."""
    data = entry.data
    name = data.get(CONF_NAME, "Sinilink Amplifier")
    mac = data[CONF_MAC]
    
    instance = hass.data[DOMAIN][mac]
    async_add_entities([SinilinkVolumeStepNumber(name, instance)])


class SinilinkVolumeStepNumber(NumberEntity, RestoreEntity):
    """Representation of a Sinilink Volume Step Number."""

    _attr_has_entity_name = True
    _attr_name = "Volume Step"
    _attr_icon = "mdi:volume-plus"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_native_unit_of_measurement = None

    def __init__(self, name: str, amp_instance: SinilinkInstance) -> None:
        """Initialize the number entity."""
        self._amp = amp_instance
        self._attr_unique_id = f"{amp_instance.mac}_volume_step"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, amp_instance.mac)},
            "name": name,
            "manufacturer": "Sinilink",
            "model": "Amplifier",
            "connections": {("mac", amp_instance.mac)},
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._amp.volume_step

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value (enforce integer)."""
        self._amp.volume_step = int(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore last known state on HA startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._amp.volume_step = int(float(last_state.state))
            except ValueError:
                pass
        self.async_write_ha_state()
