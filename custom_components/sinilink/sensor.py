"""Sensor platform for Sinilink."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_MAC, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import async_last_service_info

from .const import DOMAIN
from .sinilink import SinilinkInstance

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up sensors from a config entry."""
    mac = entry.data.get(CONF_MAC)
    instance = hass.data[DOMAIN][mac]
    name = entry.title

    async_add_entities([
        SinilinkRSSISensor(hass, instance, mac, name),
        SinilinkLastSeenSensor(instance, mac, name)
    ])

class SinilinkRSSISensor(SensorEntity):
    """Representation of a Sinilink RSSI sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, instance: SinilinkInstance, mac: str, name: str):
        """Initialize the sensor."""
        self.hass = hass
        self._instance = instance
        self._mac = mac
        self._attr_name = f"{name} Signal Strength"
        self._attr_unique_id = f"{mac}_rssi"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer="Sinilink",
            model="Bluetooth Amplifier",
        )
        self._last_rssi = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        
        # Try both connectable and non-connectable
        service_info = async_last_service_info(self.hass, self._mac, connectable=False)
        if not service_info:
            service_info = async_last_service_info(self.hass, self._mac, connectable=True)

        if service_info and hasattr(service_info, 'rssi') and service_info.rssi is not None:
            self._last_rssi = service_info.rssi
            return self._last_rssi
            
        # Fallback to bleak device if async_last_service_info fails
        ble_device = bluetooth.async_ble_device_from_address(self.hass, self._mac, connectable=False)
        if not ble_device:
            ble_device = bluetooth.async_ble_device_from_address(self.hass, self._mac, connectable=True)

        if ble_device:
            if hasattr(ble_device, 'details') and isinstance(ble_device.details, dict):
                props = ble_device.details.get("props", {})
                if "RSSI" in props:
                    self._last_rssi = props["RSSI"]
                    return self._last_rssi
            
            if hasattr(ble_device, 'rssi') and ble_device.rssi is not None:
                self._last_rssi = ble_device.rssi
                return self._last_rssi
            
        return self._last_rssi

class SinilinkLastSeenSensor(SensorEntity):
    """Representation of a Sinilink Last Seen sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = True

    def __init__(self, instance: SinilinkInstance, mac: str, name: str):
        """Initialize the sensor."""
        self._instance = instance
        self._mac = mac
        self._attr_name = f"{name} Last Seen"
        self._attr_unique_id = f"{mac}_last_seen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer="Sinilink",
            model="Bluetooth Amplifier",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._instance.last_seen
