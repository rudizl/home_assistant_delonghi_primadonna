"""Switch entities for Delonghi Primadonna."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .base_entity import DelonghiDeviceEntity
from .device import DelongiPrimadonna
from .model import get_machine_model


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Register switch entities for a config entry."""

    delongh_device: DelongiPrimadonna = entry.runtime_data
    model = get_machine_model(delongh_device.product_code)

    switches = [
        DelongiPrimadonnaNotificationSwitch(delongh_device, hass),
        DelongiPrimadonnaPowerSaveSwitch(delongh_device, hass),
        DelongiPrimadonnaSoundsSwitch(delongh_device, hass),
    ]

    if model and model.cup_light_settings:
        switches.insert(
            0,
            DelongiPrimadonnaCupLightSwitch(delongh_device, hass),
        )

    if model and model.time_settings:
        switches.insert(
            0,
            DelongiPrimadonnaTimeSyncSwitch(delongh_device, hass),
        )

    async_add_entities(switches)
    return True


class DelongiPrimadonnaCupLightSwitch(
    DelonghiDeviceEntity, SwitchEntity, RestoreEntity
):
    """This switch enable/disable the cup light"""

    _attr_is_on = False
    _attr_icon = 'mdi:lightbulb'
    _attr_translation_key = 'cup_light'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == 'on'
            # Keep the device object in sync: the switch command sends
            # all three bits at once, so a stale default would reset
            # the other settings on the machine.
            self.device.switches.cup_light = self._attr_is_on

    @property
    def entity_category(self) -> EntityCategory:
        """Return the category of the entity."""
        return EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.device.cup_light_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.device.cup_light_off()
        self._attr_is_on = False
        self.async_write_ha_state()


class DelongiPrimadonnaNotificationSwitch(
    DelonghiDeviceEntity, SwitchEntity, RestoreEntity
):
    """This switch enable HA side bar notification
       on device status change used for debug purposes
    """

    _attr_is_on = False
    _attr_icon = 'mdi:magnify-expand'
    _attr_translation_key = 'debug_notification'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.device.notify = last_state.state == 'on'

    @property
    def available(self) -> bool:
        """A local setting, usable even when the machine is offline."""
        return True

    @property
    def is_on(self) -> bool:
        """Checks is the notification ON."""
        return self.device.notify

    @property
    def entity_category(self) -> EntityCategory:
        """Return the category of the entity."""
        return EntityCategory.DIAGNOSTIC

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the notification on."""
        self.device.notify = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the notification off."""
        self.device.notify = False
        self.async_write_ha_state()


class DelongiPrimadonnaPowerSaveSwitch(
    DelonghiDeviceEntity, SwitchEntity, RestoreEntity
):

    _attr_is_on = False
    _attr_icon = 'mdi:lightning-bolt'
    _attr_translation_key = 'energy_save_mode'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == 'on'
            # Keep the device object in sync: the switch command sends
            # all three bits at once, so a stale default would reset
            # the other settings on the machine.
            self.device.switches.energy_save = self._attr_is_on

    @property
    def entity_category(self) -> EntityCategory:
        """Return the category of the entity"""
        return EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the energy save on"""
        await self.device.energy_save_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the energy save off"""
        await self.device.energy_save_off()
        self._attr_is_on = False
        self.async_write_ha_state()


class DelongiPrimadonnaSoundsSwitch(
    DelonghiDeviceEntity, SwitchEntity, RestoreEntity
):

    _attr_is_on = False
    _attr_icon = 'mdi:volume-high'
    _attr_translation_key = 'sounds'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == 'on'
            # Keep the device object in sync: the switch command sends
            # all three bits at once, so a stale default would reset
            # the other settings on the machine.
            self.device.switches.sounds = self._attr_is_on

    @property
    def entity_category(self) -> EntityCategory:
        """Return the category of the entity."""
        return EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the sounds on."""
        await self.device.sound_alarm_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the sounds off."""
        await self.device.sound_alarm_off()
        self._attr_is_on = False
        self.async_write_ha_state()


class DelongiPrimadonnaTimeSyncSwitch(
        DelonghiDeviceEntity, SwitchEntity, RestoreEntity
):
    _attr_is_on = False
    _attr_icon = 'mdi:clock-time-eight-outline'
    _attr_translation_key = 'time_sync'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == 'on'

    @property
    def entity_category(self) -> EntityCategory:
        """Return the category of the entity."""
        return EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Sync time and enable."""
        # Home Assistant time zone, not the host system one.
        await self.device.set_time(dt_util.now())
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable time sync."""
        self._attr_is_on = False
        self.async_write_ha_state()
