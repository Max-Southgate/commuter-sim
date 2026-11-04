"""Backfill historical hourly weather for the same calendar window in past years.

E.g. stay = 10 Jan - 21 Mar 2027 -> fetch 10 Jan - 21 Mar for every year 1996..2026.
Each year's window is one API call, cached on disk, so re-running is free.
"""
from __future__ import annotations

import datetime as dt
import logging

from app import store
from app.config import Route, Settings
from app.connectors.open_meteo import OpenMeteo

log = logging.getLogger(__name__)


def shift_to_year(d: dt.date, year: int) -> dt.date:
    try:
        return d.replace(year=year)
    except ValueError:  # 29 Feb in a non-leap year
        return d.replace(year=year, day=28)


def year_windows(route: Route, first_year: int, last_year: int) -> list[tuple[int, dt.date, dt.date]]:
    """(label_year, start, end) for each historical copy of the stay period."""
    span = route.period_end - route.period_start
    latest_available = dt.date.today() - dt.timedelta(days=6)  # ERA5 lags ~5 days
    out = []
    for y in range(first_year, last_year + 1):
        start = shift_to_year(route.period_start, y)
        end = min(start + span, latest_available)
        if end > start:
            out.append((y, start, end))
    return out


def backfill(settings: Settings, route: Route, client: OpenMeteo | None = None) -> int:
    om = client or OpenMeteo(timezone=settings.timezone)
    p = route.midpoint
    total = 0
    for year, start, end in year_windows(route, settings.first_year, settings.last_year):
        df = om.archive(p.lat, p.lon, start, end, location_id=route.id)
        total += store.upsert_observations(df)
        log.info("%s %d: %d rows", route.id, year, len(df))
    return total
