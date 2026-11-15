"""BLE protocol helpers for ECAM machines.

Pure functions only: no Home Assistant or Bleak imports, so the
packet parsing can be unit tested without either installed.

Requests start with 0x0D, answers with 0xD0. Byte 1 is the packet
length minus one, byte 2 the command (answer) id, and the last two
bytes are a CRC-16/CCITT over everything before them.
"""
from __future__ import annotations

import re
from binascii import crc_hqx
from dataclasses import dataclass

REQUEST_BYTE = 0x0D
START_BYTE = 0xD0

ANSWER_MONITOR_V1 = 0x70
ANSWER_MONITOR_V2 = 0x75
ANSWER_STATISTICS = 0xA2
ANSWER_PROFILES = 0xA4
ANSWER_PROFILE_SELECT = 0xA9

PROFILE_NAME_SIZE = 20
PROFILE_HEADER_SIZE = 4
PROFILE_GAP_SIZE = 1

MAC_PATTERN = re.compile(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$')


@dataclass
class MonitorData:
    """Monitor Data structure"""
    switches: int
    alarms: int
    status: int
    sub_status: int
    nozzle_state: int


def with_crc(message: list[int]) -> list[int]:
    """Return a copy of the message with its two CRC bytes filled in."""
    result = list(message)
    crc = crc_hqx(bytes(result[:-2]), 0x1D0F)
    result[-2] = (crc >> 8) & 0xFF
    result[-1] = crc & 0xFF
    return result


def answer_id(packet: bytes) -> int | None:
    """Return the command id of a request or answer packet."""
    return packet[2] if len(packet) > 2 else None


def parse_monitor_data(data: bytes) -> MonitorData | None:
    """Parse Monitor Data packet (v1 0x70 or v2 0x75)"""
    if len(data) < 3:
        return None

    kind = data[2]

    if kind == ANSWER_MONITOR_V2:
        if len(data) < 14:
            return None
        return MonitorData(
            # Switches: bytes 5, 6 (little endian)
            switches=data[5] + (data[6] << 8),
            # Alarms: bytes 7, 8, 12, 13 (little endian in blocks),
            # as in MonitorDataV2.b() of the app
            alarms=(
                data[7] + (data[8] << 8)
                + (data[12] << 16) + (data[13] << 24)
            ),
            status=data[9],
            sub_status=data[10],
            # Nozzle state: byte 4 (MonitorDataV2.a())
            nozzle_state=data[4],
        )

    if kind == ANSWER_MONITOR_V1:
        if len(data) < 11:
            return None
        return MonitorData(
            switches=data[9] + (data[10] << 8),
            alarms=data[4] + (data[5] << 8),
            status=data[8],
            # The app reads the sub state from byte 9, which is also
            # the low switch byte.
            sub_status=data[9],
            # v1 packets carry no nozzle state
            nozzle_state=-1,
        )

    return None


def parse_statistics(data: bytes) -> dict[int, int]:
    """Parse a statistics answer into {parameter id: value}.

    Layout: [D0][len][A2][0F][start id 2B][value 4B]
    then repeated [id 2B][value 4B], then the CRC.
    """
    result: dict[int, int] = {}
    if len(data) < 8:
        return result

    end = len(data) - 2  # CRC
    offset = 6
    if offset + 4 <= end:
        start_id = (data[4] << 8) | data[5]
        result[start_id] = int.from_bytes(data[offset:offset + 4], 'big')
        offset += 4

    while offset + 6 <= end:
        pid = (data[offset] << 8) | data[offset + 1]
        result[pid] = int.from_bytes(data[offset + 2:offset + 6], 'big')
        offset += 6
    return result


def parse_profile_names(data: bytes) -> dict[int, str]:
    """Parse the profile names answer into {profile id: name}.

    Names are UTF-16 BE, 20 bytes each, padded with zeros and
    separated by one byte (the profile icon).
    """
    if len(data) < PROFILE_HEADER_SIZE or data[0] != START_BYTE:
        raise ValueError('Wrong start byte')

    profiles: dict[int, str] = {}
    profile_id = 1
    idx = PROFILE_HEADER_SIZE
    while idx + PROFILE_NAME_SIZE < len(data):
        raw = data[idx:idx + PROFILE_NAME_SIZE]
        profiles.setdefault(
            profile_id,
            raw.decode('utf-16-be').rstrip('\x00').strip(),
        )
        profile_id += 1
        idx += PROFILE_NAME_SIZE + PROFILE_GAP_SIZE
    return profiles


def parse_hex_command(command: str) -> list[int]:
    """Parse a space separated hex string such as '0d 05 75 0f da 25'."""
    try:
        message = [int(part, 16) for part in command.split()]
    except ValueError as err:
        raise ValueError(f'Not a hex byte sequence: {command!r}') from err
    if len(message) < 4 or any(not 0 <= b <= 0xFF for b in message):
        raise ValueError(
            'A command needs at least 4 bytes in the range 00-ff'
        )
    return message


def normalize_mac(value: str) -> str | None:
    """Return the MAC as AA:BB:CC:DD:EE:FF, or None if it is not one.

    Upper case, as Bluetooth discovery reports it, so a manual entry
    and a discovered machine get the same config entry id.
    """
    mac = value.strip().upper().replace('-', ':')
    if len(mac) == 12 and ':' not in mac:
        mac = ':'.join(mac[i:i + 2] for i in range(0, 12, 2))
    return mac if MAC_PATTERN.match(mac) else None
