"""Select entities for Delonghi Primadonna."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .base_entity import DelonghiDeviceEntity
from .const import POWER_OFF_OPTIONS
from .device import AvailableBeverage, BeverageEntityFeature, DelongiPrimadonna

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up select entities for a config entry."""

    delongh_device: DelongiPrimadonna = entry.runtime_data
    async_add_entities(
        [
            BeverageSelect(delongh_device, hass),
            EnergySaveModeSelect(delongh_device, hass),
            ProfileSelect(delongh_device, hass),
            WaterHardnessSelect(delongh_device, hass),
            WaterTemperatureSelect(delongh_device, hass)
        ]
    )
    return True


class ProfileSelect(DelonghiDeviceEntity, SelectEntity, RestoreEntity):
    """Implementation for profile selection."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = 'profile'
    _attr_icon = 'mdi:account'

    def __init__(self, delongh_device: DelongiPrimadonna, hass: HomeAssistant):
        super().__init__(delongh_device, hass)
        self._attr_current_option = delongh_device.profiles[0]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Do NOT validate against self.options here: at startup the
        # options are the default placeholders and the real profile
        # names arrive from the machine ~30s later, so a saved name
        # like 'Rudi' would be wrongly rejected (and the select would
        # show 'unknown' once the real names load).
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in ('', 'unknown', 'unavailable')
        ):
            self._attr_current_option = last_state.state

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.device.profiles

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        profile_id = next(
            (
                pid
                for pid, name in self.device.profiles_map.items()
                if name == option
            ),
            None,
        )
        _LOGGER.debug("Select profile '%s' id=%s", option, profile_id)
        if profile_id is None:
            raise HomeAssistantError(f"Unknown profile '{option}'")
        await self.device.select_profile(profile_id)
        self._attr_current_option = option
        self.async_write_ha_state()


class BeverageSelect(DelonghiDeviceEntity, SelectEntity, RestoreEntity):
    """Beverage start implementation by the select"""

    _attr_options = [*AvailableBeverage]
    _attr_current_option = [*AvailableBeverage][0]
    _attr_translation_key = 'make_beverage'
    _attr_icon = 'mdi:coffee'
    _attr_supported_features: BeverageEntityFeature \
        = BeverageEntityFeature.MAKE_BEVERAGE

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state in self._attr_options
        ):
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Select beverage action"""
        await self.device.beverage_start(option)


class EnergySaveModeSelect(DelonghiDeviceEntity, SelectEntity, RestoreEntity):
    """Energy save mode management"""

    _attr_options = list(POWER_OFF_OPTIONS.keys())
    _attr_current_option = list(POWER_OFF_OPTIONS.keys())[3]
    _attr_translation_key = 'energy_save_mode'
    _attr_icon = 'mdi:power-plug-off'
    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state in self._attr_options
        ):
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Select energy save mode action"""
        power_off_interval = POWER_OFF_OPTIONS.get(option)
        await self.device.set_auto_power_off(power_off_interval)
        self._attr_current_option = option
        self.async_write_ha_state()


def _restored_option(state: str, options: list[str]) -> str | None:
    """Map a restored state to an option key.

    Before 2026.11.3 the options were English labels ('Very Hard');
    they are translation keys now ('very_hard').
    """
    key = state.strip().lower().replace(' ', '_')
    return key if key in options else None


class WaterHardnessSelect(DelonghiDeviceEntity, SelectEntity, RestoreEntity):
    """Water hardness management"""

    # Index in this list = value sent to the machine
    _attr_options = ['soft', 'medium', 'hard', 'very_hard']
    _attr_current_option = 'soft'
    _attr_translation_key = 'water_hardness'
    _attr_icon = 'mdi:water'
    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            option = _restored_option(last_state.state, self._attr_options)
            if option is not None:
                self._attr_current_option = option

    async def async_select_option(self, option: str) -> None:
        """Select water hardness action"""
        water_hardness = self._attr_options.index(option)
        await self.device.set_water_hardness(water_hardness)
        self._attr_current_option = option
        self.async_write_ha_state()


class WaterTemperatureSelect(
    DelonghiDeviceEntity, SelectEntity, RestoreEntity
):
    """Water temperature management"""

    # Index in this list = value sent to the machine
    _attr_options = ['low', 'medium', 'high', 'highest']
    _attr_current_option = 'low'
    _attr_translation_key = 'water_temperature'
    _attr_icon = 'mdi:thermometer'
    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            option = _restored_option(last_state.state, self._attr_options)
            if option is not None:
                self._attr_current_option = option

    async def async_select_option(self, option: str) -> None:
        """Select water temperature action"""
        water_temperature = self._attr_options.index(option)
        await self.device.set_water_temperature(water_temperature)
        self._attr_current_option = option
        self.async_write_ha_state()
