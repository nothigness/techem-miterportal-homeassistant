"""UI setup, day options and credential renewal."""
import hashlib
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import selector
from .client import validate_credentials, TechemAuthError, TechemError
from .const import DOMAIN, CONF_DAY, CONF_UNIT, DEFAULT_DAY
from .statistics import CONF_GAS


def day_selector():
    return selector.NumberSelector(selector.NumberSelectorConfig(
        min=1, max=31, step=1, mode=selector.NumberSelectorMode.BOX))


def credentials_schema(day=True):
    fields = {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    }
    if day:
        fields[vol.Required(CONF_DAY, default=DEFAULT_DAY)] = day_selector()
        fields[vol.Optional(CONF_GAS, default=False)] = bool
    return vol.Schema(fields)


class TechemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_USERNAME].strip()
            if not email or not user_input[CONF_PASSWORD]:
                errors['base'] = 'invalid_auth'
            else:
                await self.async_set_unique_id(hashlib.sha256(email.casefold().encode()).hexdigest())
                self._abort_if_unique_id_configured()
                try:
                    self._units = await self.hass.async_add_executor_job(validate_credentials, email, user_input[CONF_PASSWORD])
                except TechemAuthError:
                    errors['base'] = 'invalid_auth'
                except (TechemError, ValueError, KeyError, TypeError, OSError):
                    errors['base'] = 'cannot_connect'
                else:
                    self._input = {**user_input, CONF_USERNAME: email}
                    if len(self._units) == 1:
                        return self._finish(next(iter(self._units)))
                    return await self.async_step_unit()
        return self.async_show_form(step_id='user', data_schema=credentials_schema(), errors=errors)

    def _finish(self, unit):
        address = self._units[unit]
        title = 'Heizungsverbrauch ' + (address.get('street') or 'Techem')
        return self.async_create_entry(title=title, data={**self._input, CONF_UNIT:unit,'address':address})

    async def async_step_unit(self, user_input=None):
        if user_input is not None and user_input[CONF_UNIT] in self._units:
            return self._finish(user_input[CONF_UNIT])
        options = {k: ' · '.join(str(v) for v in a.values() if v) or k for k,a in self._units.items()}
        return self.async_show_form(step_id='unit', data_schema=vol.Schema({vol.Required(CONF_UNIT):vol.In(options)}))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                available = await self.hass.async_add_executor_job(validate_credentials, entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
                if entry.data[CONF_UNIT] not in available:
                    raise TechemError('Verbrauchsstelle fehlt')
            except TechemAuthError:
                errors['base'] = 'invalid_auth'
            except (TechemError, ValueError, KeyError, TypeError, OSError):
                errors['base'] = 'cannot_connect'
            else:
                coordinator = entry.runtime_data
                coordinator.state.update(status='waiting', last_attempt_day=None)
                await coordinator.store.async_save(coordinator.state)
                return self.async_update_reload_and_abort(entry, data_updates={CONF_PASSWORD:user_input[CONF_PASSWORD]})
        return self.async_show_form(step_id='reauth_confirm', data_schema=vol.Schema({vol.Required(CONF_PASSWORD):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TechemOptionsFlow()


class TechemOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title='', data=user_input)
        day = self.config_entry.options.get(CONF_DAY, self.config_entry.data.get(CONF_DAY, DEFAULT_DAY))
        return self.async_show_form(step_id='init', data_schema=vol.Schema({
            vol.Required(CONF_DAY, default=day):day_selector(),
            vol.Optional(CONF_GAS, default=self.config_entry.options.get(CONF_GAS, self.config_entry.data.get(CONF_GAS, False))):bool,
        }))
