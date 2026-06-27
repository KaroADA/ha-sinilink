"""Sinilink amplifier communication module."""
import asyncio
import logging

from bleak import BleakClient, BleakScanner
from bleak_retry_connector import establish_connection
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

WRITE_UUID = "0000ae10-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ae04-0000-1000-8000-00805f9b34fb"
_LOGGER = logging.getLogger(__name__)

class SinilinkInstance:
    """Instance of a Sinilink amplifier."""

    def __init__(self, mac, hass: HomeAssistant) -> None:
        """Initialize the Sinilink instance."""
        self._mac = mac
        self.hass = hass
        self._device: BleakClient | None = None
        self._is_on = False
        self._volume = 0
        self._source = "AUX"
        self._is_playing = False
        self._saved_volume = 7
        self._prompt_tone = True
        self.volume_step = 2
        self._update_callbacks = []
        self._connect_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._buffer = bytearray()

    def register_callback(self, callback):
        """Register a callback to be called on state updates."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    async def _send(self, data: bytearray):
        """Send data to the amplifier."""
        checksum = sum(data) & 0xFF
        payload = bytearray(data)
        payload.append(checksum)

        _LOGGER.debug("Preparing to send data to %s: %s", self._mac, data.hex())
        
        if not self._device or not self._device.is_connected:
            _LOGGER.debug("Device %s not connected, attempting to connect", self._mac)
            if not await self.connect():
                _LOGGER.error("Failed to connect to %s before sending data. Aborting send", self._mac)
                return

        async with self._write_lock:
            _LOGGER.debug("Final payload to send to %s: %s", self._mac, payload.hex())
            try:
                await self._device.write_gatt_char(WRITE_UUID, payload)
                await asyncio.sleep(0.1) # Debounce writes to prevent dropping
            except BleakError as e:
                _LOGGER.warning("BleakError during write to %s: %s. Attempting to reconnect and retry", self._mac, e)
                if await self.connect():
                    _LOGGER.debug("Reconnected to %s successfully. Retrying write", self._mac)
                    try:
                        await self._device.write_gatt_char(WRITE_UUID, payload)
                        await asyncio.sleep(0.1)
                    except BleakError as e_retry:
                        _LOGGER.error("BleakError on retry write to %s after reconnect: %s", self._mac, e_retry)
                    except Exception as e_retry_other:
                        _LOGGER.error("Unexpected error on retry write to %s after reconnect: %s", self._mac, e_retry_other)
                else:
                    _LOGGER.error("Failed to reconnect to %s after write error", self._mac)
            except Exception as e:
                _LOGGER.error("Unexpected error during write to %s: %s", self._mac, e)

    async def _notification_handler(self, sender: int, data: bytearray):
        """Handle incoming notifications with robust buffering."""
        hex_string = ''.join(format(x, ' 03x') for x in data)
        _LOGGER.debug("RAW Notification from %s: %s", self._mac, hex_string)

        self._buffer.extend(data)
        
        while len(self._buffer) >= 8:
            if self._buffer[0] != 0x7e:
                idx = self._buffer.find(0x7e)
                if idx == -1:
                    _LOGGER.debug("Dropping junk data: %s", self._buffer.hex())
                    self._buffer.clear()
                    break
                _LOGGER.debug("Dropping %d bytes of junk data before next packet", idx)
                self._buffer = self._buffer[idx:]
                if len(self._buffer) < 8:
                    break

            packet_len = self._buffer[1]
            if len(self._buffer) < packet_len:
                _LOGGER.debug("Incomplete packet, buffering... (have %d, need %d)", len(self._buffer), packet_len)
                break

            packet = self._buffer[:packet_len]
            self._buffer = self._buffer[packet_len:]
            
            _LOGGER.debug("Parsed complete packet: %s", packet.hex())
            self._process_packet(packet)

    def _process_packet(self, data: bytearray):
        """Process a complete unfragmented packet."""
        packet_type = data[1]

        if packet_type == 0x10:
            if len(data) >= 6 and data[2] == 0x1f:
                tone = data[3]
                self._prompt_tone = (tone == 0x01)
                _LOGGER.debug("Prompt tone update from %s: %s (Raw byte: %02x)", self._mac, self._prompt_tone, tone)
                
                volume = data[5]
                if volume > 0:
                    self._saved_volume = volume
                self._volume = volume
                self._is_on = (volume > 0)
                _LOGGER.debug("Volume update from %s: %d", self._mac, volume)
        elif packet_type == 0x0f:
            source_byte = data[4]
            if source_byte == 0x14:
                self._source = "Bluetooth"
                _LOGGER.debug("Source update from %s: Bluetooth", self._mac)
            elif source_byte == 0x16:
                self._source = "AUX"
                _LOGGER.debug("Source update from %s: AUX", self._mac)

            status_byte = data[5]
            if status_byte == 0x01:
                if self._is_playing:
                    self._is_playing = False
                    _LOGGER.debug("Playback status update from %s: Paused", self._mac)
            elif status_byte == 0x02:
                if not self._is_playing:
                    self._is_playing = True
                    _LOGGER.debug("Playback status update from %s: Playing", self._mac)

            volume = data[6]
            if volume > 0:
                self._saved_volume = volume
            self._volume = volume
            _LOGGER.debug("Volume update from %s: %d", self._mac, volume)

        for callback in self._update_callbacks:
            callback()

    def _on_disconnected(self, client: BleakClient) -> None:
        """Callback called on disconnection."""
        _LOGGER.debug("%s: Disconnected", self._mac)
        self._device = None
        self._is_on = False

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

    @property
    def prompt_tone(self):
        """Return the prompt tone state."""
        return self._prompt_tone

    def set_cached_state(self, is_on: bool | None = None, volume: int | None = None) -> None:
        """Cache state without performing BLE I/O (used on HA startup)."""
        if is_on is not None:
            self._is_on = bool(is_on)
        if volume is not None:
            try:
                self._volume = int(volume)
            except (TypeError, ValueError):
                pass

    async def set_volume(self, intensity: int):
        """Set the volume of the amplifier."""
        volume = int(intensity)

        header = bytes.fromhex("7e0f1d")
        command = (volume).to_bytes(1, 'big')
        params = bytes.fromhex("00000000000000000000")

        await self._send(header + command + params)
        self._volume = intensity

    async def turn_on(self):
        """Turn on the amplifier."""
        self._is_on = True

        if self._saved_volume <= 0:
            self._saved_volume = 7

        volume = int(self._saved_volume)

        header = bytes.fromhex("7e0f1d")
        command = (volume).to_bytes(1, 'big')
        params = bytes.fromhex("00000000000000000000")

        await self._send(header + command + params)

    async def turn_off(self):
        """Turn off the amplifier."""
        self._is_on = False

        header = bytes.fromhex("7e0f1d")
        command = bytes.fromhex("00")
        params = bytes.fromhex("00000000000000000000")

        await self._send(header + command + params)

    async def bluetooth(self):
        """Switch to Bluetooth source."""
        command = bytes.fromhex("7e051400")
        await self._send(command)

    async def aux(self):
        """Switch to AUX source."""
        command = bytes.fromhex("7e051600")
        await self._send(command)

    async def play_pause(self):
        """Toggle Play/Pause command."""
        command = bytes.fromhex("7e050100")
        await self._send(command)

    async def play(self):
        """Send Play command."""
        if not self._is_playing:
            await self.play_pause()

    async def pause(self):
        """Send Pause command."""
        if self._is_playing:
            await self.play_pause()

    async def next_track(self):
        """Send Next Track command."""
        command = bytes.fromhex("7e050800")
        await self._send(command)

    async def previous_track(self):
        """Send Previous Track command."""
        command = bytes.fromhex("7e050700")
        await self._send(command)

    async def request_system_settings(self):
        """Request system settings like prompt tone and password."""
        # The official app sends this AA handshake to unlock notifications
        await self._send(bytes.fromhex("7e07aa03d902"))
        await asyncio.sleep(0.2)
        await self._send(bytes.fromhex("7e051e00"))
        await asyncio.sleep(0.2)
        await self._send(bytes.fromhex("7e051f00"))
        await asyncio.sleep(0.2)
        await self._send(bytes.fromhex("7e052000"))

    async def toggle_prompt_tone(self):
        """Toggle the prompt tone."""
        command = bytes.fromhex("7e051800")
        await self._send(command)

    async def connect(self) -> bool:
        """Connect to the amplifier."""
        async with self._connect_lock:
            _LOGGER.debug("Attempting to connect to %s", self._mac)
            if self._device and self._device.is_connected:
                _LOGGER.debug("Already connected to %s", self._mac)
                return True

            ble_device = bluetooth.async_ble_device_from_address(self.hass, self._mac, connectable=True)
            if not ble_device:
                _LOGGER.error("Device with MAC %s not found by Home Assistant Bluetooth", self._mac)
                return False
               
            self._device = await establish_connection(
                    BleakClient,
                    ble_device,
                    self._mac,
                    disconnected_callback=self._on_disconnected,
                    max_attempts=5,
            )

            if self._device and self._device.is_connected:
                _LOGGER.info("Successfully connected to %s", self._mac)

                try:
                    await self._device.start_notify(NOTIFY_UUID, self._notification_handler)
                    await asyncio.sleep(0.5)
                    self.hass.loop.create_task(self.request_system_settings())
                except BleakError as e:
                    _LOGGER.warning("BleakError during start_notify for %s: %s", self._mac, e)
                except Exception as e:
                    _LOGGER.warning("Unexpected error during start_notify for %s: %s", self._mac, e)

                return True

            _LOGGER.error("Failed to connect to %s", self._mac)
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
