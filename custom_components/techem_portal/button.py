from homeassistant.components.button import ButtonEntity
from .entity import TechemEntity

PARALLEL_UPDATES = 1

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TechemRefresh(entry.runtime_data)])

class TechemRefresh(TechemEntity, ButtonEntity):
    _attr_translation_key = 'refresh'
    _attr_icon = 'mdi:refresh'

    def __init__(self, coordinator):
        super().__init__(coordinator,'refresh')

    async def async_press(self):
        await self.coordinator.async_manual_refresh()
