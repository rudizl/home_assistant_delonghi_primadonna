"""Tests for the BLE packet helpers."""
import pytest

from delonghi_primadonna import const
from delonghi_primadonna.machine_switch import MachineSwitch, parse_switches
from delonghi_primadonna.protocol import (MonitorData, answer_id,
                                          normalize_mac, parse_hex_command,
                                          parse_monitor_data,
                                          parse_profile_names,
                                          parse_statistics, with_crc)

# Commands and answers recorded from real machines, CRC included
RECORDED = {
    name: getattr(const, name)
    for name in (
        'BYTES_POWER', 'BYTES_POWER_OFF', 'DEBUG',
        'COFFE_ON', 'COFFE_OFF', 'DOPPIO_ON', 'DOPPIO_OFF',
        'STEAM_ON', 'STEAM_OFF', 'HOTWATER_ON', 'HOTWATER_OFF',
        'ESPRESSO_ON', 'ESPRESSO_OFF', 'ESPRESSO2_ON', 'ESPRESSO2_OFF',
        'AMERICANO_ON', 'AMERICANO_OFF', 'LONG_ON', 'LONG_OFF',
        'WATER_TANK_DETACHED', 'WATER_SHORTAGE', 'WATER_SHORTAGE2',
        'COFFEE_GROUNDS_CONTAINER_FULL', 'COFFEE_GROUNDS_CONTAINER_CLEAN',
        'COFFEE_GROUNDS_CONTAINER_DETACHED', 'DEVICE_READY',
        'DEVICE_TURNOFF', 'START_COFFEE',
    )
}


@pytest.mark.parametrize('name', sorted(RECORDED))
def test_recorded_packets_have_valid_length_and_crc(name):
    packet = RECORDED[name]
    assert packet[1] == len(packet) - 1
    assert with_crc(packet) == packet


def test_with_crc_does_not_modify_input():
    message = [0x0d, 0x05, 0x75, 0x0f, 0x00, 0x00]
    assert with_crc(message) == const.DEBUG
    assert message[-2:] == [0x00, 0x00]


def test_answer_id():
    assert answer_id(bytes(const.DEBUG)) == 0x75
    assert answer_id(b'\xd0\x01') is None


def test_monitor_v2_ready():
    data = parse_monitor_data(bytes(const.DEVICE_READY))
    assert data == MonitorData(
        switches=0x05, alarms=0, status=7, sub_status=0, nozzle_state=1
    )


def test_monitor_v2_alarm_bytes():
    shortage = parse_monitor_data(bytes(const.WATER_SHORTAGE))
    assert shortage.alarms == 1 << 0  # empty_water_tank
    full = parse_monitor_data(bytes(const.COFFEE_GROUNDS_CONTAINER_FULL))
    assert full.alarms == 1 << 1  # coffee_waste_container_full


def test_monitor_v2_turned_off():
    data = parse_monitor_data(bytes(const.DEVICE_TURNOFF))
    assert data.status == 0
    assert data.sub_status == 3


def test_monitor_rejects_short_and_unknown_packets():
    assert parse_monitor_data(b'\xd0\x02') is None
    assert parse_monitor_data(bytes(const.DEVICE_READY[:10])) is None
    assert parse_monitor_data(b'\xd0\x05\xa2\x0f\x00\x00') is None


def test_monitor_v1():
    packet = bytes([0xd0, 0x0c, 0x70, 0x0f, 0x04, 0x00,
                    0x00, 0x00, 0x05, 0x21, 0x00, 0x00, 0x00])
    data = parse_monitor_data(packet)
    assert data.alarms == 0x04
    assert data.status == 5
    assert data.switches == 0x21
    assert data.nozzle_state == -1


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('DEVICE_READY', [MachineSwitch.MOTOR_DOWN]),
        ('WATER_SHORTAGE',
         [MachineSwitch.MOTOR_DOWN, MachineSwitch.WATER_LEVEL_LOW]),
        ('WATER_TANK_DETACHED',
         [MachineSwitch.MOTOR_DOWN, MachineSwitch.WATER_TANK_ABSENT]),
        ('COFFEE_GROUNDS_CONTAINER_DETACHED',
         [MachineSwitch.MOTOR_DOWN, MachineSwitch.COFFEE_WASTE_CONTAINER]),
        # Alarm bits in byte 7 must not show up as switches
        ('COFFEE_GROUNDS_CONTAINER_FULL', [MachineSwitch.MOTOR_DOWN]),
    ],
)
def test_parse_switches(name, expected):
    assert parse_switches(bytes(RECORDED[name])) == expected


def test_parse_statistics():
    packet = bytes(
        [0xd0, 0x15, 0xa2, 0x0f, 0x00, 0x64]
        + list((1234).to_bytes(4, 'big'))
        + [0x00, 0x65] + list((7).to_bytes(4, 'big'))
        + [0x00, 0x6a] + list((50000).to_bytes(4, 'big'))
        + [0x00, 0x00]
    )
    assert parse_statistics(packet) == {100: 1234, 101: 7, 106: 50000}


def test_parse_statistics_ignores_truncated_entries():
    packet = bytes([0xd0, 0x0b, 0xa2, 0x0f, 0x0b, 0xb8,
                    0x00, 0x00, 0x00, 0x2a, 0x00, 0x01, 0x00, 0x00])
    assert parse_statistics(packet) == {3000: 42}
    assert parse_statistics(b'\xd0\x03\xa2\x0f') == {}


def _profile_packet(names):
    body = []
    for name in names:
        raw = name.encode('utf-16-be').ljust(20, b'\x00')
        body += list(raw) + [0x01]
    return bytes([0xd0, 0x00, 0xa4, 0xf0] + body + [0x00, 0x00])


def test_parse_profile_names():
    packet = _profile_packet(['Rudi', 'Гост', ''])
    assert parse_profile_names(packet) == {1: 'Rudi', 2: 'Гост', 3: ''}


def test_parse_profile_names_wrong_start_byte():
    with pytest.raises(ValueError):
        parse_profile_names(b'\x0d\x05\xa4\xf0\x00\x00')


def test_parse_hex_command():
    assert parse_hex_command('0d 05 75 0f da 25') == const.DEBUG
    assert parse_hex_command('  0d 05  75 0f 00 00 ') == [
        0x0d, 0x05, 0x75, 0x0f, 0, 0
    ]


@pytest.mark.parametrize('value', ['', 'zz 01 02 03', '0d 05', '100 1 2 3'])
def test_parse_hex_command_rejects_bad_input(value):
    with pytest.raises(ValueError):
        parse_hex_command(value)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('00:A0:50:34:77:64', '00:A0:50:34:77:64'),
        ('00:a0:50:34:77:64', '00:A0:50:34:77:64'),
        (' 00-A0-50-34-77-64 ', '00:A0:50:34:77:64'),
        ('00a050347764', '00:A0:50:34:77:64'),
        ('00:a0:50', None),
        ('zz:a0:50:34:77:64', None),
        ('', None),
    ],
)
def test_normalize_mac(value, expected):
    assert normalize_mac(value) == expected


def test_status_options_cover_every_status():
    options = set(const.STATUS_OPTIONS)
    assert set(const.MACHINE_STATUS.values()) <= options
    assert set(const.DEVICE_STATUS.values()) <= options
    assert {const.UNKNOWN_STATE, const.UNKNOWN_ALARM} <= options
