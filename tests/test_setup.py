from pathlib import Path
from unittest.mock import patch
import shutil
import asyncio
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntries, ConfigEntryState
from homeassistant import loader

@pytest.mark.asyncio
async def test_real_platform_setup_and_unload(tmp_path):
    shutil.copytree(Path(__file__).parents[1]/'custom_components',tmp_path/'custom_components',ignore=shutil.ignore_patterns('__pycache__'))
    hass=HomeAssistant(str(tmp_path))
    hass.config.time_zone='Europe/Berlin'
    loader.async_setup(hass)
    from homeassistant.helpers.recorder import async_initialize_recorder
    async_initialize_recorder(hass)
    from homeassistant.helpers import entity_registry, device_registry, area_registry, floor_registry, label_registry, issue_registry, category_registry
    device_registry.async_setup(hass)
    await asyncio.gather(*(module.async_load(hass) for module in (entity_registry,device_registry,area_registry,floor_registry,label_registry,issue_registry,category_registry)))
    hass.config_entries=ConfigEntries(hass,{})
    await hass.config_entries.async_initialize()
    entry=ConfigEntry(domain='techem_portal',title='Test',version=1,minor_version=1,
        data={'username':'test@example.invalid','password':'test-only','unit_id':'UNIT-A','fetch_day':5},
        options={'gas_statistics':True},source='user',unique_id='test',discovery_keys={},subentries_data=[])
    result={'address':{'street':'Testweg','floor':'EGR'},'reading':{'period':'2026-09','heating_kwh':100,'original_amount':0,'original_unit':'HCU','status':'OK'}}
    try:
        with patch('custom_components.techem_portal.coordinator.fetch_month',return_value=result):
            await hass.config_entries.async_add(entry)
            await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED
        states=hass.states.async_all()
        assert len([s for s in states if s.domain=='sensor'])==5
        assert hass.states.get('sensor.heizverbrauch') is not None
        device=device_registry.async_get(hass).async_get_device_by_identifier(('techem_portal','UNIT-A'),entry.entry_id)
        assert device.name == 'Heizungsverbrauch Testweg'
        assert len([s for s in states if s.domain=='button'])==1
        from homeassistant.components.recorder.util import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period
        from custom_components.techem_portal.statistics import statistic_id, publish
        from datetime import datetime, timezone
        await hass.async_start()
        recorder=get_instance(hass)
        await recorder.async_block_till_done()
        sid=statistic_id(entry)
        async def read_stats():
            return await recorder.async_add_executor_job(
                statistics_during_period, hass, datetime(2026,8,1,tzinfo=timezone.utc),
                datetime(2026,11,1,tzinfo=timezone.utc), {sid}, 'hour', None, {'sum','state'})
        first=await read_stats()
        assert len(first[sid])==2
        assert first[sid][-1]['sum']==100
        publish(hass,entry,entry.runtime_data.state)
        await recorder.async_block_till_done()
        repeated=await read_stats()
        assert len(repeated[sid])==2
        assert repeated[sid][-1]['sum']==100
        entry.runtime_data.state['monthly_readings']['2026-09']=80
        publish(hass,entry,entry.runtime_data.state)
        await recorder.async_block_till_done()
        corrected=await read_stats()
        assert len(corrected[sid])==2
        assert corrected[sid][-1]['sum']==80
        assert await hass.config_entries.async_unload(entry.entry_id)
    finally:
        await hass.async_stop()
