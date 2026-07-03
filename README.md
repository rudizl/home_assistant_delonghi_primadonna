# Home Assistant DeLonghi BLE Integration (rudizl fork)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/rudizl/home_assistant_delonghi_primadonna?style=for-the-badge)](https://github.com/rudizl/home_assistant_delonghi_primadonna/blob/masterV0/LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/rudizl/home_assistant_delonghi_primadonna?style=for-the-badge)](https://github.com/rudizl/home_assistant_delonghi_primadonna/releases)

![Company logo](https://brands.home-assistant.io/delonghi_primadonna/logo.png)

## About this fork

This is a fork of [JoelyMoley/home_assistant_delonghi_primadonna](https://github.com/JoelyMoley/home_assistant_delonghi_primadonna) (feature/power-off branch), which itself is a fork of [Arbuzov/home_assistant_delonghi_primadonna](https://github.com/Arbuzov/home_assistant_delonghi_primadonna).

### Fixes and improvements in this fork

- **Improvements (2026.7.3.1)**:
  - Added full Bulgarian (bg) translation, including all machine states, alarms, switches and statistics sensors
- **Improvements (2026.7.3)**:
  - Added the community-decoded `MACHINE_STATUS` map (upstream PRs #235/#238) for the machine state byte: turned_off, heating, washing, ready, brewing, rinsing, preparing, delivering_hot_water, cleaning_milk_spout, descaling. Verified against live Dinamica Plus data (0 = off, 7 = ready on the v2 protocol, 2 = shutdown wash cycle)
  - The previous mapping showed "Ready" while the machine was actually turned off (status bytes 0/1/5 were lumped together); the default status is now `turned_off` instead of a bogus beans-empty alarm
- **Improvements (2026.7.2.1)**:
  - Added a `DataUpdateCoordinator`: one central 60 s polling loop replaces the previous per-entity polling (device tracker + every statistics sensor triggering its own update)
  - BLE notifications now push state changes to all entities instantly instead of waiting for the next Home Assistant poll cycle
  - The machine models JSON is preloaded in an executor job, so the device constructor no longer performs blocking file I/O in the event loop
- **Bug fixes (2026.7.2)**:
  - Fixed cascading `GATT Error 133` warnings: a failed read/write in `get_device_name` left a stale BLE client in place, so every subsequent poll wrote to a dead connection; the client is now reset on any error and a fresh connection is established. Repeated connection failures are logged at debug level (warning only on the connected → disconnected transition)
  - Fixed crash in the BLE notify callback when a profile response (0xA4) failed to parse (`list.items()` AttributeError)
  - Fixed the options flow never appearing: `async_get_options_flow` is now a static method on `ConfigFlow`; removed the deprecated `OptionsFlow.__init__(config_entry)` assignment (removed in HA 2025.12)
  - MAC address is no longer editable in the options flow — changing it would orphan all entities (it is the unique_id base)
  - Fixed state restore after HA restart: Nozzle, Status, Switches and all statistics sensors restored into `_attr_native_value`, which was shadowed by their `native_value` properties, so restored values were never shown; they now serve as a proper fallback until fresh BLE data arrives
  - Profile names are now stored per device instance instead of mutating the global `AVAILABLE_PROFILES` constant (fixes profile clashes with multiple machines)
  - The `make_beverage` service is now registered once and resolves the target machine via `device_id` (previously each config entry overwrote the service to always target the last machine)
  - `send_command` now catches all connection errors, not only `BleakError` — a `TimeoutError` from the connect phase used to escape as an unhandled task exception and skip the retry loop
  - Guarded `ProfileSelect` against sending `select_profile(None)` when an unknown profile name is selected
  - The 30-second delayed init is now a managed background task, cancelled automatically when the entry unloads
  - Select entities no longer restore `unknown`/`unavailable` or out-of-options states
  - `device_tracker.source_type` uses the `SourceType` enum instead of a deprecated string
  - Removed dead `native_value` properties from binary sensors, duplicate `entity_category` properties, the `homeassistant.backports.enum` fallback and unused empty constants
  - Switch entities inherit `SwitchEntity` instead of the generic `ToggleEntity`
  - `manifest.json`: added `integration_type: device`, corrected `iot_class` to `local_push`; `hacs.json` minimum HA raised to 2024.6.0 to match the APIs actually used
  - Normalised line endings to LF and added `.gitattributes`
- **BLE Bluetooth proxy support** — Fixed connection via Bluetooth proxies (Shelly, ESPHome). Changed `connectable=True` to `connectable=False` and replaced `BleakClient.connect()` with `establish_connection()` from `bleak_retry_connector` for reliable proxy-based connections.
- **Prevent statistics timeout in standby** — Statistics requests are now skipped when the machine is off/in standby, eliminating timeout warnings in the logs.
- **Skip statistics update when machine is off** — The HA sensor update cycle no longer triggers statistics polling when the machine is powered off.
- **Power off support** — Inherited from JoelyMoley's fork, adds a power switch entity to turn the machine off remotely.
- **Optimistic power switch state** — The power switch holds its state for 60 s after turn-on and 30 s after turn-off, preventing flickering while the machine boots or shuts down.
- **Bug fixes (2026.5.22)**:
  - Fixed `datetime.now()` → `datetime.datetime.now()` in the time-sync switch (would crash on activation)
  - Fixed `turn_on`/`turn_off` sync methods → `async_turn_on`/`async_turn_off` in `TimeSyncSwitch`
  - Fixed `await` on sync `async_update_entry()` in the options flow (would raise `TypeError`)
  - Fixed `make_beverage` service not being unregistered on integration unload (double-registration on reload)
  - Fixed `COFFEE_GROUNDS_CONTAINER_CLEAN` event reporting as `GroundsContainerFull` instead of `GroundsContainerClean`
  - Fixed `SwitchesSensor` incorrectly declared as `ENUM` device class while returning comma-joined multi-switch values
  - Fixed `entity_category` property signatures carrying `**kwargs` (invalid Python property syntax)
  - Fixed `asyncio.exceptions.TimeoutError` → `asyncio.TimeoutError` for broader Python compatibility
  - Optimised `DEVICE_NOTIFICATION` lookup from 3× to 1× per notification in `_event_trigger`

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
