from unittest.mock import Mock, patch
from types import SimpleNamespace
from custom_components.techem_portal.config_flow import day_selector
from custom_components.techem_portal.migration import migrate_heating_id


def test_number_input_mode():
    assert day_selector().config['mode'] == 'box'
    assert day_selector().config['step'] == 1


def test_generated_id_migration_and_user_override():
    entry=SimpleNamespace(unique_id='test',data={'unit_id':'UNIT-A'})
    reg=Mock()
    reg.async_get_available_entity_id.return_value='sensor.heizverbrauch'
    with patch('custom_components.techem_portal.migration.er.async_get',return_value=reg):
        reg.async_get_entity_id.return_value='sensor.testweg_heizverbrauch_letzter_abgerufener_monat'
        migrate_heating_id(None,entry,{'street':'Testweg'})
        reg.async_update_entity.assert_called_once_with('sensor.testweg_heizverbrauch_letzter_abgerufener_monat',new_entity_id='sensor.heizverbrauch')
        reg.reset_mock()
        reg.async_get_entity_id.return_value='sensor.mein_eigener_name'
        migrate_heating_id(None,entry,{'street':'Testweg'})
        reg.async_update_entity.assert_not_called()
