"""Data update coordinator for Delonghi Primadonna."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .device import DelongiPrimadonna

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


class DelonghiCoordinator(DataUpdateCoordinator[None]):
    """Single polling loop for the device.

    Replaces the previous per-entity polling (device tracker +
    every statistics sensor triggering its own update). BLE
    notifications additionally push instant state updates to all
    entities via ``device.on_state_update``.
    """

    def __init__(
        self, hass: HomeAssistant, device: DelongiPrimadonna
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f'{DOMAIN}_{device.mac}',
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        device.on_state_update = self._device_updated

    @callback
    def _device_updated(self) -> None:
        """Push a state change from a BLE notification to entities."""
        self.async_update_listeners()

    async def _async_update_data(self) -> None:
        """Poll the device.

        ``get_device_name`` connects, reads the hostname and sends the
        DEBUG command which makes the machine report its status via
        notify. Statistics are requested only when the machine is on
        (throttled internally).
        """
        await self.device.get_device_name()
        if self.device.connected and self.device.switches.is_on:
            await self.device.update_statistics()
        return None
