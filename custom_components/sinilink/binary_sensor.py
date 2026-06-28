"""Binary sensor platform for Sinilink."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_MAC
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .sinilink import SinilinkInstance

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up binary sensors from a config entry."""
    mac = entry.data.get(CONF_MAC)
    instance = hass.data[DOMAIN][mac]

    async_add_entities([SinilinkConnectionSensor(instance, mac, entry.title)])

class SinilinkConnectionSensor(BinarySensorEntity):
    """Representation of a Sinilink connection sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = True

    def __init__(self, instance: SinilinkInstance, mac: str, name: str):
        """Initialize the sensor."""
        self._instance = instance
        self._mac = mac
        self._attr_name = f"{name} Connection"
        self._attr_unique_id = f"{mac}_connection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer="Sinilink",
            model="Bluetooth Amplifier",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        return self._instance._device is not None and self._instance._device.is_connected
