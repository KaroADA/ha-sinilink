"""Support for Sinilink Amplifier media player."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .sinilink import SinilinkInstance

DOMAIN = "sinilink"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_MAC): cv.string,
})


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Sinilink Amp platform."""
    amp = {
        "name": config[CONF_NAME],
        "mac": config[CONF_MAC],
        "hass": hass
    }
    
    add_entities([SinilinkAmplifier(amp)])


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Sinilink media player from a config entry."""
    data = entry.data
    amp = {
        "name": data.get(CONF_NAME, "Sinilink Amplifier"),
        "mac": data[CONF_MAC],
        "hass": hass
    }
    async_add_entities([SinilinkAmplifier(amp)])


class SinilinkAmplifier(MediaPlayerEntity):
    """Representation of a Sinilink Amplifier."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_icon = "mdi:audio-video"
    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, amp):
        """Initialize a SinilinkAmplifier."""
        self._amp = SinilinkInstance(amp["mac"], amp["hass"])
        self._name = amp["name"]
        self._hass = amp["hass"]
        self._attr_state = MediaPlayerState.OFF
        self._source_list = {"AUX", "Bluetooth"}
        self._source = self.source_list[0]
        self._muted = False
        self._media_volume_level = 0.2
        self._volume_max = 255

    @property
    def name(self) -> str:
        """Return the display name."""
        return self._name

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return sorted(self._source_list)

    @property
    def source(self) -> str:
        """Return the source."""
        return self._source

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the media player."""
        if self._amp.is_on:
            return MediaPlayerState.ON
        
        return MediaPlayerState.OFF

    @property
    def volume_level(self):
        """Return volume level of the media player (0..1)."""
        return self._media_volume_level
        
    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def device_info(self):
        """Return device information for device registry."""
        return {
            "identifiers": {(DOMAIN, self._amp.mac)},
            "name": self._name,
            "manufacturer": "Sinilink",
            "model": "Amplifier",
            "connections": {("mac", self._amp.mac)},
        }

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return self._amp.mac

    def update(self) -> None:
        """Update the state of the media player."""
        if self._amp.is_on:
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF

        self._media_volume_level = self._amp.volume / self._volume_max
        return True

    async def async_turn_off(self):
        """Turn AMP power off."""
        await self._amp.turn_off()
        self.async_schedule_update_ha_state()

    async def async_turn_on(self):
        """Turn AMP power on."""
        await self._amp.turn_on()
        self.async_schedule_update_ha_state()

    async def async_set_volume_level(self, volume: float):
        """Set AMP volume (0 to 1)."""
        _LOGGER.warning("Set volume %s, %s", volume, int(volume * self._volume_max))

        await self._amp.set_volume(int(volume * self._volume_max))
        self._media_volume_level = volume
        self.async_schedule_update_ha_state()

    async def async_mute_volume(self, mute: bool):
        """Mute AMP."""
        await self._amp.set_volume(int(self._media_volume_level * self._volume_max) * int(mute))
        self._muted = mute
        self.async_schedule_update_ha_state()

    async def async_select_source(self, source):
        """Select input source."""
        _LOGGER.warning("Set source %s", source)
        self._source = source
        if source == "AUX":
            await self._amp.aux()
        else:
            await self._amp.bluetooth()

        self.async_schedule_update_ha_state()