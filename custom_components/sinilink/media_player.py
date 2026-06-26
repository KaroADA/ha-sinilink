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
from homeassistant.helpers.restore_state import RestoreEntity

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
    name = config[CONF_NAME]
    mac = config[CONF_MAC]
    
    hass.data.setdefault(DOMAIN, {})
    if mac not in hass.data[DOMAIN]:
        hass.data[DOMAIN][mac] = SinilinkInstance(mac, hass)
        
    add_entities([SinilinkAmplifier(name, hass.data[DOMAIN][mac])])


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Sinilink media player from a config entry."""
    data = entry.data
    name = data.get(CONF_NAME, "Sinilink Amplifier")
    mac = data[CONF_MAC]
    
    instance = hass.data[DOMAIN][mac]
    async_add_entities([SinilinkAmplifier(name, instance)])


class SinilinkAmplifier(MediaPlayerEntity, RestoreEntity):
    """Representation of a Sinilink Amplifier."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_icon = "mdi:audio-video"
    _attr_should_poll = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )
    def __init__(self, name, amp_instance):
        """Initialize a SinilinkAmplifier."""
        self._amp = amp_instance
        self._name = name
        self._hass = amp_instance.hass
        self._attr_state = MediaPlayerState.OFF
        self._source_list = {"AUX", "Bluetooth"}
        self._source = self.source_list[0]
        self._muted = False
        self._media_volume_level = 0.0
        self._saved_volume_level = 0.1
        self._volume_max = 255
        self._amp.register_callback(self.async_schedule_update_ha_state)

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
        return getattr(self._amp, "_source", self.source_list[0])

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the media player."""
        if not self._amp.is_on:
            return MediaPlayerState.OFF
            
        if getattr(self._amp, "_is_playing", False):
            return MediaPlayerState.PLAYING
            
        return MediaPlayerState.PAUSED

    @property
    def volume_level(self):
        """Return volume level of the media player (0..1)."""
        if self._amp.volume is not None:
            return self._amp.volume / self._volume_max
        return 0.0
        
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

    async def async_added_to_hass(self) -> None:
        """Restore last known state on HA startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state:
            return

        # Restore power
        is_on = last_state.state == MediaPlayerState.ON
        self._attr_state = MediaPlayerState.ON if is_on else MediaPlayerState.OFF

        # Restore volume
        vol_level = last_state.attributes.get("volume_level")
        if isinstance(vol_level, (int, float)):
            self._media_volume_level = max(0.0, min(1.0, float(vol_level)))

        # Restore mute
        muted = last_state.attributes.get("is_volume_muted")
        if muted is None:
            muted = last_state.attributes.get("volume_muted")
        if isinstance(muted, bool):
            self._muted = muted

        # Restore source if available
        src = last_state.attributes.get("source")
        if isinstance(src, str) and src in self.source_list:
            self._source = src

        # Cache into BLE instance without I/O
        self._amp.set_cached_state(
            is_on=is_on,
            volume=int(self._media_volume_level * self._volume_max),
        )

        self.async_write_ha_state()

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
        _LOGGER.debug("Set volume %s, %s", volume, int(volume * self._volume_max))

        await self._amp.set_volume(int(volume * self._volume_max))
        self._media_volume_level = volume
        self.async_schedule_update_ha_state()

    async def async_mute_volume(self, mute: bool):
        """Mute AMP."""
        if mute:
            await self._amp.pause()
            _LOGGER.debug("Mute")
        else:
            await self._amp.play()
            _LOGGER.debug("Unmute")

        self._muted = mute
        self.async_schedule_update_ha_state()

    async def async_select_source(self, source):
        """Select input source."""
        _LOGGER.debug("Set source %s", source)
        self._source = source
        if source == "AUX":
            await self._amp.aux()
        else:
            await self._amp.bluetooth()

        self.async_schedule_update_ha_state()

    async def async_media_play(self):
        """Send play command."""
        await self._amp.play()
        self.async_schedule_update_ha_state()

    async def async_media_pause(self):
        """Send pause command."""
        await self._amp.pause()
        self.async_schedule_update_ha_state()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._amp.next_track()
        self.async_schedule_update_ha_state()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._amp.previous_track()
        self.async_schedule_update_ha_state()

    async def async_update(self) -> None:
        """Watchdog to maintain connection and update state."""
        if getattr(self._amp, "_device", None) and self._amp._device.is_connected:
            return

        _LOGGER.debug("Attempting to connect to %s", self._amp.mac)
        await self._amp.connect()
        
        self.async_schedule_update_ha_state()
