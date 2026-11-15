"""Delongi primadonna device description"""
import asyncio
import logging
import time
import uuid
from binascii import hexlify
from datetime import datetime
from enum import IntFlag, StrEnum

from bleak import BleakClient
from bleak.exc import BleakDBusError, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (AMERICANO_OFF, AMERICANO_ON, AVAILABLE_PROFILES,
                    BASE_COMMAND, BYTES_AUTOPOWEROFF_COMMAND,
                    BYTES_LOAD_PROFILES, BYTES_POWER, BYTES_POWER_OFF,
                    BYTES_STATISTICS_COMMAND, BYTES_SWITCH_COMMAND,
                    BYTES_TIME_COMMAND, BYTES_WATER_HARDNESS_COMMAND,
                    BYTES_WATER_TEMPERATURE_COMMAND, COFFE_OFF, COFFE_ON,
                    COFFEE_GROUNDS_CONTAINER_CLEAN,
                    COFFEE_GROUNDS_CONTAINER_DETACHED,
                    COFFEE_GROUNDS_CONTAINER_FULL, CONTROLL_CHARACTERISTIC,
                    DEBUG, DEVICE_READY, DEVICE_STATUS, DEVICE_TURNOFF, DOMAIN,
                    DOPPIO_OFF, DOPPIO_ON, ESPRESSO2_OFF, ESPRESSO2_ON,
                    ESPRESSO_OFF, ESPRESSO_ON, HOTWATER_OFF, HOTWATER_ON,
                    LONG_OFF, LONG_ON, MACHINE_STATUS, NAME_CHARACTERISTIC,
                    NOZZLE_STATE, START_COFFEE, STEAM_OFF, STEAM_ON,
                    WATER_SHORTAGE, WATER_TANK_DETACHED)
from .machine_switch import MachineSwitch, parse_switches
from .model import get_machine_model
from .protocol import (ANSWER_MONITOR_V1, ANSWER_MONITOR_V2,
                       ANSWER_PROFILE_SELECT, ANSWER_PROFILES,
                       ANSWER_STATISTICS, START_BYTE, MonitorData, answer_id,
                       parse_hex_command, parse_monitor_data,
                       parse_profile_names, parse_statistics, with_crc)

_LOGGER = logging.getLogger(__name__)

class BeverageEntityFeature(IntFlag):
    """Supported features of the beverage entity"""

    MAKE_BEVERAGE = 1
    SET_TEMPERATURE = 2
    SET_INTENCE = 4


class AvailableBeverage(StrEnum):
    """Coffee machine available beverages"""

    NONE = 'none'
    STEAM = 'steam'
    LONG = 'long'
    COFFEE = 'coffee'
    DOPIO = 'dopio'
    HOTWATER = 'hot_water'
    ESPRESSO = 'espresso'
    AMERICANO = 'americano'
    ESPRESSO2 = 'espresso2'


class NotificationType(StrEnum):
    """Coffee machine notification types"""

    STATUS = 'status'
    PROCESS = 'process'


class BeverageCommand:
    """Coffee machine beverage commands"""

    def __init__(self, on, off):
        self.on = on
        self.off = off


class BeverageNotify:
    """Coffee machine beverage notifications"""

    def __init__(self, kind, description):
        self.kind = str(kind)
        self.description = str(description)


class DeviceSwitches:
    """All binary switches for the device"""

    def __init__(self):
        self.sounds = False
        self.energy_save = False
        self.cup_light = False
        self.filter = False
        self.is_on = False


BEVERAGE_COMMANDS = {
    AvailableBeverage.NONE: BeverageCommand(DEBUG, DEBUG),
    AvailableBeverage.STEAM: BeverageCommand(STEAM_ON, STEAM_OFF),
    AvailableBeverage.LONG: BeverageCommand(LONG_ON, LONG_OFF),
    AvailableBeverage.COFFEE: BeverageCommand(COFFE_ON, COFFE_OFF),
    AvailableBeverage.DOPIO: BeverageCommand(DOPPIO_ON, DOPPIO_OFF),
    AvailableBeverage.HOTWATER: BeverageCommand(HOTWATER_ON, HOTWATER_OFF),
    AvailableBeverage.ESPRESSO: BeverageCommand(ESPRESSO_ON, ESPRESSO_OFF),
    AvailableBeverage.AMERICANO: BeverageCommand(AMERICANO_ON, AMERICANO_OFF),
    AvailableBeverage.ESPRESSO2: BeverageCommand(ESPRESSO2_ON, ESPRESSO2_OFF),
}

DEVICE_NOTIFICATION = {
    str(bytearray(DEVICE_READY)): BeverageNotify(
        NotificationType.STATUS, 'DeviceOK'
    ),
    str(bytearray(DEVICE_TURNOFF)): BeverageNotify(
        NotificationType.STATUS, 'DeviceOFF'
    ),
    str(bytearray(WATER_TANK_DETACHED)): BeverageNotify(
        NotificationType.STATUS, 'NoWaterTank'
    ),
    str(bytearray(WATER_SHORTAGE)): BeverageNotify(
        NotificationType.STATUS, 'NoWater'
    ),
    str(bytearray(COFFEE_GROUNDS_CONTAINER_DETACHED)): BeverageNotify(
        NotificationType.STATUS, 'NoGroundsContainer'
    ),
    str(bytearray(COFFEE_GROUNDS_CONTAINER_FULL)): BeverageNotify(
        NotificationType.STATUS, 'GroundsContainerFull'
    ),
    str(bytearray(COFFEE_GROUNDS_CONTAINER_CLEAN)): BeverageNotify(
        NotificationType.STATUS, 'GroundsContainerClean'
    ),
    str(bytearray(START_COFFEE)): BeverageNotify(
        NotificationType.STATUS, 'START_COFFEE'
    ),
}


class DelonghiCommandError(HomeAssistantError):
    """A command could not be delivered to the machine."""


class DelongiPrimadonna:
    """Delongi Primadonna class"""

    def __init__(self, config: dict, hass: HomeAssistant) -> None:
        """Initialize device"""
        self._device_status = None
        # Set by the coordinator; called on every state change coming
        # from a BLE notification so entities update instantly.
        self.on_state_update = None
        # Backreference set in async_setup_entry; used by base_entity.
        self.coordinator = None
        self._client = None
        self._hass = hass
        self._device = None
        self._connecting = False
        self.mac = config.get(CONF_MAC)
        self.name = config.get(CONF_NAME)
        self.product_code = config.get(CONF_MODEL)
        self.hostname = ''
        self.model = 'Prima Donna'
        self.friendly_name = ''
        self.cooking = AvailableBeverage.NONE
        self.connected = False
        self.notify = False
        self.steam_nozzle = NOZZLE_STATE[-1]
        self.service = 0
        # True once a monitor packet was parsed; until then entities
        # show their restored state instead of the defaults above.
        self.monitor_received = False
        self.status = MACHINE_STATUS[0]
        self.switches = DeviceSwitches()
        self.active_switches: list[MachineSwitch] = []
        self._lock = asyncio.Lock()
        self._rx_buffer = bytearray()
        self._response_event = None
        # Answer id the pending command waits for (= its command id)
        self._expected_answer: int | None = None
        self.statistics: dict[int, int | float] = {}
        self._last_stats_request = 0.0
        self._stats_lock = asyncio.Lock()
        machine = get_machine_model(self.product_code)
        self._n_profiles = (
            machine.nProfiles
            if machine and machine.nProfiles
            else len(AVAILABLE_PROFILES)
        )
        # Per-instance profile mapping. AVAILABLE_PROFILES stays a
        # read-only default so multiple machines don't clash.
        self.profiles_map: dict[int, str] = {
            pid: AVAILABLE_PROFILES.get(pid, f"Profile {pid}")
            for pid in range(1, self._n_profiles + 1)
        }
        self.profiles = list(self.profiles_map.values())
        self._profiles_loaded = False

    async def _reset_client(self):
        """Drop a (possibly stale) BLE client so the next attempt
        establishes a fresh connection. GATT errors (e.g. status 133)
        usually mean the underlying connection is dead even if the
        client object still reports connected. Callers must hold
        ``self._lock``.
        """
        client = self._client
        self._client = None
        self.connected = False
        if client is not None:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5)
            except Exception:  # noqa: BLE001
                pass

    async def disconnect(self):
        """Disconnect from the device."""
        _LOGGER.info("Disconnect from %s", self.mac)
        async with self._lock:
            client = self._client
            if client is not None and client.is_connected:
                try:
                    await asyncio.wait_for(client.disconnect(), timeout=5)
                except (
                    asyncio.TimeoutError,
                    Exception,
                ) as error:  # noqa: BLE001
                    _LOGGER.warning(
                        "Forced disconnect [%s]: %s",
                        type(error).__name__,
                        error
                    )
                finally:
                    self._client = None
                    self.connected = False
            else:
                self._client = None
                self.connected = False

    async def _connect(self, retries=3):
        """Connect to the device."""
        self._connecting = True
        last_error = None
        for attempt in range(retries):
            try:
                if self._client is None or not self._client.is_connected:
                    self._device = bluetooth.async_ble_device_from_address(
                        self._hass, self.mac, connectable=True
                    )
                    if not self._device:
                        raise BleakError(
                            (
                                f"A device with address {self.mac}"
                                " could not be found."
                            )
                        )
                    _LOGGER.info(
                        "Connect to %s (attempt %d)",
                        self.mac,
                        attempt + 1,
                    )
                    self._client = await establish_connection(
                        BleakClient,
                        self._device,
                        self.mac,
                    )
                    # Service discovery is performed during the connection
                    # process. Accessing ``get_services`` directly raises a
                    # ``FutureWarning`` in recent versions of Bleak.
                    # ``self._client.services`` will contain the discovered
                    # services once the connection succeeds.
                    await asyncio.wait_for(
                        self._client.start_notify(
                            uuid.UUID(CONTROLL_CHARACTERISTIC),
                            self._process_raw_data,
                        ),
                        timeout=10,
                    )
                self._connecting = False
                return
            except Exception as error:
                _LOGGER.warning(
                    "BLE connect error: %s (type: %s, attempt %d)",
                    error,
                    type(error).__name__,
                    attempt + 1,
                )
                if self._client is not None:
                    try:
                        await asyncio.wait_for(
                            self._client.disconnect(), timeout=5
                        )
                    except Exception:  # noqa: BLE001
                        pass
                self._client = None
                last_error = error
                await asyncio.sleep(2)
        self._connecting = False
        raise last_error

    def _make_switch_command(self):
        """Make hex command"""
        base_command = list(BASE_COMMAND)
        base_command[3] = '1' if self.switches.energy_save else '0'
        base_command[4] = '1' if self.switches.cup_light else '0'
        base_command[5] = '1' if self.switches.sounds else '0'
        hex_command = BYTES_SWITCH_COMMAND.copy()
        hex_command[9] = int(''.join(base_command), 2)
        return hex_command

    async def _event_trigger(self, value):
        """
        Trigger event
        :param value: event value
        """
        hex_str = hexlify(value, ' ').decode()
        event_data = {'data': hex_str}

        notification_message = '[0x' + hex_str.replace(' ', ', 0x') + ']'

        notification = DEVICE_NOTIFICATION.get(str(bytearray(value)))
        if notification is not None:
            notification_message = notification.description
            event_data.setdefault('type', notification.kind)
            event_data.setdefault('description', notification.description)
            # Update power state when machine turns off
            if notification.description == 'DeviceOFF':
                self.switches.is_on = False
        self._hass.bus.async_fire(f'{DOMAIN}_event', event_data)

        if self.notify:
            answer_hex = f"{value[2]:02x}"
            await self._hass.services.async_call(
                'persistent_notification',
                'create',
                {
                    'message': notification_message,
                    'title': f'{self.name} {answer_hex}',
                    # One notification per answer type: a new packet replaces
                    # the previous one instead of piling up.
                    'notification_id': f'{self.mac}_debug_{answer_hex}',
                },
            )
        _LOGGER.info('Event triggered: %s', event_data)

    async def _process_raw_data(self, sender, value):
        """Assemble incoming BLE packets and pass complete messages."""
        self._rx_buffer.extend(value)

        while True:
            if len(self._rx_buffer) < 2:
                return
            try:
                start_index = self._rx_buffer.index(START_BYTE)
            except ValueError:
                self._rx_buffer.clear()
                return

            if start_index > 0:
                del self._rx_buffer[:start_index]

            if len(self._rx_buffer) < 2:
                return

            msg_len = self._rx_buffer[1] + 1

            if len(self._rx_buffer) < msg_len:
                return

            packet = bytes(self._rx_buffer[:msg_len])
            del self._rx_buffer[:msg_len]
            await self._handle_data(sender, packet)

    async def _handle_data(self, sender, value):
        """Handle notifications from the device."""
        kind = answer_id(value)
        if (
            self._response_event is not None
            and not self._response_event.is_set()
            and kind == self._expected_answer
        ):
            self._response_event.set()

        if kind in (ANSWER_MONITOR_V2, ANSWER_MONITOR_V1):
            monitor_data = parse_monitor_data(value)
            if monitor_data:
                self._handle_monitor_data(monitor_data, kind, value)
        elif kind == ANSWER_PROFILES:
            parsed: dict[int, str] = {}
            try:
                parsed = parse_profile_names(value)
            except (ValueError, UnicodeDecodeError) as err:
                _LOGGER.warning("Failed to parse profile response: %s", err)
            for pid, name in parsed.items():
                if name:
                    self.profiles_map[pid] = name
            _LOGGER.debug(
                "Available profiles: %s",
                self.profiles_map
            )
            self.profiles = list(self.profiles_map.values())
        elif kind == ANSWER_PROFILE_SELECT:
            profile_id = value[4] if len(value) > 4 else None
            status = value[5] if len(value) > 5 else None
            _LOGGER.debug(
                "Profile change response id=%s status=%s raw=%s",
                profile_id,
                status,
                hexlify(value, " "),
            )
        elif kind == ANSWER_STATISTICS:
            self._parse_statistics(value)

        hex_value = hexlify(value, ' ')

        if self._device_status != hex_value:
            _LOGGER.info(
                'Received data: %s from %s',
                hex_value,
                sender
            )
            # Statistics replies are polled data, not machine events.
            if kind != ANSWER_STATISTICS:
                await self._event_trigger(value)
            if self.on_state_update is not None:
                self.on_state_update()

        self._device_status = hex_value

    def _handle_monitor_data(
        self, monitor_data: MonitorData, kind: int, raw_packet: bytes
    ) -> None:
        """Apply parsed monitor data to device state."""
        self.monitor_received = True
        # Power state
        self.switches.is_on = monitor_data.status > 0

        # Nozzle state (only present in v2 / 0x75 packets)
        if monitor_data.nozzle_state != -1:
            self.steam_nozzle = NOZZLE_STATE.get(
                monitor_data.nozzle_state, monitor_data.nozzle_state
            )

        # Alarm bitmask — feeds the Descale binary sensor (bit 2)
        self.service = monitor_data.alarms

        # Display status: show first active alarm, or machine state
        if monitor_data.alarms > 0:
            for i in range(32):
                if (monitor_data.alarms >> i) & 1:
                    self.status = DEVICE_STATUS.get(i, f"Alarm {i}")
                    break
        else:
            self.status = MACHINE_STATUS.get(
                monitor_data.status, f"State {monitor_data.status}"
            )

        # Active switches (v2 only; v1 uses different byte offsets)
        if kind == ANSWER_MONITOR_V2:
            self.active_switches = parse_switches(raw_packet)

    async def power_on(self) -> None:
        """Turn the device on."""
        await self.send_command(BYTES_POWER)

    async def power_off(self) -> None:
        """Turn the device off."""
        await self.send_command(BYTES_POWER_OFF)

    async def _set_switch(self, name: str, value: bool) -> None:
        """Send the switch command with one switch changed.

        Cup light, energy save and sounds travel in one command, so the
        new value is applied only once the command was delivered.
        """
        previous = getattr(self.switches, name)
        setattr(self.switches, name, value)
        try:
            await self.send_command(self._make_switch_command())
        except HomeAssistantError:
            setattr(self.switches, name, previous)
            raise

    async def cup_light_on(self) -> None:
        """Turn the cup light on."""
        await self._set_switch('cup_light', True)

    async def cup_light_off(self) -> None:
        """Turn the cup light off."""
        await self._set_switch('cup_light', False)

    async def energy_save_on(self):
        """Enable energy save mode"""
        await self._set_switch('energy_save', True)

    async def energy_save_off(self):
        """Disable energy save mode"""
        await self._set_switch('energy_save', False)

    async def sound_alarm_on(self):
        """Enable sound alarm"""
        await self._set_switch('sounds', True)

    async def sound_alarm_off(self):
        """Disable sound alarm"""
        await self._set_switch('sounds', False)

    async def beverage_start(self, beverage: AvailableBeverage) -> None:
        """Start beverage"""
        command = BEVERAGE_COMMANDS.get(beverage)
        if command is None:
            raise HomeAssistantError(f'Unknown beverage: {beverage}')
        await self.send_command(command.on)

    async def beverage_cancel(self) -> None:
        """Cancel beverage"""
        if self.cooking != AvailableBeverage.NONE:
            await self.send_command(BEVERAGE_COMMANDS.get(self.cooking).off)

    async def debug(self):
        """Send command which causes status reply"""
        await self.send_command(DEBUG)

    async def get_device_name(self):
        """
        Get device name
        :return: device name
        """
        async with self._lock:
            try:
                await self._connect()
                self.hostname = bytes(
                    await self._client.read_gatt_char(
                        uuid.UUID(NAME_CHARACTERISTIC)
                    )
                ).decode('utf-8')
                await self._client.write_gatt_char(
                    uuid.UUID(CONTROLL_CHARACTERISTIC), bytearray(DEBUG)
                )
                self.connected = True
            except (
                BleakDBusError,
                BleakError,
                asyncio.TimeoutError,
            ) as error:
                # Warn only on the connected -> disconnected transition,
                # log repeats at debug level to avoid flooding the log.
                log = _LOGGER.warning if self.connected else _LOGGER.debug
                log(
                    '%s: %s at device connection',
                    type(error).__name__,
                    error,
                )
                await self._reset_client()
            except asyncio.CancelledError:
                await self._reset_client()
                raise

        if self.connected and not self._profiles_loaded:
            command = list(BYTES_LOAD_PROFILES)
            command[5] = self._n_profiles
            try:
                await self.send_command(command)
            except HomeAssistantError as err:
                _LOGGER.debug('Loading profiles failed, will retry: %s', err)
            else:
                self._profiles_loaded = True

    async def set_time(self, dt: datetime) -> None:
        """Set device clock from provided datetime."""
        packet = BYTES_TIME_COMMAND.copy()
        packet[4] = dt.hour & 0xFF
        packet[5] = dt.minute & 0xFF
        await self.send_command(packet)

    async def select_profile(self, profile_id) -> None:
        """select a profile."""
        _LOGGER.debug("Send select profile command id=%s", profile_id)
        message = [0x0D, 0x06, 0xA9, 0xF0, profile_id, 0x00, 0x00]
        await self.send_command(message)

    async def set_auto_power_off(self, power_off_interval) -> None:
        """Set auto power off time."""
        message = list(BYTES_AUTOPOWEROFF_COMMAND)
        message[9] = power_off_interval
        await self.send_command(message)

    async def set_water_hardness(self, hardness_level) -> None:
        """Set water hardness"""
        message = list(BYTES_WATER_HARDNESS_COMMAND)
        message[9] = hardness_level
        await self.send_command(message)

    async def set_water_temperature(self, temperature_level) -> None:
        """Set water temperature"""
        message = list(BYTES_WATER_TEMPERATURE_COMMAND)
        message[9] = temperature_level
        await self.send_command(message)

    async def common_command(self, command: str) -> None:
        """Send custom BLE command"""
        try:
            message = parse_hex_command(command)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await self.send_command(message)

    async def send_command(self, message, retries=3):
        """Send a command and wait for the answer with the same id.

        Raises DelonghiCommandError when the command could not be
        written. A missing answer only logs a warning: some commands
        are not answered by every model.
        """
        message_to_send = with_crc(message)
        hex_message = hexlify(bytearray(message_to_send), ' ')
        async with self._lock:
            last_error: Exception | None = None
            for attempt in range(retries):
                try:
                    await self._connect()
                    _LOGGER.info('Send command: %s', hex_message)
                    self._expected_answer = answer_id(message_to_send)
                    self._response_event = asyncio.Event()
                    await self._client.write_gatt_char(
                        CONTROLL_CHARACTERISTIC, bytearray(message_to_send)
                    )
                    try:
                        await asyncio.wait_for(
                            self._response_event.wait(),
                            timeout=10,
                        )
                    except asyncio.TimeoutError:
                        _LOGGER.warning(
                            'No answer to command: %s', hex_message
                        )
                    return
                except asyncio.CancelledError:
                    await self._reset_client()
                    raise
                except Exception as error:  # noqa: BLE001
                    # _connect re-raises its last error which is not
                    # always a BleakError (e.g. asyncio.TimeoutError).
                    # Reset the client: GATT errors like status 133
                    # mean the connection is dead even if the client
                    # object still reports connected.
                    last_error = error
                    await self._reset_client()
                    _LOGGER.warning(
                        'Send command failed: %s (%s, attempt %d)',
                        error,
                        type(error).__name__,
                        attempt + 1
                    )
                    await asyncio.sleep(2)
                finally:
                    self._response_event = None
                    self._expected_answer = None
        raise DelonghiCommandError(
            f'Could not send command to {self.name} after {retries} '
            f'attempts: {last_error}'
        )

    def _parse_statistics(self, data: bytes) -> None:
        """Store the values of a statistics answer."""
        _LOGGER.debug(
            'Statistics raw: %s', hexlify(data, ' ').decode('utf-8')
        )
        values = parse_statistics(data)
        _LOGGER.debug('Statistics parsed: %s', values)
        self.statistics.update(values)

        # Total coffee = black coffee (3000) + additional totals (3077)
        if 3000 in self.statistics:
            self.statistics[-3077] = (
                self.statistics[3000] + self.statistics.get(3077, 0)
            )

        # Water counter to litres (same scale as before: value / 2000)
        water = self.statistics.get(106, 0)
        if water > 0:
            self.statistics[10106] = round(water / 2000.0, 2)

    async def update_statistics(self) -> None:
        """Update statistics with throttling.

        Requests statistics from the ECAM machine via BLE.
        Based on APK's parameter address mappings:
        - 100-109: Maintenance counters (water, descaling, filters)
        - 110-119: Extended maintenance counters (milk cleaning)
        - 3000-3009: Coffee beverage totals
        - 3077-3080: Additional coffee totals (combined with 3000 for total)
        """

        # Use a lock to prevent concurrent statistics updates from multiple
        # sensors
        if self._stats_lock.locked():
            return

        async with self._stats_lock:
            current_time = time.monotonic()
            # Update at most once every 60 seconds
            if current_time - self._last_stats_request < 60:
                return
            # Don't request statistics when machine is off
            if not self.switches.is_on:
                return

            self._last_stats_request = current_time
            # Request parameter range for maintenance counters
            # Covers: 100-109 (includes 106=water, 105=descale, 108=filter,
            # etc.)
            await self.get_statistics(100, 10)
            await asyncio.sleep(0.3)

            # Request extended maintenance counters
            # Covers: 110-119 (includes 115=milk cleaning)
            await self.get_statistics(110, 10)
            await asyncio.sleep(0.3)

            # Request coffee statistics range
            # Covers: 3000-3009 (includes 3000=total black coffee, 3001=with
            # milk, etc.)
            await self.get_statistics(3000, 10)
            await asyncio.sleep(0.3)

            # Request additional coffee totals range
            # Covers: 3077-3080 (3077 is combined with 3000 for total coffee)
            await self.get_statistics(3077, 4)
            await asyncio.sleep(0.3)

            # Optional: Request tea/other beverages if needed
            # await self.get_statistics(3025, 1)  # Tea counter

    async def get_statistics(self, start_index: int, count: int) -> None:
        """Get statistics from the machine"""
        message = list(BYTES_STATISTICS_COMMAND)
        message[4] = (start_index >> 8) & 0xFF
        message[5] = start_index & 0xFF
        message[6] = count
        await self.send_command(message)
