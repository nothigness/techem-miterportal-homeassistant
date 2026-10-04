"""Techem Mieterportal integration."""
from homeassistant.const import Platform
from .coordinator import TechemCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

async def async_setup_entry(hass, entry):
    coordinator = TechemCoordinator(hass, entry)
    await coordinator.async_load()
    from .migration import migrate_heating_id
    migrate_heating_id(hass, entry, coordinator.state.get('address', {}))
    entry.runtime_data = coordinator
    await coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload))
    return True

async def async_reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_remove_entry(hass, entry):
    from homeassistant.helpers.storage import Store
    from .const import DOMAIN
    await Store(hass, 1, f'{DOMAIN}.{entry.entry_id}').async_remove()
