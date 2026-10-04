"""Calendar logic independent of Home Assistant; uses its local date."""
from calendar import monthrange
from datetime import timedelta


def previous_month(today):
    return (today.replace(day=1)-timedelta(days=1)).strftime('%Y-%m')


def due(today, day, state):
    if state.get('status') == 'auth_error':
        return False
    if state.get('last_attempt_day') == today.isoformat():
        return False
    reading = state.get('reading')
    if not reading:
        return True  # Initial import; thereafter at most once a local day.
    if today.day < min(day, monthrange(today.year, today.month)[1]):
        return False
    return reading.get('period') != previous_month(today)
