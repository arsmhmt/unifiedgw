"""
Timezone utilities for PayCrypt Unified System
Uses EEST (Eastern European Summer Time) UTC+3 as the default timezone
"""

from datetime import datetime, timezone, timedelta
import pytz

# Define EEST timezone (UTC+3)
EEST = timezone(timedelta(hours=3))

# Alternative using pytz for better timezone handling
EEST_PYTZ = pytz.timezone('Europe/Istanbul')  # EEST is typically Istanbul timezone

def now_eest():
    """Get current datetime in EEST timezone"""
    return datetime.now(EEST)

def utc_to_eest(utc_dt):
    """Convert UTC datetime to EEST"""
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(EEST)

def eest_to_utc(eest_dt):
    """Convert EEST datetime to UTC"""
    if eest_dt.tzinfo is None:
        # Assume EEST if no timezone info
        eest_dt = EEST_PYTZ.localize(eest_dt)
    return eest_dt.astimezone(timezone.utc)

def format_datetime_eest(dt, format_string="%Y-%m-%d %H:%M:%S EEST"):
    """Format datetime in EEST timezone"""
    if dt.tzinfo is None:
        dt = utc_to_eest(dt)
    elif dt.tzinfo != EEST:
        dt = dt.astimezone(EEST)

    return dt.strftime(format_string)

def get_current_timestamp():
    """Get current timestamp in EEST"""
    return int(now_eest().timestamp())

# For backward compatibility - these functions maintain the same interface
def datetime_now():
    """Alias for now_eest() - for backward compatibility"""
    return now_eest()

def format_timestamp(dt):
    """Format timestamp in EEST - for backward compatibility"""
    return format_datetime_eest(dt)