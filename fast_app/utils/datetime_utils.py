from datetime import datetime, timezone, tzinfo


def now(tz: tzinfo = None) -> datetime:
    if not tz:
        tz = timezone.utc
        
    return datetime.now(tz)