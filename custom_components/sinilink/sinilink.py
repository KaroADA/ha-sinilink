"""Sinilink amplifier communication module."""
import asyncio
import logging

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from crccheck.crc import Crc8Maxim

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

WRITE_UUID = "0000ae10-0000-1000-8000-00805f9b34fb"
_LOGGER = logging.getLogger(__name__)


async def discover():
    """Discover Bluetooth LE devices."""
    devices = await BleakScanner.discover()
    _LOGGER.debug("Discovered devices: %s", [{"address": device.address, "name": device.name} for device in devices])
    return [device for device in devices if device.name.startswith("Sinilink-APP")]


class SinilinkInstance:
    """Instance of a Sinilink amplifier."""

    def __init__(self, mac, hass: HomeAssistant) -> None:
        """Initialize the Sinilink instance."""
        self._mac = mac
        self.hass = hass
        self._device: BleakClient | None = None
        self._is_on = False
        self._volume = 0

    async def _send(self, data: bytearray):
        """Send data to the amplifier."""
        _LOGGER.debug(''.join(format(x, ' 03x') for x in data))
        
        if not self._device or not self._device.is_connected:
            _LOGGER.debug("Device %s not connected, attempting to connect", self._mac)
            if not await self.connect():
                _LOGGER.error("Failed to connect to %s before sending data. Aborting send", self._mac)
                return

        crcinst = Crc8Maxim()
        crcinst.process(data)
        payload = data + crcinst.finalbytes()
        
        try:
            await self._device.write_gatt_char(WRITE_UUID, payload)
        except BleakError as e:
            _LOGGER.warning("BleakError during write to %s: %s. Attempting to reconnect and retry", self._mac, e)
            if await self.connect():
                _LOGGER.debug("Reconnected to %s successfully. Retrying write", self._mac)
                try:
                    await self._device.write_gatt_char(WRITE_UUID, payload)
                except BleakError as e_retry:
                    _LOGGER.error("BleakError on retry write to %s after reconnect: %s", self._mac, e_retry)
                except Exception as e_retry_other:
                    _LOGGER.error("Unexpected error on retry write to %s after reconnect: %s", self._mac, e_retry_other)
            else:
                _LOGGER.error("Failed to reconnect to %s after write error", self._mac)
        except Exception as e:
            _LOGGER.error("Unexpected error during write to %s: %s", self._mac, e)

    @property
    def mac(self):
        """Return the MAC address."""
        return self._mac

    @property
    def is_on(self):
        """Return if the amplifier is on."""
        return self._is_on

    @property
    def volume(self):
        """Return the current volume."""
        return self._volume

    async def set_volume(self, intensity: int):
        """Set the volume of the amplifier."""
        volume = int(intensity / 5)

        header = bytes.fromhex("7e0f1d")
        command = (volume).to_bytes(1, 'big')
        params = bytes.fromhex("00000000000000000000")
        sufix = (volume + 170).to_bytes(1, 'big')

        await self._send(header + command + params + sufix)
        self._volume = intensity

    async def turn_on(self):
        """Turn on the amplifier."""
        self._is_on = True

        volume = 7

        if self._volume is not None:
            volume = int(self._volume / 5)

        header = bytes.fromhex("7e0f1d")
        command = (volume).to_bytes(1, 'big')
        params = bytes.fromhex("00000000000000000000")
        sufix = (volume + 170).to_bytes(1, 'big')

        await self._send(header + command + params + sufix)

    async def turn_off(self):
        """Turn off the amplifier."""
        self._is_on = False

        header = bytes.fromhex("7e0f1d")
        command = bytes.fromhex("00")
        params = bytes.fromhex("00000000000000000000")
        sufix = bytes.fromhex("aa")

        await self._send(header + command + params + sufix)

    async def bluetooth(self):
        """Switch to Bluetooth source."""
        command = bytes.fromhex("7e05140097")
        await self._send(command)

    async def aux(self):
        """Switch to AUX source."""
        command = bytes.fromhex("7e05160099")
        await self._send(command)

    async def connect(self) -> bool:
        """Connect to the amplifier."""
        _LOGGER.debug("Attempting to connect to %s", self._mac)
        if self._device and self._device.is_connected:
            _LOGGER.debug("Already connected to %s", self._mac)
            return True

        ble_device = bluetooth.async_ble_device_from_address(self.hass, str(self._mac), connectable=True)
        if not ble_device:
            _LOGGER.error("Device with MAC %s not found by Home Assistant Bluetooth", self._mac)
            if self._device:
                try:
                    if self._device.is_connected:
                        await self._device.disconnect()
                except BleakError:
                    pass
                except Exception:
                    pass
                self._device = None
            return False

        _LOGGER.debug("Found BLEDevice for %s: %s (%s)", self._mac, ble_device.name, ble_device.address)
        
        if not ble_device.address:
            _LOGGER.error("BLEDevice for %s has no address. Cannot connect", self._mac)
            self._device = None
            return False

        self._device = BleakClient(ble_device)

        try:
            await self._device.connect(timeout=20)
            await asyncio.sleep(1)
            if self._device.is_connected:
                _LOGGER.info("Successfully connected to %s", self._mac)
                return True
            
            _LOGGER.error("Connection attempt to %s finished, but device is not connected", self._mac)
        except BleakError as e:
            _LOGGER.error("BleakError during connect to %s: %s", self._mac, e)
        except Exception as e:
            _LOGGER.error("Unexpected error during connect to %s: %s", self._mac, e)
        
        if self._device:
            try:
                await self._device.disconnect()
            except BleakError:
                pass
            except Exception:
                pass
        self._device = None
        return False

    async def disconnect(self):
        """Disconnect from the amplifier."""
        _LOGGER.debug("Disconnecting from %s", self._mac)
        if self._device and self._device.is_connected:
            try:
                await self._device.disconnect()
                _LOGGER.info("Successfully disconnected from %s", self._mac)
            except BleakError as e:
                _LOGGER.warning("BleakError during disconnect from %s: %s", self._mac, e)
            except Exception as e:
                _LOGGER.warning("Unexpected error during disconnect from %s: %s", self._mac, e)
        
        self._device = None
        _LOGGER.debug("Client instance for %s cleared", self._mac)