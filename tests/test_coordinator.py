from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from custom_components.techem_portal.coordinator import TechemCoordinator
from custom_components.techem_portal.client import TechemError, TechemAuthError
from custom_components.techem_portal.sensor import TechemSensor

@pytest.fixture
def entry():
    return ConfigEntry(domain='techem_portal',title='Test',version=1,minor_version=1,
        data={'username':'test@example.invalid','password':'test-only','unit_id':'UNIT-A','fetch_day':5},
        options={},source='user',unique_id='test',discovery_keys={},subentries_data=[])

@pytest.fixture
async def coordinator(tmp_path,entry):
    hass=HomeAssistant(str(tmp_path))
    c=TechemCoordinator(hass,entry)
    c.store=Mock(async_save=AsyncMock(),async_load=AsyncMock(return_value=None))
    yield c
    await hass.async_stop()

@pytest.mark.asyncio
async def test_success_persist_and_skip(coordinator):
    c=coordinator
    now=datetime(2026,10,5,tzinfo=timezone.utc)
    result={'address':{'street':'Testweg','floor':'EGR'},'reading':{'period':'2026-09','heating_kwh':0,'original_amount':0,'original_unit':'HCU','status':'OK'}}
    with patch('custom_components.techem_portal.coordinator.dt_util.now',return_value=now),patch.object(c.hass,'async_add_executor_job',new=AsyncMock(return_value=result)) as fetch:
        c.data=await c._async_update_data()
        assert c.data['status']=='ok'
        assert c.store.async_save.await_count==1
        assert TechemSensor(c,'heating').native_value==0
        assert TechemSensor(c,'heating').state_class is None
        assert TechemSensor(c,'address').extra_state_attributes['floor']=='EGR'
        await c._async_update_data()
        assert fetch.await_count==1
        c.force=True
        await c._async_update_data()
        assert fetch.await_count==2

@pytest.mark.asyncio
async def test_failure_preserves_reading_and_retries_tomorrow(coordinator):
    c=coordinator
    c.state['reading']={'period':'2026-08','heating_kwh':12}
    with patch('custom_components.techem_portal.coordinator.dt_util.now',return_value=datetime(2026,10,6,tzinfo=timezone.utc)),patch.object(c.hass,'async_add_executor_job',new=AsyncMock(side_effect=TechemError('missing'))) as fetch:
        c.data=await c._async_update_data()
        assert c.data['reading']['heating_kwh']==12
        assert c.data['status']=='retry_pending'
        assert TechemSensor(c,'heating').available
        await c._async_update_data()
        assert fetch.await_count==1
    with patch('custom_components.techem_portal.coordinator.dt_util.now',return_value=datetime(2026,10,7,tzinfo=timezone.utc)),patch.object(c.hass,'async_add_executor_job',new=AsyncMock(side_effect=TechemError('missing'))) as fetch:
        await c._async_update_data()
        assert fetch.await_count==1

@pytest.mark.asyncio
async def test_auth_failure_stops_automatic_attempts(coordinator):
    c=coordinator
    with patch.object(c.hass,'async_add_executor_job',new=AsyncMock(side_effect=TechemAuthError())),patch.object(c.entry,'async_start_reauth') as reauth:
        c.data=await c._async_update_data()
        assert c.data['status']=='auth_error'
        reauth.assert_called_once()
        assert not TechemSensor(c,'heating').native_value

@pytest.mark.asyncio
async def test_restart_loads_cache(coordinator):
    c=coordinator
    cached={'reading':{'period':'2026-09','heating_kwh':42,'status':'OK'},'status':'ok','last_attempt_day':'2026-10-05'}
    c.store.async_load.return_value=cached
    await c.async_load()
    assert c.data['reading']['heating_kwh']==42
    with patch('custom_components.techem_portal.coordinator.dt_util.now',return_value=datetime(2026,10,5,tzinfo=timezone.utc)),patch.object(c.hass,'async_add_executor_job',new=AsyncMock()) as fetch:
        await c._async_update_data()
        fetch.assert_not_awaited()
