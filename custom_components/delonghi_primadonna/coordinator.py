"""Data update coordinator for Delonghi Primadonna."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from .const import DOMAIN
from .device import DelongiPrimadonna

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)
# While the machine heats, brews or rinses, ask more often so the
# status and progress follow it
BUSY_UPDATE_INTERVAL = timedelta(seconds=5)

# BLE drops single polls easily; only mark the entities unavailable
# after this many polls in a row could not reach the machine.
FAILURES_BEFORE_UNAVAILABLE = 3


class DelonghiCoordinator(DataUpdateCoordinator[None]):
    """Single polling loop for the device.

    BLE notifications additionally push instant state updates to all
    entities via ``device.on_state_update``.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: DelongiPrimadonna,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f'{DOMAIN}_{device.mac}',
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        self._failures = 0
        device.on_state_update = self._device_updated

    @callback
    def _device_updated(self) -> None:
        """Push a state change from a BLE notification to entities."""
        self.async_update_listeners()
        # A beverage or power on started: switch to the fast interval
        # now instead of after the next slow poll
        if self.device.busy and self.update_interval != BUSY_UPDATE_INTERVAL:
            self.update_interval = BUSY_UPDATE_INTERVAL
            self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self) -> None:
        """Poll the device.

        ``get_device_name`` connects, reads the hostname and sends the
        DEBUG command which makes the machine report its status via
        notify. Statistics are requested only when the machine is on
        (throttled internally).
        """
        await self.device.get_device_name()
        if not self.device.connected:
            self._failures += 1
            if self._failures >= FAILURES_BEFORE_UNAVAILABLE:
                raise UpdateFailed(
                    f'{self.device.name} ({self.device.mac}) has not '
                    f'answered {self._failures} polls in a row'
                )
            return None

        self._failures = 0
        self.update_interval = (
            BUSY_UPDATE_INTERVAL if self.device.busy else UPDATE_INTERVAL
        )
        if self.device.switches.is_on:
            try:
                await self.device.update_statistics()
            except HomeAssistantError as err:
                # Statistics are optional; a failed request must not
                # mark the whole device unavailable.
                _LOGGER.debug('Statistics update failed: %s', err)
        return None
