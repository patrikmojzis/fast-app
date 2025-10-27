from datetime import datetime, timezone

def now(tz: timezone = None) -> datetime:
    if not tz:
        tz = timezone.utc
        
    return datetime.now(tz)