"""Collect live MVG departures for the configured stops and keep the latest state of each.

Each (station, line, trip, planned time) is one row. Every poll updates it, so the row
ends up holding the last delay/cancellation status seen before the vehicle left -
which is the best free approximation of "what actually happened".
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from zoneinfo import ZoneInfo

import pandas as pd

from app import store
from app.config import Settings
from app.connectors.mvg import MVG

log = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO departures
SELECT station_id, line_id, trip_code, planned_utc, label, transport_type, destination, platform,
       realtime, delay_min, realtime_utc, cancelled, sev, infos,
       ? AS first_seen_utc, ? AS last_seen_utc, 1 AS n_obs
FROM incoming
ON CONFLICT (station_id, line_id, trip_code, planned_utc) DO UPDATE SET
    realtime      = EXCLUDED.realtime,
    delay_min     = EXCLUDED.delay_min,
    realtime_utc  = EXCLUDED.realtime_utc,
    cancelled     = EXCLUDED.cancelled,
    sev           = EXCLUDED.sev,
    platform      = EXCLUDED.platform,
    infos         = EXCLUDED.infos,
    last_seen_utc = EXCLUDED.last_seen_utc,
    n_obs         = departures.n_obs + 1
"""


def upsert_departures(df: pd.DataFrame, now_utc: dt.datetime) -> int:
    if df.empty:
        return 0
    df = df.drop_duplicates(subset=["station_id", "line_id", "trip_code", "planned_utc"], keep="last")
    with store.connect() as con:
        con.register("incoming", df)
        con.execute(UPSERT_SQL, [now_utc, now_utc])
    return len(df)


def log_run(station_id: str, n: int, ok: bool, error: str | None, now_utc: dt.datetime) -> None:
    with store.connect() as con:
        con.execute("INSERT INTO collector_runs VALUES (?, ?, ?, ?, ?)", [now_utc, station_id, n, ok, error])


def all_stops(settings: Settings) -> list[str]:
    seen: dict[str, None] = {}
    for r in settings.routes.values():
        for s in r.stops:
            seen[s] = None
    return list(seen)


def in_window(settings: Settings, now_local: dt.datetime) -> bool:
    c = settings.collector
    if c.weekdays_only and now_local.weekday() >= 5:
        return False
    if not c.windows:
        return True
    t = now_local.time()
    return any(a <= t <= b for a, b in c.windows)


def poll_once(settings: Settings, mvg: MVG | None = None) -> int:
    mvg = mvg or MVG()
    total = 0
    for station in all_stops(settings):
        now_utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        try:
            df = mvg.departures(station, limit=settings.collector.departures_per_poll)
            n = upsert_departures(df, now_utc)
            log_run(station, n, True, None, now_utc)
            total += n
        except Exception as e:  # keep collecting other stations; record the failure
            log.warning("poll failed for %s: %s", station, e)
            log_run(station, 0, False, str(e)[:500], now_utc)
    return total


def run_forever(settings: Settings, ignore_windows: bool = False) -> None:
    stops = all_stops(settings)
    if not stops:
        raise SystemExit("No stops configured. Add MVG station ids under routes.<id>.stops in config/routes.yaml "
                         "(find them with: python -m app.tools.stops nearby --lat .. --lon ..)")
    tz = ZoneInfo(settings.timezone)
    mvg = MVG()
    log.info("Collecting departures for %s every %ss (windows=%s)", stops, settings.collector.interval_seconds,
             "ignored" if ignore_windows else settings.collector.windows)
    while True:
        now_local = dt.datetime.now(tz)
        if ignore_windows or in_window(settings, now_local):
            n = poll_once(settings, mvg)
            log.info("%s polled %d departures", now_local.strftime("%a %H:%M"), n)
        time.sleep(settings.collector.interval_seconds)
