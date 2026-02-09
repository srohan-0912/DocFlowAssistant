# utils/time_utils.py
from datetime import datetime
import pytz

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def ist_time_filter(utc_dt):
    if not utc_dt:
        return "-"
    ist = pytz.timezone('Asia/Kolkata')
    return utc_dt.astimezone(ist).strftime('%b %d, %Y %I:%M:%S %p')
