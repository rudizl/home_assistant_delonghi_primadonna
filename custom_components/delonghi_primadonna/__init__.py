"""Delonghi integration"""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import BEVERAGE_SERVICE_NAME, DOMAIN
from .device import AvailableBeverage, BeverageEntityFeature, DelongiPrimadonna

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

__all__ = ['async_setup_entry', 'async_unload_entry', 'BeverageEntityFeature']

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry"""
    hass.data.setdefault(DOMAIN, {})
    delonghi_device = DelongiPrimadonna(entry.data, hass)
    hass.data[DOMAIN][entry.unique_id] = delonghi_device
    _LOGGER.debug('Device id %s', entry.unique_id)
    _LOGGER.debug("Device data %s", entry.data)

    async def delayed_init():
        await asyncio.sleep(30)
        await delonghi_device.get_device_name()

    # Background task is cancelled automatically when the entry is
    # unloaded, so it can no longer touch a removed device.
    entry.async_create_background_task(
        hass, delayed_init(), f'{DOMAIN}_delayed_init'
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, BEVERAGE_SERVICE_NAME):

        async def make_beverage(call: ServiceCall) -> None:
            _LOGGER.debug('Make beverage %s', call.data)
            devices: dict[str, DelongiPrimadonna] = hass.data.get(DOMAIN, {})
            device = None
            device_id = call.data.get('device_id')
            if device_id:
                device_entry = dr.async_get(hass).async_get(device_id)
                if device_entry:
                    for domain, identifier in device_entry.identifiers:
                        if domain == DOMAIN and identifier in devices:
                            device = devices[identifier]
                            break
            if device is None and len(devices) == 1:
                device = next(iter(devices.values()))
            if device is None:
                _LOGGER.error(
                    'make_beverage: unable to determine target device; '
                    'pass device_id when multiple machines are configured'
                )
                return
            await device.beverage_start(call.data['beverage'])

        hass.services.async_register(
            DOMAIN,
            BEVERAGE_SERVICE_NAME,
            make_beverage,
            schema=vol.Schema(
                {
                    vol.Required('beverage'): vol.In([*AvailableBeverage]),
                    vol.Optional('entity_id'): vol.Coerce(str),
                    vol.Optional('device_id'): vol.Coerce(str),
                }
            ),
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        await hass.data[DOMAIN][entry.unique_id].disconnect()
        hass.data[DOMAIN].pop(entry.unique_id)
        # Unregister service only when last instance is removed
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, BEVERAGE_SERVICE_NAME)
    _LOGGER.debug('Unload %s', entry.unique_id)
    return unload_ok
