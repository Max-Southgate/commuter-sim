"""Turn decades of hourly weather into "what would my commutes have been like?".

Every historical day in the stay window becomes two commute *legs* (out, back). Each
leg gets the weather during the hours it overlaps and is judged cyclable or not against
the user's thresholds. Everything downstream (summaries, calendar heatmap, Phase 3
simulator) builds on that leg table.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict

import numpy as np
import pandas as pd

from app import store
from app.collectors.weather_history import year_windows
from app.config import CyclingThresholds, Route, Settings
from app.connectors.daylight import is_dark, sun_times
from app.connectors.open_meteo import ARCHIVE_SOURCE

# precipitation/snowfall at hour T are sums over (T-1h, T]; temperatures are instants at T.
ACCUMULATED = {"precipitation", "rain", "snowfall"}


def load_weather(route_id: str, source: str = ARCHIVE_SOURCE) -> pd.DataFrame:
    df = store.query_df(
        "SELECT ts, metric, value FROM observations WHERE source = ? AND location_id = ?",
        [source, route_id],
    )
    if df.empty:
        return df
    wide = df.pivot_table(index="ts", columns="metric", values="value", aggfunc="first").sort_index()
    wide.columns.name = None
    return wide


_weather_cache: dict[tuple[str, str], tuple[int, pd.DataFrame]] = {}


def load_weather_cached(route_id: str, source: str = ARCHIVE_SOURCE) -> pd.DataFrame:
    """Historical weather barely changes; keep it in memory so slider tweaks are instant."""
    n = store.query_df("SELECT count(*) AS n FROM observations WHERE source = ? AND location_id = ?",
                       [source, route_id])
    count = 0 if n.empty else int(n["n"].iloc[0])
    hit = _weather_cache.get((route_id, source))
    if hit is None or hit[0] != count:
        hit = (count, load_weather(route_id, source))
        _weather_cache[(route_id, source)] = hit
    return hit[1]


def leg_hours(start: dt.time, minutes: int) -> tuple[list[int], list[int]]:
    """Hours of day whose weather applies to a leg starting at `start` lasting `minutes`.

    Returns (accumulation stamps, instantaneous stamps). An accumulation stamp T covers
    (T-1h, T]; it overlaps the leg [s, e] iff s < T < e + 1h.
    """
    s = start.hour * 60 + start.minute
    e = s + minutes
    accum = [h for h in range(24) if s < h * 60 < e + 60]
    inst = [h for h in range(24) if (s // 60) * 60 <= h * 60 <= -(-e // 60) * 60]
    return accum, inst


def _leg_weather(wide: pd.DataFrame, start: dt.time, minutes: int) -> pd.DataFrame:
    accum_h, inst_h = leg_hours(start, minutes)
    hours = wide.index.hour
    dates = wide.index.normalize()

    def agg(cols, hset, how):
        cols = [c for c in cols if c in wide.columns]
        sub = wide.loc[np.isin(hours, hset), cols]
        return sub.groupby(dates[np.isin(hours, hset)]).agg(how)

    acc = agg(["precipitation", "snowfall"], accum_h, "max").rename(
        columns={"precipitation": "precip_max_mm_h", "snowfall": "snowfall_max_cm_h"})
    inst = agg(["temperature_2m", "apparent_temperature", "wind_gusts_10m", "snow_depth"], inst_h, "min")
    inst = inst.rename(columns={"temperature_2m": "temp_min_c", "apparent_temperature": "feels_min_c",
                                "snow_depth": "snow_depth_min_m"})
    gust = agg(["wind_gusts_10m"], inst_h, "max").rename(columns={"wind_gusts_10m": "gust_max_kmh"})
    inst = inst.drop(columns=["wind_gusts_10m"], errors="ignore")
    out = acc.join(inst, how="outer").join(gust, how="outer")
    out.index = out.index.date
    out.index.name = "date"
    return out


def build_legs(wide: pd.DataFrame, route: Route, settings: Settings, th: CyclingThresholds,
               since_year: int | None = None) -> pd.DataFrame:
    """One row per (historical date, leg) with weather, flags and the 2027-equivalent date."""
    if wide.empty:
        return pd.DataFrame()

    # Map each historical date onto the stay period (same offset from the period start).
    mapping = []
    first = max(settings.first_year, since_year or settings.first_year)
    for year, start, end in year_windows(route, first, settings.last_year):
        for off in range((end - start).days + 1):
            mapping.append((start + dt.timedelta(days=off), year, route.period_start + dt.timedelta(days=off)))
    dmap = pd.DataFrame(mapping, columns=["date", "year", "stay_date"]).set_index("date")

    # Darkness depends on the calendar date, not the weather -> compute once per stay date.
    p = route.midpoint
    dark = {}
    for d in dmap["stay_date"].unique():
        t = sun_times(p.lat, p.lon, d, settings.timezone)
        for leg, lt in (("out", route.out_time), ("back", route.back_time)):
            s = dt.datetime.combine(d, lt)
            dark[(d, leg)] = is_dark(s, s + dt.timedelta(minutes=route.commute_minutes), t)

    frames = []
    for leg, lt in (("out", route.out_time), ("back", route.back_time)):
        w = _leg_weather(wide, lt, route.commute_minutes).join(dmap, how="inner")
        w["leg"] = leg
        w["dark"] = [dark[(d, leg)] for d in w["stay_date"]]
        frames.append(w)
    legs = pd.concat(frames).reset_index()

    snow_cm = legs.get("snow_depth_min_m", pd.Series(0.0, index=legs.index)).fillna(0) * 100
    legs["wet"] = legs["precip_max_mm_h"].fillna(0) > th.max_precip_mm_h
    legs["snowing"] = legs["snowfall_max_cm_h"].fillna(0) > 0.05
    legs["snow_on_ground"] = snow_cm > th.max_snow_depth_cm
    legs["below_zero"] = legs["temp_min_c"] < 0
    legs["too_cold"] = legs["feels_min_c"] < th.min_temp_c
    legs["too_windy"] = legs["gust_max_kmh"] > th.max_gust_kmh
    legs["cyclable"] = ~(legs["wet"] | legs["snowing"] | legs["too_cold"] | legs["too_windy"]
                         | legs["snow_on_ground"])
    legs["weekday"] = pd.to_datetime(legs["stay_date"]).dt.day_of_week
    return legs


def _pct(s: pd.Series) -> float:
    return round(float(s.mean()) * 100, 1) if len(s) else 0.0


def summarize(legs: pd.DataFrame, route: Route, settings: Settings, th: CyclingThresholds) -> dict:
    commute_days = route.commute_days()
    n_commute = len(commute_days)
    base = {
        "route": {"id": route.id, "name": route.name, "line": route.line,
                  "home": asdict(route.home), "work": asdict(route.work),
                  "out_time": route.out_time.strftime("%H:%M"), "back_time": route.back_time.strftime("%H:%M"),
                  "commute_minutes": route.commute_minutes},
        "period": {"start": route.period_start.isoformat(), "end": route.period_end.isoformat(),
                   "commute_days": n_commute},
        "thresholds": asdict(th),
        "using_example_config": settings.source_file.name == "routes.example.yaml",
    }
    if legs.empty:
        return {**base, "has_data": False}

    flags = ["wet", "snowing", "snow_on_ground", "below_zero", "too_cold", "too_windy", "dark", "cyclable"]
    per_leg = {leg: {f: _pct(g[f]) for f in flags} | {
                   "median_feels_c": round(float(g["feels_min_c"].median()), 1),
                   "median_temp_c": round(float(g["temp_min_c"].median()), 1)}
               for leg, g in legs.groupby("leg")}

    # Only working days count towards "how many of MY commutes".
    work = legs[legs["weekday"].isin(route.workdays)]
    day = work.pivot_table(index=["year", "stay_date"], columns="leg", values="cyclable", aggfunc="first").dropna()
    day["both"] = day["out"] & day["back"]
    day["ok_legs"] = day["out"].astype(int) + day["back"].astype(int)

    per_year = day.groupby(level="year").agg(both_days=("both", "sum"), ok_legs=("ok_legs", "sum"))
    per_year["n"] = day.groupby(level="year").size()
    # scale to this stay's number of commute days (a year's window may be truncated, e.g. current year)
    per_year["both_days_scaled"] = per_year["both_days"] / per_year["n"] * n_commute
    per_year["ok_legs_scaled"] = per_year["ok_legs"] / per_year["n"] * n_commute
    q = per_year["both_days_scaled"].quantile([0.1, 0.5, 0.9]).round(0)

    # Weekly profile through the stay (does it get better towards March?)
    wk = legs.copy()
    wk["week"] = (pd.to_datetime(wk["stay_date"]) - pd.Timestamp(route.period_start)).dt.days // 7
    weekly = []
    for w, g in wk.groupby("week"):
        start = route.period_start + dt.timedelta(days=7 * int(w))
        o, b = g[g["leg"] == "out"], g[g["leg"] == "back"]
        weekly.append({
            "week": int(w), "week_start": start.isoformat(),
            "out_cyclable_pct": _pct(o["cyclable"]), "back_cyclable_pct": _pct(b["cyclable"]),
            "out_dark_pct": _pct(o["dark"]), "back_dark_pct": _pct(b["dark"]),
            "out_median_feels_c": round(float(o["feels_min_c"].median()), 1),
            "back_median_feels_c": round(float(b["feels_min_c"].median()), 1),
            "wet_pct": _pct(g["wet"] | g["snowing"]),
        })

    # Why legs fail (a leg can fail for several reasons)
    failing = legs[~legs["cyclable"]]
    reasons = {f: _pct(failing[f]) for f in ["wet", "snowing", "snow_on_ground", "too_cold", "too_windy"]}

    return {
        **base,
        "has_data": True,
        "years": {"first": int(legs["year"].min()), "last": int(legs["year"].max()),
                  "n": int(legs["year"].nunique())},
        "legs": per_leg,
        "days": {
            "both_cyclable_pct": _pct(day["both"]),
            "one_cyclable_pct": _pct(day["ok_legs"] == 1),
            "none_cyclable_pct": _pct(day["ok_legs"] == 0),
            "expected_both_days": {"p10": int(q.loc[0.1]), "median": int(q.loc[0.5]), "p90": int(q.loc[0.9])},
            "expected_ok_legs_median": int(round(per_year["ok_legs_scaled"].median())),
            "total_legs": 2 * n_commute,
        },
        "per_year": [{"year": int(y), "both_days": int(round(r.both_days_scaled)),
                      "ok_legs": int(round(r.ok_legs_scaled))} for y, r in per_year.iterrows()],
        "weekly": weekly,
        "fail_reasons_pct": reasons,
    }


def calendar(legs: pd.DataFrame, route: Route) -> dict:
    """Year x stay-date grid. Value = number of cyclable legs that day (0, 1, 2); null = weekend."""
    if legs.empty:
        return {"years": [], "dates": [], "values": []}
    g = legs.pivot_table(index=["year", "stay_date"], columns="leg", values="cyclable", aggfunc="first")
    g["v"] = g["out"].astype(int) + g["back"].astype(int)
    grid = g["v"].unstack("stay_date").sort_index()
    dates = sorted(grid.columns)
    values = []
    for y in grid.index:
        row = []
        for d in dates:
            v = grid.at[y, d]
            row.append(None if d.weekday() not in route.workdays or pd.isna(v) else int(v))
        values.append(row)
    return {"years": [int(y) for y in grid.index], "dates": [d.isoformat() for d in dates], "values": values}


def daylight_table(route: Route, settings: Settings) -> list[dict]:
    p = route.midpoint
    out, d = [], route.period_start
    while d <= route.period_end:
        t = sun_times(p.lat, p.lon, d, settings.timezone)
        out.append({"date": d.isoformat(), **{k: v.strftime("%H:%M") for k, v in t.items()}})
        d += dt.timedelta(days=1)
    return out
