from datetime import date
from custom_components.techem_portal.schedule import due, previous_month

def test_year_boundary():
    assert previous_month(date(2026,1,5)) == '2025-12'

def test_day_and_restart():
    state={'reading':{'period':'2026-07'}}
    assert not due(date(2026,9,4),5,state)
    assert due(date(2026,9,8),5,state)
    state['last_attempt_day']='2026-09-08'
    assert not due(date(2026,9,8),5,state)
    assert due(date(2026,9,9),5,state)

def test_february_and_leap_year():
    state={'reading':{'period':'2025-12'}}
    assert due(date(2026,2,28),31,state)
    assert not due(date(2028,2,28),31,state)
    assert due(date(2028,2,29),31,state)

def test_already_imported():
    assert not due(date(2026,9,6),5,{'reading':{'period':'2026-08'}})

def test_initial_import_and_auth_stop():
    assert due(date(2026,9,1),5,{'reading':None})
    assert not due(date(2026,9,6),5,{'reading':None,'status':'auth_error'})
