"""The Sinilink Amplifier Integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_MAC

from .const import DOMAIN
from .sinilink import SinilinkInstance

PLATFORMS = ["media_player", "switch", "number"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    mac = entry.data.get(CONF_MAC)
    instance = SinilinkInstance(mac, hass)
    hass.data[DOMAIN][mac] = instance

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    mac = entry.data.get(CONF_MAC)
    if unload_ok and mac in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(mac)
    return unload_ok