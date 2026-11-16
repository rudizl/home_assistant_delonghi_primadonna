"""Button entity definitions for Delonghi Primadonna."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .base_entity import DelonghiDeviceEntity
from .device import AvailableBeverage, DelongiPrimadonna
from .model import get_machine_model

BEVERAGE_ICONS = {
    AvailableBeverage.STEAM: 'mdi:kettle-steam',
    AvailableBeverage.HOTWATER: 'mdi:kettle',
    AvailableBeverage.LONG: 'mdi:coffee-outline',
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up button entities for a config entry."""

    delongh_device: DelongiPrimadonna = entry.runtime_data
    buttons: list[ButtonEntity] = [
        DelongiPrimadonnaPowerButton(delongh_device, hass),
    ]
    buttons.extend(
        DelongiPrimadonnaBeverageButton(delongh_device, hass, beverage)
        for beverage in AvailableBeverage
        if beverage is not AvailableBeverage.NONE
    )
    model = get_machine_model(delongh_device.product_code)
    if model and model.time_settings:
        buttons.append(DelongiPrimadonnaSyncTimeButton(delongh_device, hass))
    async_add_entities(buttons)
    return True


class DelongiPrimadonnaPowerButton(DelonghiDeviceEntity, ButtonEntity):
    """This button turns on the device"""

    _attr_translation_key = 'power_on'

    async def async_press(self):
        await self.device.power_on()


class DelongiPrimadonnaBeverageButton(DelonghiDeviceEntity, ButtonEntity):
    """Start one beverage."""

    def __init__(
        self,
        device: DelongiPrimadonna,
        hass: HomeAssistant,
        beverage: AvailableBeverage,
    ) -> None:
        super().__init__(device, hass)
        self._beverage = beverage
        self._attr_unique_id = f'{device.mac}_beverage_{beverage.value}'
        self._attr_translation_key = f'beverage_{beverage.value}'
        self._attr_icon = BEVERAGE_ICONS.get(beverage, 'mdi:coffee')

    async def async_press(self) -> None:
        await self.device.beverage_start(self._beverage)


class DelongiPrimadonnaSyncTimeButton(DelonghiDeviceEntity, ButtonEntity):
    """Set the machine clock to the Home Assistant time."""

    _attr_translation_key = 'sync_time'
    _attr_icon = 'mdi:clock-check-outline'
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        # Home Assistant time zone, not the host system one.
        await self.device.set_time(dt_util.now())
