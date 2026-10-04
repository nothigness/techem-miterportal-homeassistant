"""Historical monthly values deliberately have no state_class."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util
from .entity import TechemEntity
from .schedule import previous_month
from .statistics import statistic_id, CONF_GAS

PARALLEL_UPDATES = 0

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(TechemSensor(entry.runtime_data,key) for key in ('heating','original','address','last_success','status'))

class TechemSensor(TechemEntity, SensorEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator,key)
        self.key = key
        self._attr_native_unit_of_measurement = None
        self._attr_translation_key = key
        if key == 'heating':
            self._attr_has_entity_name = False
            self.entity_id = 'sensor.heizverbrauch'
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        elif key == 'last_success':
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key == 'status':
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ['waiting','ok','retry_pending','auth_error']
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key == 'address':
            self._attr_icon = 'mdi:home-map-marker'
        else:
            self._attr_icon = 'mdi:radiator'

    @property
    def available(self):
        # Cached readings remain useful when the next monthly request fails.
        return self.coordinator.data is not None

    @property
    def native_unit_of_measurement(self):
        if self.key == 'original':
            unit = (self.coordinator.data.get('reading') or {}).get('original_unit')
            return 'Einheiten' if unit == 'HCU' else unit
        return self._attr_native_unit_of_measurement

    @property
    def native_value(self):
        data = self.coordinator.data
        reading = data.get('reading') or {}
        if self.key == 'heating': return reading.get('heating_kwh')
        if self.key == 'original': return reading.get('original_amount')
        if self.key == 'address': return data.get('address',{}).get('street')
        if self.key == 'status': return data.get('status')
        value = data.get('last_success')
        return dt_util.parse_datetime(value) if value else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if self.key == 'address': return data.get('address',{})
        if self.key in ('heating','original'):
            reading = data.get('reading') or {}
            return {'consumption_month':reading.get('period'),
                    'target_month':previous_month(dt_util.now().date()),
                    'fetch_status':data.get('status'),
                    'last_successful_fetch':data.get('last_success'),
                    'source_status':reading.get('status'),
                    'source_revision':reading.get('revision'),
                    'gas_statistic_id':statistic_id(self.coordinator.entry) if self.coordinator.entry.options.get(CONF_GAS, self.coordinator.entry.data.get(CONF_GAS, False)) else None}
        return None
