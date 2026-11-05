from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app import store
from app.config import Route, get_settings
from app.connectors.base import JsonCache
from app.connectors.mvg import MVG

log = logging.getLogger(__name__)

router = APIRouter(prefix="/transit", tags=["transit"])


@router.get("/collector-status")
def collector_status():
    """Is the delay collector actually running and collecting?"""
    runs = store.query_df("""
        SELECT station_id, count(*) AS polls, sum(CASE WHEN ok THEN 0 ELSE 1 END) AS failures,
               max(ts_utc) AS last_poll_utc, min(ts_utc) AS first_poll_utc
        FROM collector_runs GROUP BY station_id ORDER BY station_id
    """)
    deps = store.query_df("SELECT count(*) AS n, min(planned_utc) AS first, max(planned_utc) AS last FROM departures")
    stations = [] if runs.empty else [
        {**r, "last_poll_utc": str(r["last_poll_utc"]), "first_poll_utc": str(r["first_poll_utc"])}
        for r in runs.astype(object).to_dict("records")
    ]
    d = {} if deps.empty else deps.iloc[0]
    return {
        "stations": stations,
        "departures": 0 if deps.empty else int(d["n"]),
        "first_planned_utc": None if deps.empty or d["n"] == 0 else str(d["first"]),
        "last_planned_utc": None if deps.empty or d["n"] == 0 else str(d["last"]),
    }


@router.get("/delays")
def delay_summary(route: str | None = None):
    """Delay/cancellation statistics per line for the route's stops, from collected data."""
    s = get_settings()
    try:
        r = s.route(route)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    if not r.stops:
        return {"lines": [], "note": "No stops configured for this route."}
    placeholders = ",".join("?" * len(r.stops))
    df = store.query_df(f"""
        SELECT station_id, label, transport_type,
               count(*)                                              AS departures,
               avg(CASE WHEN cancelled THEN 1.0 ELSE 0.0 END) * 100  AS cancelled_pct,
               avg(CASE WHEN sev THEN 1.0 ELSE 0.0 END) * 100        AS replacement_bus_pct,
               quantile_cont(delay_min, 0.5)                          AS delay_p50,
               quantile_cont(delay_min, 0.9)                          AS delay_p90,
               avg(CASE WHEN delay_min >= 5 THEN 1.0 ELSE 0.0 END) * 100 AS late_5min_pct
        FROM departures
        WHERE station_id IN ({placeholders}) AND realtime
        GROUP BY ALL
        ORDER BY departures DESC
    """, list(r.stops))
    lines = [] if df.empty else df.round(1).astype(object).where(df.notna(), None).to_dict("records")
    names = station_names(r)
    for line in lines:
        line["station_name"] = names.get(line["station_id"])
    return {"lines": lines}


def station_names(r: Route) -> dict[str, str]:
    """Names for the route's stops. MVG has no lookup by id, but its 'nearby' search around home and
    work returns the stops with names. Responses are cached on disk, so this hits MVG once per route."""
    mvg = MVG(cache=JsonCache("mvg_stations"))
    names: dict[str, str] = {}
    for p in (r.home, r.work):
        try:
            for st in mvg.nearby_stations(p.lat, p.lon):
                names.setdefault(st["globalId"], st["name"])
        except Exception as e:  # names are a nicety; never break the delay table over them
            log.warning("station name lookup failed: %s", e)
    return {sid: names[sid] for sid in r.stops if sid in names}
