from unittest.mock import AsyncMock, Mock, patch
import pytest
from custom_components.techem_portal.config_flow import TechemConfigFlow, credentials_schema
from custom_components.techem_portal.client import TechemAuthError
import voluptuous as vol

@pytest.mark.asyncio
async def test_single_unit_setup():
    flow=TechemConfigFlow()
    flow.hass=Mock(async_add_executor_job=AsyncMock(return_value={'UNIT-A':{'street':'Testweg'}}))
    with patch.object(flow,'async_set_unique_id',new=AsyncMock()),patch.object(flow,'_abort_if_unique_id_configured'):
        result=await flow.async_step_user({'username':' test@example.invalid ','password':'test-only','fetch_day':5})
    assert result['type']=='create_entry'
    assert result['data']['unit_id']=='UNIT-A'
    assert result['data']['username']=='test@example.invalid'

@pytest.mark.asyncio
async def test_bad_login_returns_form():
    flow=TechemConfigFlow()
    flow.hass=Mock(async_add_executor_job=AsyncMock(side_effect=TechemAuthError()))
    with patch.object(flow,'async_set_unique_id',new=AsyncMock()),patch.object(flow,'_abort_if_unique_id_configured'):
        result=await flow.async_step_user({'username':'test@example.invalid','password':'test-only','fetch_day':5})
    assert result['errors']=={'base':'invalid_auth'}

@pytest.mark.asyncio
async def test_multiple_units_selection():
    flow=TechemConfigFlow()
    flow.hass=Mock(async_add_executor_job=AsyncMock(return_value={'UNIT-A':{'street':'A'},'UNIT-B':{'street':'B'}}))
    with patch.object(flow,'async_set_unique_id',new=AsyncMock()),patch.object(flow,'_abort_if_unique_id_configured'):
        result=await flow.async_step_user({'username':'test@example.invalid','password':'test-only','fetch_day':5})
    assert result['step_id']=='unit'
    result=await flow.async_step_unit({'unit_id':'UNIT-B'})
    assert result['data']['address']['street']=='B'

@pytest.mark.parametrize('day',[0,32,-1])
def test_invalid_day(day):
    with pytest.raises(vol.Invalid):credentials_schema()({'username':'test@example.invalid','password':'test-only','fetch_day':day})
