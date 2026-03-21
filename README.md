# Home Assistant DeLonghi BLE Integration (rudizl fork)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/rudizl/home_assistant_delonghi_primadonna?style=for-the-badge)](https://github.com/rudizl/home_assistant_delonghi_primadonna/blob/masterV0/LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/rudizl/home_assistant_delonghi_primadonna?style=for-the-badge)](https://github.com/rudizl/home_assistant_delonghi_primadonna/releases)

![Company logo](https://brands.home-assistant.io/delonghi_primadonna/logo.png)

## About this fork

This is a fork of [JoelyMoley/home_assistant_delonghi_primadonna](https://github.com/JoelyMoley/home_assistant_delonghi_primadonna) (feature/power-off branch), which itself is a fork of [Arbuzov/home_assistant_delonghi_primadonna](https://github.com/Arbuzov/home_assistant_delonghi_primadonna).

### Fixes and improvements in this fork

- **BLE Bluetooth proxy support** — Fixed connection via Bluetooth proxies (Shelly, ESPHome). Changed `connectable=True` to `connectable=False` and replaced `BleakClient.connect()` with `establish_connection()` from `bleak_retry_connector` for reliable proxy-based connections.
- **Prevent statistics timeout in standby** — Statistics requests are now skipped when the machine is off/in standby, eliminating timeout warnings in the logs.
- **Skip statistics update when machine is off** — The HA sensor update cycle no longer triggers statistics polling when the machine is powered off.
- **Power off support** — Inherited from JoelyMoley's fork, adds a power switch entity to turn the machine off remotely.

## Installation via HACS

1. Go to HACS → Integrations → three dots (⋮) → **Custom repositories**
2. Add `rudizl/home_assistant_delonghi_primadonna` as **Integration**
3. Find **DeLonghi BLE** and click **Download**
4. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services → **Add Integration**
2. Search for **DeLonghi**
3. Select **DeLonghi BLE**
4. Enter the MAC address of your coffee machine

> **Note:** This integration uses Bluetooth proxies (Shelly Gen3, ESPHome ESP32) to connect to the machine. Make sure at least one proxy is within range of the machine.

## Known issues

- Power off command may not work on all models — the correct bytes have not been confirmed for all devices.
- The machine supports only one simultaneous BLE connection. Disconnect the official DeLonghi app before using this integration.

## Compatible devices

- De'Longhi Dinamica Plus ECAM 550.55
- De'Longhi Dinamica Plus Class ECAM 370.85.SB
- De'Longhi Dinamica Plus Class ECAM 370.95
- De'Longhi Dinamica Plus Class ECAM 370.95.S
- De'Longhi Maestosa EPAM 960.75.GLM
- De'Longhi ECAM 650.85.MS
- De'Longhi ECAM 550.55.W
- De'Longhi ECAM 650.55.MS EX:1
- De'Longhi ECAM 510.55M
- Feel free to add your model via a pull request!

## Credits

- Original integration: [@Arbuzov](https://github.com/Arbuzov)
- Power-off feature: [@JoelyMoley](https://github.com/JoelyMoley)
- BLE proxy fixes & improvements: [@rudizl](https://github.com/rudizl)
