import json
from .timezone import format_datetime_eest, utc_to_eest

def escapejs(value):
    """
    Escape a string for use in JavaScript/JSON.
    This is similar to Django's escapejs filter.
    """
    if value is None:
        return ''
    return json.dumps(str(value))[1:-1]  # Remove the surrounding quotes from json.dumps

def format_datetime(value, format_string="%Y-%m-%d %H:%M:%S EEST"):
    """
    Format a datetime object in EEST timezone
    """
    if value is None:
        return ''
    return format_datetime_eest(value, format_string)

def datetime_eest(value, format_string="%d/%m/%Y %H:%M EEST"):
    """
    Convert UTC datetime to EEST and format nicely
    """
    if value is None:
        return ''
    return format_datetime_eest(value, format_string)
