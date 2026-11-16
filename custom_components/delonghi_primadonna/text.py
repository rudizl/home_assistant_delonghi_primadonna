"""Text entity for sending raw commands to the device."""

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import DelonghiDeviceEntity
from .device import DelongiPrimadonna


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up debug text entity for a config entry."""

    delongh_device: DelongiPrimadonna = entry.runtime_data
    async_add_entities([DebugInput(delongh_device, hass)])
    return True


class DebugInput(DelonghiDeviceEntity, TextEntity):
    """Implementation debug input."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = 'debug_input'

    async def async_set_value(self, value: str) -> None:
        await self.device.common_command(value)

    @property
    def native_value(self) -> str:
        return ''

    @property
    def available(self) -> bool:
        return super().available and self.device.notify
