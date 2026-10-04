from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import pytest
from custom_components.techem_portal.statistics import build_statistics, update_ledger, publish, statistic_id


def reading(month, value):
    return {'period':month,'heating_kwh':value,'status':'OK'}


def test_idempotent_and_corrected_month():
    ledger=update_ledger({},reading('2026-09',100))
    assert update_ledger(ledger,reading('2026-09',100)) == ledger
    ledger=update_ledger(ledger,reading('2026-10',150))
    first=build_statistics(ledger,'Europe/Berlin')
    assert first[-1]['sum']==250
    ledger=update_ledger(ledger,reading('2026-09',80))
    corrected=build_statistics(ledger,'Europe/Berlin')
    assert corrected[-1]['sum']==230
    assert [p['start'] for p in corrected]==[p['start'] for p in first]
    assert corrected[1]['sum']==80


def test_first_month_baseline_and_zero():
    rows=build_statistics({'2026-09':0},'Europe/Berlin')
    assert len(rows)==2
    assert rows[0]['sum']==rows[1]['sum']==0
    assert rows[0]['start'].astimezone(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d %H')=='2026-08-31 23'
    assert rows[-1]['start'].astimezone(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d %H')=='2026-09-30 23'


def test_dst_year_and_missing_month():
    rows=build_statistics({'2025-12':10,'2026-03':20,'2026-10':30},'Europe/Berlin')
    assert rows[-1]['sum']==60
    assert len(rows)==6
    assert all(r['start'].minute==0 and r['start'].tzinfo==timezone.utc for r in rows)
    assert len({r['start'] for r in rows})==len(rows)


def test_publish_opt_in_metadata():
    entry=SimpleNamespace(data={'unit_id':'TEST'},options={})
    hass=Mock();hass.config.time_zone='Europe/Berlin'
    state={'monthly_readings':{'2026-09':100},'address':{'street':'Testweg'}}
    with patch('custom_components.techem_portal.statistics.async_add_external_statistics') as add:
        publish(hass,entry,state);add.assert_not_called()
        entry.options={'gas_statistics':True}
        publish(hass,entry,state)
        metadata=add.call_args.args[1]
        assert metadata['has_sum'] is True
        assert metadata['unit_of_measurement']=='kWh'
        assert metadata['unit_class']=='energy'
        assert metadata['statistic_id']==statistic_id(entry)
        assert add.call_args.args[2][-1]['sum']==100

@pytest.mark.parametrize('value',[None,True,-1,float('nan')])
def test_invalid_reading(value):
    with pytest.raises(ValueError):update_ledger({},reading('2026-09',value))
