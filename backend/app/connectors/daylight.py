"""Sunrise / sunset / civil twilight, computed locally (no network)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun


def sun_times(lat: float, lon: float, day: dt.date, timezone: str = "Europe/Berlin") -> dict[str, dt.datetime]:
    """Returns naive local datetimes for dawn (civil), sunrise, sunset, dusk (civil)."""
    tz = ZoneInfo(timezone)
    loc = LocationInfo(latitude=lat, longitude=lon, timezone=timezone)
    s = sun(loc.observer, date=day, tzinfo=tz)
    return {k: s[k].replace(tzinfo=None) for k in ("dawn", "sunrise", "sunset", "dusk")}


def is_dark(start: dt.datetime, end: dt.datetime, times: dict[str, dt.datetime]) -> bool:
    """True if any part of [start, end] falls before civil dawn or after civil dusk.

    Civil twilight is used because that's roughly when you genuinely need lights and
    visibility to drivers drops; between dawn and sunrise it's grey but visible.
    """
    return start < times["dawn"] or end > times["dusk"]
