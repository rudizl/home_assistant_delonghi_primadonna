"""Delonghi integration"""
from __future__ import annotations

import asyncio
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID,
                                 Platform)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .beverages import BEVERAGE_IDS
from .const import BEVERAGE_SERVICE_NAME, DOMAIN
from .coordinator import DelonghiCoordinator
from .device import DelongiPrimadonna
from .model import get_machine_models

PLATFORMS: list[str] = [
    Platform.IMAGE,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.DEVICE_TRACKER,
]

__all__ = [
    'async_setup',
    'async_setup_entry',
    'async_unload_entry',
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_BEVERAGE = 'beverage'

# Entities of earlier versions that no longer exist: the power switch
# (the machine ignores power off over Bluetooth) and the beverage
# select (replaced by one button per beverage).
REMOVED_ENTITIES = ('DelongiPrimadonnaPowerSwitch', 'BeverageSelect')

MAKE_BEVERAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BEVERAGE): vol.In(sorted(BEVERAGE_IDS)),
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_AREA_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)

_LOGGER = logging.getLogger(__name__)

type DelonghiConfigEntry = ConfigEntry[DelongiPrimadonna]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration services."""

    async def make_beverage(call: ServiceCall) -> None:
        _LOGGER.debug('Make beverage %s', call.data)
        for device in _target_devices(hass, call):
            await device.beverage_start(call.data[ATTR_BEVERAGE])

    hass.services.async_register(
        DOMAIN,
        BEVERAGE_SERVICE_NAME,
        make_beverage,
        schema=MAKE_BEVERAGE_SCHEMA,
    )
    return True


def _target_devices(
    hass: HomeAssistant, call: ServiceCall
) -> list[DelongiPrimadonna]:
    """Return the machines a service call targets.

    Without any target the call goes to the only configured machine.
    """
    loaded: dict[str, DelongiPrimadonna] = {
        entry.entry_id: entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    }
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    device_ids: set[str] = set(call.data.get(ATTR_DEVICE_ID, []))
    entity_ids: set[str] = set(call.data.get(ATTR_ENTITY_ID, []))
    for area_id in call.data.get(ATTR_AREA_ID, []):
        device_ids.update(
            device.id
            for device in dr.async_entries_for_area(device_reg, area_id)
        )
        entity_ids.update(
            entity.entity_id
            for entity in er.async_entries_for_area(entity_reg, area_id)
        )

    entry_ids: set[str] = set()
    for device_id in device_ids:
        if (device := device_reg.async_get(device_id)) is not None:
            entry_ids.update(device.config_entries & loaded.keys())
    for entity_id in entity_ids:
        entity = entity_reg.async_get(entity_id)
        if entity is not None and entity.config_entry_id in loaded:
            entry_ids.add(entity.config_entry_id)

    has_target = any(
        call.data.get(key)
        for key in (ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID)
    )
    if not has_target and len(loaded) == 1:
        entry_ids = set(loaded)

    if not entry_ids:
        raise ServiceValidationError(
            'No DeLonghi machine matches the target; pick a device or '
            'entity when several machines are configured'
        )
    return [loaded[entry_id] for entry_id in entry_ids]


def _remove_old_entities(
    hass: HomeAssistant, entry: DelonghiConfigEntry, mac: str
) -> None:
    """Delete registry entries of entities this version no longer has."""
    registry = er.async_get(hass)
    for name in REMOVED_ENTITIES:
        for entity in er.async_entries_for_config_entry(
            registry, entry.entry_id
        ):
            if entity.unique_id == f'{mac}_{name}':
                _LOGGER.info('Removing old entity %s', entity.entity_id)
                registry.async_remove(entity.entity_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: DelonghiConfigEntry
) -> bool:
    """Set up from a config entry"""
    # Preload the machine models JSON in the executor so the device
    # constructor never does blocking file I/O in the event loop.
    await hass.async_add_executor_job(get_machine_models)
    delonghi_device = DelongiPrimadonna(entry.data, hass)
    coordinator = DelonghiCoordinator(hass, entry, delonghi_device)
    delonghi_device.coordinator = coordinator
    entry.runtime_data = delonghi_device
    _remove_old_entities(hass, entry, delonghi_device.mac)
    _LOGGER.debug('Device id %s', entry.unique_id)
    _LOGGER.debug("Device data %s", entry.data)

    async def delayed_init():
        # Give the bluetooth proxies time to discover the device
        # after a Home Assistant start before the first connection.
        await asyncio.sleep(30)
        await coordinator.async_refresh()

    # Background task is cancelled automatically when the entry is
    # unloaded, so it can no longer touch a removed device.
    entry.async_create_background_task(
        hass, delayed_init(), f'{DOMAIN}_delayed_init'
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DelonghiConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        await entry.runtime_data.disconnect()
    _LOGGER.debug('Unload %s', entry.unique_id)
    return unload_ok
