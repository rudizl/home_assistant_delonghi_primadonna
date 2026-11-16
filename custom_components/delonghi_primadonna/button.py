"""Button entity definitions for Delonghi Primadonna."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .base_entity import DelonghiDeviceEntity
from .beverages import DEFAULT_BEVERAGES, beverages_for_recipe_ids
from .device import DelongiPrimadonna
from .model import get_machine_model

BEVERAGE_ICONS = {
    'hot_water': 'mdi:kettle',
    'steam': 'mdi:kettle-steam',
    'hot_milk': 'mdi:cup',
    'cold_milk': 'mdi:cup-outline',
    'tea': 'mdi:tea',
    'ciocco': 'mdi:cup',
    'long': 'mdi:coffee-outline',
    'coffee_pot': 'mdi:coffee-maker',
    'travel_mug': 'mdi:cup-water',
    'brew_over_ice': 'mdi:snowflake',
}


def _beverages(device: DelongiPrimadonna) -> list[str]:
    """Beverages of the configured model, or the default set."""
    model = get_machine_model(device.product_code)
    if model and model.recipes:
        keys = beverages_for_recipe_ids(r.id for r in model.recipes)
        if keys:
            return keys
    return list(DEFAULT_BEVERAGES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up button entities for a config entry."""

    delongh_device: DelongiPrimadonna = entry.runtime_data
    beverages = _beverages(delongh_device)
    buttons: list[ButtonEntity] = [
        DelongiPrimadonnaPowerButton(delongh_device, hass),
        DelongiPrimadonnaStopButton(delongh_device, hass),
    ]
    buttons.extend(
        DelongiPrimadonnaBeverageButton(delongh_device, hass, beverage)
        for beverage in beverages
    )
    model = get_machine_model(delongh_device.product_code)
    if model and model.time_settings:
        buttons.append(DelongiPrimadonnaSyncTimeButton(delongh_device, hass))

    # Drop beverage buttons this model cannot make (2026.11.3 created
    # the same eight for every model).
    keep = {f'{delongh_device.mac}_beverage_{b}' for b in beverages}
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity.domain == 'button'
            and entity.unique_id.startswith(f'{delongh_device.mac}_beverage_')
            and entity.unique_id not in keep
        ):
            registry.async_remove(entity.entity_id)

    async_add_entities(buttons)
    return True


class DelongiPrimadonnaPowerButton(DelonghiDeviceEntity, ButtonEntity):
    """This button turns on the device"""

    _attr_translation_key = 'power_on'

    async def async_press(self):
        await self.device.power_on()


class DelongiPrimadonnaStopButton(DelonghiDeviceEntity, ButtonEntity):
    """Stop the beverage started from Home Assistant."""

    _attr_translation_key = 'stop'
    _attr_icon = 'mdi:stop-circle-outline'

    async def async_press(self) -> None:
        await self.device.beverage_stop()


class DelongiPrimadonnaBeverageButton(DelonghiDeviceEntity, ButtonEntity):
    """Start one beverage with the recipe saved on the machine."""

    def __init__(
        self,
        device: DelongiPrimadonna,
        hass: HomeAssistant,
        beverage: str,
    ) -> None:
        super().__init__(device, hass)
        self._beverage = beverage
        self._attr_unique_id = f'{device.mac}_beverage_{beverage}'
        self._attr_translation_key = f'beverage_{beverage}'
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
