"""Shorten only known generated IDs; leave user-selected IDs untouched."""
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from .const import CONF_UNIT


def migrate_heating_id(hass, entry, address):
    registry = er.async_get(hass)
    unique_id = f'{entry.unique_id}_{entry.data[CONF_UNIT]}_heating'
    entity_id = registry.async_get_entity_id('sensor', 'techem_portal', unique_id)
    if not entity_id:
        return
    street = address.get('street') or 'Techem Verbrauchsstelle'
    old_names = ('Heizverbrauch letzter abgerufener Monat', 'Heating consumption last retrieved month')
    old_ids = {f'sensor.{slugify(street + " " + name)}' for name in old_names}
    if entity_id not in old_ids:
        return
    target = registry.async_get_available_entity_id('sensor', 'heizverbrauch')
    registry.async_update_entity(entity_id, new_entity_id=target)
