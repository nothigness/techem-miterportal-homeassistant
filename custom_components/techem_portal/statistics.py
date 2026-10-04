"""Import monthly totals at month end, without fabricating daily readings."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import math
import re
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.util.unit_conversion import EnergyConverter
from .const import DOMAIN, CONF_UNIT

CONF_GAS = 'gas_statistics'


def statistic_id(entry):
    digest = hashlib.sha256(entry.data[CONF_UNIT].encode()).hexdigest()[:24]
    return f'{DOMAIN}:gas_{digest}'


def update_ledger(ledger, reading):
    """Replace a month's value; never append a second copy of the same month."""
    month = reading.get('period', '')
    value = reading.get('heating_kwh')
    if (not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month)
            or reading.get('status') != 'OK'
            or isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError('Invalid monthly reading')
    return {**ledger, month: value}


def build_statistics(ledger, timezone_name):
    """Sparse boundary points: full month booked in its last UTC hour.

    The preceding baseline ensures the first import is counted. Rebuild every
    known point after corrections so subsequent cumulative sums remain correct.
    Daily/hourly graphs show a month-end booking, not a measured load profile.
    """
    zone = ZoneInfo(timezone_name)
    points = {}
    total = Decimal(0)
    for month, value in sorted(ledger.items()):
        year, number = map(int, month.split('-'))
        start = datetime(year, number, 1, tzinfo=zone).astimezone(timezone.utc)
        end = datetime(year + (number == 12), number % 12 + 1, 1, tzinfo=zone).astimezone(timezone.utc)
        baseline = start - timedelta(hours=1)
        points[baseline] = {'start': baseline, 'sum': float(total), 'state': float(total)}
        total += Decimal(str(value))
        last_hour = end - timedelta(hours=1)
        points[last_hour] = {'start': last_hour, 'sum': float(total), 'state': float(total)}
    return [points[key] for key in sorted(points)]


def publish(hass, entry, state):
    if not entry.options.get(CONF_GAS, entry.data.get(CONF_GAS, False)):
        return
    ledger = state.get('monthly_readings', {})
    if not ledger:
        return
    address = state.get('address', {}).get('street', 'Techem')
    metadata = {
        'statistic_id': statistic_id(entry), 'source': DOMAIN,
        'name': f'Techem Gasverbrauch · {address}',
        'unit_of_measurement': 'kWh', 'unit_class': EnergyConverter.UNIT_CLASS,
        'mean_type': StatisticMeanType.NONE, 'has_sum': True,
    }
    async_add_external_statistics(hass, metadata, build_statistics(
        ledger, state.get('statistics_timezone', hass.config.time_zone)))
