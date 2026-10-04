"""Persist monthly readings and limit automatic requests to one per day."""
from datetime import timedelta
import logging
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from .client import fetch_month, TechemError, TechemAuthError
from .const import DOMAIN, CONF_DAY, CONF_UNIT, DEFAULT_DAY
from .schedule import due, previous_month
from .statistics import update_ledger, publish

_LOGGER = logging.getLogger(__name__)

class TechemCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(hours=1))
        self.entry = entry
        self.store = Store(hass, 1, f'{DOMAIN}.{entry.entry_id}')
        self.state = {'address': entry.data.get('address', {}), 'reading': None,
                      'status': 'waiting', 'last_success': None, 'last_attempt_day': None}
        self.force = False

    async def async_load(self):
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.state.update(saved)
        if self.state.get('status') == 'auth_error':
            self.entry.async_start_reauth(self.hass)
        self.state.setdefault('statistics_timezone', self.hass.config.time_zone)
        if self.state.get('reading'):
            self.state['monthly_readings'] = update_ledger(self.state.get('monthly_readings', {}), self.state['reading'])
            await self.store.async_save(self.state)
            publish(self.hass, self.entry, self.state)
        self.data = self.state.copy()

    async def async_manual_refresh(self):
        self.force = True
        await self.async_request_refresh()

    async def _async_update_data(self):
        today = dt_util.now().date()
        day = int(self.entry.options.get(CONF_DAY, self.entry.data.get(CONF_DAY, DEFAULT_DAY)))
        force, self.force = self.force, False
        if not force and not due(today, day, self.state):
            return self.state.copy()
        self.state['last_attempt_day'] = today.isoformat()
        try:
            result = await self.hass.async_add_executor_job(
                fetch_month, self.entry.data[CONF_USERNAME], self.entry.data[CONF_PASSWORD],
                self.entry.data[CONF_UNIT], previous_month(today))
        except TechemAuthError:
            self.state['status'] = 'auth_error'
            self.entry.async_start_reauth(self.hass)
        except (TechemError, ValueError, KeyError, TypeError, OSError):
            # Never log response bodies, account identifiers or credentials.
            self.state['status'] = 'retry_pending'
        else:
            self.state.update(result)
            self.state['monthly_readings'] = update_ledger(self.state.get('monthly_readings', {}), result['reading'])
            self.state.setdefault('statistics_timezone', self.hass.config.time_zone)
            self.state['last_success'] = dt_util.utcnow().isoformat()
            self.state['status'] = 'ok'
        await self.store.async_save(self.state)
        publish(self.hass, self.entry, self.state)
        return self.state.copy()
