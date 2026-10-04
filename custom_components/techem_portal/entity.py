"""Shared identity and device metadata."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_UNIT

class TechemEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._attr_unique_id = f'{coordinator.entry.unique_id}_{coordinator.entry.data[CONF_UNIT]}_{key}'

    @property
    def device_info(self):
        address = self.coordinator.data.get('address', {})
        return DeviceInfo(identifiers={(DOMAIN,self.coordinator.entry.data[CONF_UNIT])},
                          name='Heizungsverbrauch ' + (address.get('street') or 'Techem'),
                          manufacturer='Techem', model='Mieterportal')
